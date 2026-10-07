"""Event collectors: USGS earthquakes, GDACS disasters, GDELT 2.0 events, ACLED, ReliefWeb."""
import csv
import io
import json
import logging
import time
import zipfile
from collections import defaultdict

from .. import config, db, http
from ..countries import COUNTRIES, lookup_name
from .base import Collector, Skip, register

log = logging.getLogger("netwatch.events")


def _put(con, uid, kind, ts, country, lat, lon, mag, title, url, source, payload) -> int:
    return con.execute("""INSERT INTO events(uid,kind,ts,country,lat,lon,magnitude,title,url,source,payload)
        VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET magnitude=excluded.magnitude,payload=excluded.payload""",
                       (uid, kind, ts, country, lat, lon, mag, title, url, source, json.dumps(payload))).rowcount


def parse_usgs(data: dict) -> list[tuple]:
    out = []
    for f in data.get("features", []):
        p, g = f["properties"], f["geometry"]["coordinates"]
        if p.get("mag") is None:
            continue
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p["time"] / 1000))
        out.append((f"usgs:{f['id']}", "quake", ts, None, g[1], g[0], float(p["mag"]), p.get("place") or "earthquake",
                    p.get("url"), "USGS", {"depth_km": g[2], "tsunami": p.get("tsunami"), "alert": p.get("alert")}))
    return out


def usgs() -> int:
    d = http.get_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson")
    items = parse_usgs(d)
    with db.session() as con:
        return sum(_put(con, *i) for i in items)


def parse_gdacs(data: dict) -> list[tuple]:
    out = []
    for f in data.get("features", []):
        p, geom = f["properties"], f.get("geometry") or {}
        co = geom.get("coordinates") or [None, None]
        if geom.get("type") != "Point":
            continue
        iso = (p.get("iso3") or "")
        out.append((f"gdacs:{p.get('eventtype')}{p.get('eventid')}:{p.get('episodeid')}", "disaster",
                    (p.get("fromdate") or db.now())[:19] + "Z", None, co[1], co[0], p.get("alertscore"),
                    p.get("name") or p.get("title") or "disaster", (p.get("url") or {}).get("details"), "GDACS",
                    {"alertlevel": p.get("alertlevel"), "eventtype": p.get("eventtype"), "country": p.get("country"), "iso3": iso}))
    return out


def gdacs() -> int:
    """GDACS GeoJSON event list; falls back to the public RSS (GeoRSS) if the JSON API refuses the request."""
    try:
        d = http.get_json("https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?alertlevel=Green;Orange;Red")
        items = parse_gdacs(d)
    except Exception:  # noqa: BLE001
        items = parse_gdacs_rss(http.get("https://www.gdacs.org/xml/rss.xml").content)
    with db.session() as con:
        return sum(_put(con, *i) for i in items)


def parse_gdacs_rss(content: bytes) -> list[tuple]:
    import feedparser
    out = []
    for e in feedparser.parse(content).entries:
        w = e.get("where") or {}
        if w.get("coordinates"):
            pt = [str(w["coordinates"][1]), str(w["coordinates"][0])]  # feedparser gives GeoJSON order (lon, lat)
        else:
            pt = (e.get("georss_point") or "").split()
        if len(pt) != 2:
            continue
        lvl = e.get("gdacs_alertlevel") or ""
        uid = e.get("gdacs_eventtype", "") + str(e.get("gdacs_eventid", e.get("id", "")))
        out.append((f"gdacs:{uid}:{e.get('gdacs_episodeid', '')}", "disaster", db.now(), None, float(pt[0]), float(pt[1]),
                    None, e.get("title", "disaster"), e.get("link"), "GDACS",
                    {"alertlevel": lvl.capitalize(), "eventtype": e.get("gdacs_eventtype"), "country": e.get("gdacs_country")}))
    return out


# ---- GDELT 2.0 events (15-min export files). We aggregate by country & CAMEO root to stay light ----
CAMEO_KIND = {"14": "protest", "18": "conflict", "19": "conflict", "20": "conflict", "17": "conflict",
              "13": "tension", "16": "sanction", "05": "diplomacy", "04": "diplomacy", "03": "diplomacy"}


