"""Corporate surveillance: quotes, SEC EDGAR (filings + 13F holders), US lobbying (LDA), EU register import,
regulator feeds (fines), Wikidata people/ownership."""
import csv
import io
import json
import logging
import re
import time
import xml.etree.ElementTree as ET

import feedparser

from .. import config, db, http
from ..processing import text
from . import markets
from .base import Collector, register
from .rss import load_yaml
from .sources_loader import edge, node, slug

log = logging.getLogger("netwatch.corpos")


def load_companies() -> int:
    cfg = load_yaml("corpos.yaml") or {}
    n = 0
    with db.session() as con:
        for c in cfg.get("companies", []):
            con.execute("""INSERT INTO companies(id,name,ticker,sector,country,data) VALUES(?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,ticker=excluded.ticker,sector=excluded.sector,
                country=excluded.country,data=excluded.data""",
                        (c["id"], c["name"], c.get("stooq"), c.get("sector"), c.get("country"), json.dumps(c, ensure_ascii=False)))
            node(con, f"co:{c['id']}", c["name"], "company", c.get("country"), c.get("qid"))
            for m in c.get("owns_media", []):
                edge(con, f"co:{c['id']}", f"media:{m['source']}", "owns", m.get("ref"), 1.0, "owns media")
            n += 1
    return n


def company_quotes() -> int:
    load_companies()
    n = 0
    for c in db.rows("SELECT * FROM companies WHERE ticker IS NOT NULL AND ticker!=''"):
        try:
            sid = "CO:" + c["id"]
            have = db.one("SELECT COUNT(*) k FROM indicators WHERE series=?", (sid,))["k"]
            pts = markets.stooq_history(c["ticker"], 3650 if have < 100 else 14)
            if pts:
                n += markets._store(sid, pts)
                with db.session() as con:
                    markets._meta(con, sid, c["name"], "", "company", "Stooq", f"https://stooq.com/q/?s={c['ticker']}", db.now())
        except Exception as e:  # noqa: BLE001
            log.warning("quote %s: %s", c["id"], e)
    return n


# ---------------- SEC EDGAR ----------------
def _edgar(url: str, **kw):
    return http.get(url, headers={"Accept-Encoding": "gzip"}, **kw)


def cik_map() -> dict[str, dict]:
    """ticker -> {cik, title}, from the key-free SEC file."""
    d = _edgar("https://www.sec.gov/files/company_tickers.json").json()
    return {v["ticker"].upper(): dict(cik=int(v["cik_str"]), title=v["title"]) for v in d.values()}


