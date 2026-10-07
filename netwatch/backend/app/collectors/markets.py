"""Vital signs: quotes (Stooq CSV), FRED, World Bank, ECB, Eurostat. Each indicator keeps its source + update time."""
import csv
import io
import logging
import time

from .. import config, db, http
from .base import Collector, Skip, register

log = logging.getLogger("netwatch.markets")

# series id -> (label, unit, group, stooq symbol, source page)
QUOTES = {
    "SPX": ("S&P 500", "pts", "markets", "^spx"), "NDX": ("Nasdaq 100", "pts", "markets", "^ndx"),
    "DJI": ("Dow Jones", "pts", "markets", "^dji"), "CAC": ("CAC 40", "pts", "markets", "^cac"),
    "DAX": ("DAX", "pts", "markets", "^dax"), "IBEX": ("IBEX 35", "pts", "markets", "^ibex"),
    "FTSE": ("FTSE 100", "pts", "markets", "^ukx"), "N225": ("Nikkei 225", "pts", "markets", "^nkx"),
    "HSI": ("Hang Seng", "pts", "markets", "^hsi"), "SHC": ("Shanghai Comp.", "pts", "markets", "^shc"),
    "VIX": ("VIX", "pts", "markets", "^vix"),
    "GOLD": ("Gold", "USD/oz", "commodities", "xauusd"), "BRENT": ("Brent", "USD/bbl", "commodities", "lco.f"),
    "WTI": ("WTI", "USD/bbl", "commodities", "cl.f"), "TTF": ("Gas TTF", "EUR/MWh", "commodities", "ttf.f"),
    "BTC": ("Bitcoin", "USD", "crypto", "btcusd"),
    "EURUSD": ("EUR/USD", "", "fx", "eurusd"), "USDCNY": ("USD/CNY", "", "fx", "usdcny"),
    "USDJPY": ("USD/JPY", "", "fx", "usdjpy"), "GBPUSD": ("GBP/USD", "", "fx", "gbpusd"),
}
# FRED series -> (label, unit, group)
FRED = {
    "FEDFUNDS": ("Fed funds rate", "%", "rates"), "DGS10": ("US 10y yield", "%", "rates"),
    "CPIAUCSL": ("US CPI index", "idx", "macro"), "UNRATE": ("US unemployment", "%", "macro"),
    "GFDEGDQ188S": ("US federal debt / GDP", "%", "macro"), "T10Y2Y": ("US 10y-2y spread", "pp", "rates"),
}


def _meta(con, series, label, unit, group, source, url, updated):
    con.execute("""INSERT INTO indicator_meta(series,label,unit,group_name,source,source_url,updated) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(series) DO UPDATE SET label=excluded.label,unit=excluded.unit,group_name=excluded.group_name,
        source=excluded.source,source_url=excluded.source_url,updated=excluded.updated""",
                (series, label, unit, group, source, url, updated))


def parse_stooq_csv(body: str) -> list[tuple[str, float]]:
    out = []
    for r in csv.DictReader(io.StringIO(body)):
        try:
            out.append((r["Date"], float(r["Close"])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def stooq_history(symbol: str, days: int = 3650) -> list[tuple[str, float]]:
    d1 = time.strftime("%Y%m%d", time.gmtime(time.time() - days * 86400))
    d2 = time.strftime("%Y%m%d")
    r = http.get("https://stooq.com/q/d/l/", params={"s": symbol, "i": "d", "d1": d1, "d2": d2})
    r.raise_for_status()
    return parse_stooq_csv(r.text)


def _store(series: str, pts: list[tuple[str, float]]) -> int:
    with db.session() as con:
        con.executemany("INSERT OR REPLACE INTO indicators(series,ts,value) VALUES(?,?,?)", [(series, t, v) for t, v in pts])
    return len(pts)


def quotes() -> int:
    n = 0
    for sid, (label, unit, group, sym) in QUOTES.items():
        try:
            have = db.one("SELECT COUNT(*) c FROM indicators WHERE series=?", (sid,))["c"]
            pts = stooq_history(sym, 3650 if have < 100 else 14)
            if pts:
                n += _store(sid, pts)
                with db.session() as con:
                    _meta(con, sid, label, unit, group, "Stooq", f"https://stooq.com/q/?s={sym}", db.now())
        except Exception as e:  # noqa: BLE001
            log.warning("quote %s failed: %s", sid, e)
    return n


def fred() -> int:
    k = config.key("FRED_API_KEY")
    if not k:
        raise Skip("FRED_API_KEY not set (free key, see .env.example)")
    n = 0
    start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 11 * 365 * 86400))
    for sid, (label, unit, group) in FRED.items():
        d = http.get_json("https://api.stlouisfed.org/fred/series/observations",
                          params={"series_id": sid, "api_key": k, "file_type": "json", "observation_start": start})
        pts = [(o["date"], float(o["value"])) for o in d.get("observations", []) if o["value"] not in (".", "")]
        n += _store("FRED:" + sid, pts)
        with db.session() as con:
            _meta(con, "FRED:" + sid, label, unit, group, "FRED", f"https://fred.stlouisfed.org/series/{sid}", db.now())
    return n