def parse_gdelt_export(raw: bytes) -> dict:
    """Return {(fips_country, kind): [count, goldstein_sum, sample_url]} from an export.CSV.zip body.
    GDELT 2.0 event columns used: 28 EventRootCode, 30 GoldsteinScale, 53 ActionGeo_CountryCode, 56/57 lat/lon, 60 SOURCEURL."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    agg: dict = defaultdict(lambda: [0, 0.0, ""])
    for line in z.read(z.namelist()[0]).decode("utf-8", "ignore").splitlines():
        c = line.split("\t")
        if len(c) < 61:
            continue
        kind = CAMEO_KIND.get(c[28])
        if not kind or not c[53] or not c[56]:
            continue
        a = agg[(c[53], kind)]
        a[0] += 1
        a[1] += float(c[30] or 0)
        a[2] = a[2] or c[60]
    return agg


# FIPS 10-4 -> ISO2 for the countries we track (GDELT geo codes are FIPS)
FIPS2ISO = {"FR": "FR", "SP": "ES", "GM": "DE", "IT": "IT", "PO": "PT", "UK": "GB", "EI": "IE", "NL": "NL", "BE": "BE",
            "SZ": "CH", "AU": "AT", "SW": "SE", "NO": "NO", "DA": "DK", "FI": "FI", "PL": "PL", "EZ": "CZ", "LO": "SK",
            "HU": "HU", "RO": "RO", "BU": "BG", "GR": "GR", "HR": "HR", "SI": "SI", "RI": "RS", "BK": "BA", "AL": "AL",
            "MK": "MK", "MJ": "ME", "KV": "XK", "EN": "EE", "LG": "LV", "LH": "LT", "UP": "UA", "BO": "BY", "MD": "MD",
            "RS": "RU", "TU": "TR", "IS": "IL", "WE": "PS", "GZ": "PS", "LE": "LB", "SY": "SY", "JO": "JO", "IZ": "IQ",
            "IR": "IR", "SA": "SA", "AE": "AE", "QA": "QA", "KU": "KW", "BA": "BH", "MU": "OM", "YM": "YE", "AF": "AF",
            "PK": "PK", "IN": "IN", "BG": "BD", "CE": "LK", "NP": "NP", "KZ": "KZ", "UZ": "UZ", "CH": "CN", "TW": "TW",
            "JA": "JP", "KS": "KR", "KN": "KP", "VM": "VN", "TH": "TH", "BM": "MM", "MY": "MY", "SN": "SG", "ID": "ID",
            "RP": "PH", "AS": "AU", "NZ": "NZ", "EG": "EG", "LY": "LY", "TS": "TN", "AG": "DZ", "MO": "MA", "SU": "SD",
            "OD": "SS", "ET": "ET", "ER": "ER", "SO": "SO", "KE": "KE", "UG": "UG", "TZ": "TZ", "RW": "RW", "CG": "CD",
            "CF": "CG", "CM": "CM", "CD": "TD", "NI": "NG", "GH": "GH", "IV": "CI", "SG": "SN", "ML": "ML", "UV": "BF",
            "NG": "NE", "AO": "AO", "ZA": "ZM", "ZI": "ZW", "MZ": "MZ", "SF": "ZA", "US": "US", "CA": "CA", "MX": "MX",
            "CU": "CU", "HA": "HT", "CO": "CO", "VE": "VE", "EC": "EC", "PE": "PE", "BL": "BO", "BR": "BR", "AR": "AR",
            "CI": "CL", "UY": "UY", "PA": "PY"}


def gdelt() -> int:
    """Pull the last ~4 hours of 15-minute GDELT event exports and aggregate per country/kind/hour."""
    txt = http.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt").text
    last = [l.split()[2] for l in txt.splitlines() if l.endswith("export.CSV.zip")][0]
    stamp = last.rsplit("/", 1)[-1][:14]
    base_t = time.mktime(time.strptime(stamp, "%Y%m%d%H%M%S")) - time.timezone
    total = 0
    for k in range(0, 16):  # 16 x 15 min = 4 h
        t = time.gmtime(base_t - k * 900)
        url = f"http://data.gdeltproject.org/gdeltv2/{time.strftime('%Y%m%d%H%M%S', t)}.export.CSV.zip"
        try:
            r = http.get(url, retries=1, timeout=60)
            if r.status_code != 200:
                continue
            agg = parse_gdelt_export(r.content)
        except Exception:  # noqa: BLE001
            continue
        hour = time.strftime("%Y-%m-%dT%H:00:00Z", t)
        with db.session() as con:
            for (fips, kind), (n, gold, sample) in agg.items():
                iso = FIPS2ISO.get(fips)
                c = COUNTRIES.get(iso or "")
                if not c or n < 3:
                    continue
                uid = f"gdelt:{iso}:{kind}:{hour}"
                # keep the largest slice seen for this hour (several 15-min files share an hour)
                prev = con.execute("SELECT magnitude FROM events WHERE uid=?", (uid,)).fetchone()
                mag = float(n) + (prev["magnitude"] if prev else 0)
                _put(con, uid, kind, hour, iso, c["lat"], c["lon"], mag, f"{c['name']} — {kind}",
                     sample, "GDELT", {"events": mag, "avg_goldstein": round(gold / n, 2)})
                total += 1
    return total


def acled() -> int:
    email, k = config.key("ACLED_EMAIL"), config.key("ACLED_KEY")
    if not (email and k):
        raise Skip("ACLED_EMAIL / ACLED_KEY not set (free registration, see .env.example)")
    since = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 14 * 86400))
    d = http.get_json("https://api.acleddata.com/acled/read", params={
        "key": k, "email": email, "event_date": f"{since}|{time.strftime('%Y-%m-%d')}", "event_date_where": "BETWEEN", "limit": 5000})
    n = 0
    kinds = {"Battles": "conflict", "Violence against civilians": "conflict", "Explosions/Remote violence": "conflict",
             "Protests": "protest", "Riots": "protest", "Strategic developments": "tension"}
    with db.session() as con:
        for e in d.get("data", []):
            iso = lookup_name(e.get("country"))
            n += _put(con, f"acled:{e['event_id_cnty']}", kinds.get(e["event_type"], "tension"), e["event_date"] + "T00:00:00Z",
                      iso, float(e["latitude"]), float(e["longitude"]), float(e.get("fatalities") or 0) + 1,
                      f"{e['event_type']} — {e.get('location')}, {e.get('country')}", "https://acleddata.com/data-export-tool/",
                      "ACLED", {"fatalities": e.get("fatalities"), "actors": [e.get("actor1"), e.get("actor2")]})
    return n


def reliefweb() -> int:
    app = config.key("RELIEFWEB_APPNAME")
    if not app:
        raise Skip("RELIEFWEB_APPNAME not set (free registration, see .env.example)")
    d = http.get_json("https://api.reliefweb.int/v1/disasters", params={
        "appname": app, "limit": 50, "profile": "list", "preset": "latest"})
    n = 0
    with db.session() as con:
        for it in d.get("data", []):
            f = it["fields"]
            iso = lookup_name((f.get("country") or [{}])[0].get("name")) if f.get("country") else None
            c = COUNTRIES.get(iso or "", {})
            n += _put(con, f"reliefweb:{it['id']}", "disaster", (f.get("date", {}).get("created") or db.now())[:19] + "Z", iso,
                      c.get("lat"), c.get("lon"), None, f.get("name"), f.get("url"), "ReliefWeb",
                      {"status": f.get("status"), "alertlevel": None})
    return n


register(Collector("usgs", "events", 20, usgs))
register(Collector("gdacs", "events", 30, gdacs))
register(Collector("gdelt", "events", 60, gdelt))
register(Collector("acled", "events", 360, acled, needs="ACLED_EMAIL, ACLED_KEY"))
register(Collector("reliefweb", "events", 180, reliefweb, needs="RELIEFWEB_APPNAME"))
