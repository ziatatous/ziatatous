"""RSF World Press Freedom Index: tries the public CSV, falls back to a file in data/inbox/ (rsf*.csv).
Columns accepted (case-insensitive): ISO / ISO2 / iso_code, Score / 'Score N', Rank / 'Rank N'."""
import csv
import io
import time

from .. import config, db, http
from .base import Collector, register


def parse(body: str, year: int) -> int:
    rd = csv.DictReader(io.StringIO(body), delimiter=";" if body.split("\n", 1)[0].count(";") > 2 else ",")
    n = 0
    with db.session() as con:
        for row in rd:
            low = {(k or "").lower().strip(): v for k, v in row.items()}
            iso = (low.get("iso") or low.get("iso2") or low.get("iso_code") or "").upper()[:2]
            score = next((v for k, v in low.items() if k.startswith("score") and v), None)
            rank = next((v for k, v in low.items() if k.startswith("rank") and v), None)
            if len(iso) != 2:
                continue
            for suffix, val in (("score", score), ("rank", rank)):
                if val:
                    try:
                        con.execute("INSERT OR REPLACE INTO indicators(series,ts,value) VALUES(?,?,?)",
                                    (f"RSF:{iso}:{suffix}", f"{year}-01-01", float(val.replace(",", "."))))
                        n += 1
                    except ValueError:
                        pass
        con.execute("""INSERT OR REPLACE INTO indicator_meta(series,label,unit,group_name,source,source_url,updated)
            VALUES('RSF','RSF World Press Freedom Index','','press','RSF','https://rsf.org/en/index',?)""", (db.now(),))
    return n


def collect() -> int:
    year = time.gmtime().tm_year
    inbox = config.DATA_DIR / "inbox"
    for f in sorted(inbox.glob("rsf*.csv")) if inbox.exists() else []:
        return parse(f.read_text(encoding="utf-8-sig", errors="ignore"), year)
    for y in (year, year - 1):
        r = http.get(f"https://rsf.org/sites/default/files/index_{y}.csv", retries=1)
        if r.status_code == 200 and "ISO" in r.text[:500].upper():
            return parse(r.text, y)
    raise RuntimeError("RSF CSV not reachable: download it from rsf.org/en/index and drop it as data/inbox/rsf.csv")


register(Collector("rsf", "sources", 10080, collect))