# ECB data portal (SDMX CSV). key -> (label, unit, group, flow, series key)
ECB = {
    "ECB:DFR": ("ECB deposit facility rate", "%", "rates", "FM", "D.U2.EUR.4F.KR.DFR.LEV"),
    "ECB:FR10": ("France 10y yield", "%", "rates", "IRS", "M.FR.L.L40.CI.0000.EUR.N.Z"),
    "ECB:ES10": ("Spain 10y yield", "%", "rates", "IRS", "M.ES.L.L40.CI.0000.EUR.N.Z"),
    "ECB:DE10": ("Germany 10y yield", "%", "rates", "IRS", "M.DE.L.L40.CI.0000.EUR.N.Z"),
    "ECB:IT10": ("Italy 10y yield", "%", "rates", "IRS", "M.IT.L.L40.CI.0000.EUR.N.Z"),
    "ECB:HICP": ("Euro area inflation (HICP, y/y)", "%", "macro", "ICP", "M.U2.N.000000.4.ANR"),
}


def parse_ecb_csv(body: str) -> list[tuple[str, float]]:
    out = []
    for r in csv.DictReader(io.StringIO(body)):
        try:
            t = r["TIME_PERIOD"]
            out.append((t if len(t) == 10 else t + "-01", float(r["OBS_VALUE"])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def ecb() -> int:
    n = 0
    for sid, (label, unit, group, flow, key) in ECB.items():
        try:
            r = http.get(f"https://data-api.ecb.europa.eu/service/data/{flow}/{key}",
                         params={"format": "csvdata", "startPeriod": str(time.gmtime().tm_year - 11)})
            r.raise_for_status()
            n += _store(sid, parse_ecb_csv(r.text))
            with db.session() as con:
                _meta(con, sid, label, unit, group, "ECB Data Portal", f"https://data.ecb.europa.eu/data/datasets/{flow}", db.now())
        except Exception as e:  # noqa: BLE001
            log.warning("ECB %s failed: %s", sid, e)
    return n


# World Bank annual indicators for France, Spain, Germany, USA, China ...
WB = {"GC.DOD.TOTL.GD.ZS": ("Central gov. debt / GDP", "%"), "FP.CPI.TOTL.ZG": ("Inflation (CPI, annual)", "%"),
      "SL.UEM.TOTL.ZS": ("Unemployment", "%"), "NY.GDP.MKTP.KD.ZG": ("GDP growth", "%")}
WB_COUNTRIES = ["FR", "ES", "DE", "IT", "US", "CN", "GB", "JP", "BR", "IN"]


def worldbank() -> int:
    n = 0
    for ind, (label, unit) in WB.items():
        d = http.get_json(f"https://api.worldbank.org/v2/country/{';'.join(WB_COUNTRIES)}/indicator/{ind}",
                          params={"format": "json", "per_page": 1000, "date": f"{time.gmtime().tm_year - 12}:{time.gmtime().tm_year}"})
        for o in (d[1] if len(d) > 1 and d[1] else []):
            if o["value"] is None:
                continue
            sid = f"WB:{o['countryiso3code'] or o['country']['id']}:{ind}"
            _store(sid, [(o["date"] + "-01-01", float(o["value"]))])
            with db.session() as con:
                _meta(con, sid, f"{o['country']['value']} — {label}", unit, "country", "World Bank",
                      f"https://data.worldbank.org/indicator/{ind}?locations={o['country']['id']}", db.now())
            n += 1
    return n


# Eurostat dissemination API (JSON-stat): monthly unemployment rate, euro area & FR/ES/DE
def parse_jsonstat_time_series(d: dict) -> list[tuple[str, float]]:
    times = d["dimension"]["time"]["category"]["index"]
    inv = {v: k for k, v in times.items()}
    out = []
    for pos, val in d["value"].items():
        t = inv.get(int(pos))
        if t and val is not None:
            out.append((t + "-01" if len(t) == 7 else t, float(val)))
    return sorted(out)


def eurostat() -> int:
    n = 0
    for geo in ("EA20", "FR", "ES", "DE"):
        try:
            d = http.get_json("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m",
                              params={"geo": geo, "s_adj": "SA", "age": "TOTAL", "sex": "T", "unit": "PC_ACT", "format": "JSON", "lang": "EN"})
            sid = f"ESTAT:UNE:{geo}"
            n += _store(sid, parse_jsonstat_time_series(d))
            with db.session() as con:
                _meta(con, sid, f"Unemployment rate ({geo})", "%", "macro", "Eurostat une_rt_m",
                      "https://ec.europa.eu/eurostat/databrowser/view/une_rt_m", db.now())
        except Exception as e:  # noqa: BLE001
            log.warning("Eurostat %s failed: %s", geo, e)
    return n


def series_stats(series: str) -> dict:
    """Latest value, change and 10-year percentile (context, not a score)."""
    pts = db.rows("SELECT ts,value FROM indicators WHERE series=? ORDER BY ts", (series,))
    if not pts:
        return {}
    vals = [p["value"] for p in pts]
    last, prev = pts[-1], pts[-2] if len(pts) > 1 else None
    window = [p["value"] for p in pts if p["ts"] >= time.strftime("%Y-%m-%d", time.gmtime(time.time() - 10 * 366 * 86400))] or vals
    pct = 100 * sum(1 for v in window if v <= last["value"]) / len(window)
    return dict(last=last, prev=prev, change=(last["value"] - prev["value"]) if prev else None,
                change_pct=((last["value"] / prev["value"] - 1) * 100) if prev and prev["value"] else None,
                percentile_10y=round(pct, 1), n=len(pts), min=min(window), max=max(window))


register(Collector("quotes", "markets", 15, quotes))
register(Collector("fred", "markets", 720, fred, needs="FRED_API_KEY"))
register(Collector("ecb", "markets", 720, ecb))
register(Collector("worldbank", "markets", 4320, worldbank))
register(Collector("eurostat", "markets", 1440, eurostat))