def edgar_filings() -> int:
    load_companies()
    cm = cik_map()
    n = 0
    for c in db.rows("SELECT * FROM companies"):
        data = json.loads(c["data"])
        t = (data.get("sec_ticker") or "").upper()
        if t not in cm:
            continue
        cik = cm[t]["cik"]
        sub = _edgar(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
        rec = sub["filings"]["recent"]
        with db.session() as con:
            for i, form in enumerate(rec["form"][:60]):
                if form not in ("8-K", "10-K", "10-Q", "SC 13D", "SC 13G", "DEF 14A", "20-F", "6-K"):
                    continue
                acc = rec["accessionNumber"][i]
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{rec['primaryDocument'][i]}"
                n += con.execute("INSERT OR IGNORE INTO company_facts(company_id,kind,ts,label,value,url,payload) VALUES(?,?,?,?,?,?,?)",
                                 (c["id"], "filing", rec["filingDate"][i], f"{form} {rec.get('primaryDocDescription', [''] * 99)[i]}".strip(),
                                  None, url, json.dumps(dict(form=form, accession=acc)))).rowcount
    return n


MANAGERS = {  # name -> CIK (checked at runtime against the name returned by SEC)
    "BlackRock": 1364742, "Vanguard Group": 102909, "State Street": 93751, "Berkshire Hathaway": 1067983,
    "FMR (Fidelity)": 315066, "Geode Capital": 1214717, "T. Rowe Price": 1113169, "Morgan Stanley": 895421,
    "JPMorgan Chase": 19617, "Goldman Sachs": 886982, "Northern Trust": 73124, "Wellington Management": 902219,
    "Norges Bank": 1374170, "Capital Research / Capital World": 1422849,
}


def _norm_issuer(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return " ".join(w for w in s.split() if w not in {"inc", "corp", "corporation", "co", "ltd", "plc", "com", "the", "holdings",
                                                          "class", "a", "cl", "new", "sa", "nv", "group", "adr", "sponsored"})


def parse_13f_infotable(xml_text: str) -> list[dict]:
    xml_text = re.sub(r'xmlns(:\w+)?="[^"]+"', "", xml_text)
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter("infoTable"):
        g = lambda tag: (it.findtext(tag) or "").strip()  # noqa: E731
        try:
            out.append(dict(issuer=g("nameOfIssuer"), cls=g("titleOfClass"), cusip=g("cusip"), value=float(g("value") or 0),
                            shares=float(it.findtext("shrsOrPrnAmt/sshPrnamt") or 0)))
        except ValueError:
            continue
    return out


def edgar_13f() -> int:
    load_companies()
    cm = cik_map()
    tracked = {}
    for c in db.rows("SELECT * FROM companies"):
        data = json.loads(c["data"])
        t = (data.get("sec_ticker") or "").upper()
        if t in cm:
            tracked[_norm_issuer(cm[t]["title"])] = c["id"]
    n = 0
    for mname, cik in MANAGERS.items():
        try:
            sub = _edgar(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
            if mname.split()[0].lower() not in sub.get("name", "").lower() and mname.split()[0].lower() not in " ".join(
                    x.get("name", "") for x in sub.get("formerNames", [])).lower():
                log.warning("13F manager %s: CIK %s resolves to %r — skipped, fix MANAGERS", mname, cik, sub.get("name"))
                continue
            rec = sub["filings"]["recent"]
            idx = next((i for i, f in enumerate(rec["form"]) if f == "13F-HR"), None)
            if idx is None:
                continue
            acc = rec["accessionNumber"][idx].replace("-", "")
            base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
            items = _edgar(base + "index.json").json()["directory"]["item"]
            xmls = [i["name"] for i in items if i["name"].lower().endswith(".xml") and "primary_doc" not in i["name"].lower()]
            holdings: dict[str, list[float]] = {}
            for fn in xmls:
                body = _edgar(base + fn, timeout=120).text
                if "infoTable" not in body:
                    continue
                for h in parse_13f_infotable(body):
                    cid = tracked.get(_norm_issuer(h["issuer"]))
                    if cid:
                        a = holdings.setdefault(cid, [0.0, 0.0])
                        a[0] += h["value"]
                        a[1] += h["shares"]
                break
            period = rec["reportDate"][idx]
            filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR"
            with db.session() as con:
                node(con, f"org:{slug(mname)}", mname, "org", "US")
                for cid, (val, sh) in holdings.items():
                    con.execute("INSERT OR REPLACE INTO company_facts(company_id,kind,ts,label,value,url,payload) VALUES(?,?,?,?,?,?,?)",
                                (cid, "holder", period, mname, val, filing_url, json.dumps(dict(shares=sh, period=period))))
                    edge(con, f"org:{slug(mname)}", f"co:{cid}", "owns", filing_url, max(min(val / 5e10, 1.0), 0.1), f"13F {period}")
                    n += 1
        except Exception as e:  # noqa: BLE001
            log.warning("13F %s: %s", mname, e)
    return n


# ---------------- Lobbying ----------------
def lda() -> int:
    n = 0
    hdr = {"Authorization": f"Token {config.key('LDA_API_KEY')}"} if config.key("LDA_API_KEY") else {}
    year = time.gmtime().tm_year
    for c in db.rows("SELECT * FROM companies WHERE country='US'"):
        data = json.loads(c["data"])
        nm = data.get("lda_name") or c["name"]
        tot: dict[int, float] = {}
        issues: dict[str, int] = {}
        for y in (year - 2, year - 1, year):
            r = http.get("https://lda.senate.gov/api/v1/filings/", params={"client_name": nm, "filing_year": y, "page_size": 100}, headers=hdr)
            if r.status_code in (401, 403):
                raise RuntimeError("LDA API refused the request: set LDA_API_KEY (see .env.example)")
            if r.status_code != 200:
                continue
            for f in r.json().get("results", []):
                if (f.get("client") or {}).get("name", "").lower().find(nm.lower().split()[0]) < 0:
                    continue
                amt = float(f.get("expenses") or f.get("income") or 0)
                tot[y] = tot.get(y, 0) + amt
                for a in f.get("lobbying_activities") or []:
                    k = a.get("general_issue_code_display")
                    if k:
                        issues[k] = issues.get(k, 0) + 1
        with db.session() as con:
            for y, v in tot.items():
                n += con.execute("INSERT OR REPLACE INTO company_facts(company_id,kind,ts,label,value,url,payload) VALUES(?,?,?,?,?,?,?)",
                                 (c["id"], "lobbying_us", f"{y}-12-31", f"US lobbying {y}", v,
                                  f"https://lda.senate.gov/filings/public/filing/search/?client_name={nm}", json.dumps(dict(issues=issues)))).rowcount
    return n


def import_eu_register() -> int:
    """Imports a user-downloaded export of the EU Transparency Register (CSV) placed in data/inbox/.
    Columns are matched loosely (name / cost). The official download page is documented in docs/SOURCES_DATA.md."""
    inbox = config.DATA_DIR / "inbox"
    files = list(inbox.glob("*transparency*.csv")) if inbox.exists() else []
    n = 0
    names = {c["id"]: c["name"].lower() for c in db.rows("SELECT id,name FROM companies")}
    for f in files:
        rd = csv.DictReader(io.StringIO(f.read_text(encoding="utf-8-sig", errors="ignore")))
        for row in rd:
            low = {k.lower(): v for k, v in row.items() if k}
            nm = next((v for k, v in low.items() if "name" in k and v), "")
            cost = next((v for k, v in low.items() if ("cost" in k or "expenditure" in k) and v), "")
            rid = next((v for k, v in low.items() if "identification" in k or "register" in k and "id" in k), "")
            for cid, cname in names.items():
                if cname.split()[0] in nm.lower() and len(nm) < len(cname) + 25:
                    m = re.search(r"[\d.,]+", cost.replace(" ", ""))
                    with db.session() as con:
                        n += con.execute("INSERT OR REPLACE INTO company_facts(company_id,kind,ts,label,value,url,payload) VALUES(?,?,?,?,?,?,?)",
                                         (cid, "lobbying_eu", time.strftime("%Y-%m-%d"), f"EU register: {nm}",
                                          float(m.group(0).replace(",", "")) if m else None,
                                          "https://transparency-register.europa.eu/search-register-or-update_en", json.dumps(row))).rowcount
    return n


FINE_WORDS = re.compile(r"\b(fine[sd]?|fining|penalt|settle|antitrust|cartel|abuse of dominant|amende|multa|sanction|condamn|breach|investigation)\w*", re.I)


def regulators() -> int:
    cfg = load_yaml("corpos.yaml") or {}
    comps = db.rows("SELECT id,name FROM companies")
    n = 0
    for feed in cfg.get("regulator_feeds", []):
        try:
            r = http.get(feed["url"])
            r.raise_for_status()
            for e in feedparser.parse(r.content).entries[:100]:
                title = text.clean_html(e.get("title"))
                body = f"{title} {text.clean_html(e.get('summary'))}"
                if not FINE_WORDS.search(body):
                    continue
                for c in comps:
                    if re.search(rf"(?<!\w){re.escape(c['name'].split(' (')[0])}(?!\w)", body, re.I):
                        t = e.get("published_parsed")
                        with db.session() as con:
                            n += con.execute("INSERT OR IGNORE INTO company_facts(company_id,kind,ts,label,value,url,payload) VALUES(?,?,?,?,?,?,?)",
                                             (c["id"], "regulatory", time.strftime("%Y-%m-%d", t) if t else db.now()[:10], title, None, e.get("link"),
                                              json.dumps(dict(regulator=feed["name"])))).rowcount
        except Exception as ex:  # noqa: BLE001
            log.warning("regulator feed %s: %s", feed.get("name"), ex)
    return n


def wikidata_people() -> int:
    from . import wikidata
    load_companies()
    n = 0
    for c in db.rows("SELECT * FROM companies"):
        data = json.loads(c["data"])
        qid = data.get("qid")
        if not qid:
            hit = wikidata.search_entity(c["name"])
            qid = hit["id"] if hit else None
            if qid:
                data["qid"] = qid
                data["qid_auto_match"] = True
                db.execute("UPDATE companies SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), c["id"]))
        if qid:
            try:
                n += wikidata.company_people(c["id"], qid)
            except Exception as e:  # noqa: BLE001
                log.warning("wikidata people %s: %s", c["id"], e)
    return n


register(Collector("company_quotes", "corpos", 60, company_quotes))
register(Collector("edgar_filings", "corpos", 720, edgar_filings))
register(Collector("edgar_13f", "corpos", 10080, edgar_13f))
register(Collector("lobbying_us", "corpos", 10080, lda))
register(Collector("lobbying_eu", "corpos", 10080, import_eu_register))
register(Collector("regulators", "corpos", 360, regulators))
register(Collector("wikidata_people", "corpos", 10080, wikidata_people))
