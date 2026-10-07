"""Non-editorial text utilities: normalisation, language detection, entity extraction, sentences."""
import hashlib
import html
import re
import unicodedata

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean_html(s: str | None) -> str:
    if not s:
        return ""
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", s))).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _WS.sub(" ", re.sub(r"[^\w\s]", " ", s)).strip()


def title_hash(title: str) -> str:
    return hashlib.sha1(norm(title).encode()).hexdigest()[:16]


def detect_lang(text: str, fallback: str | None = None) -> str | None:
    if len(text or "") < 20:
        return fallback
    try:
        from langdetect import DetectorFactory, detect
        DetectorFactory.seed = 0
        code = detect(text)
        return {"zh-cn": "zh", "zh-tw": "zh"}.get(code, code)
    except Exception:  # noqa: BLE001
        return fallback


# Generic entity extraction: runs of capitalised words (Latin scripts) + watchlist gazetteer.
_CAP = re.compile(r"\b([A-ZÀ-ÖØ-Ý][\wÀ-ÿ'’.-]+(?:\s+(?:de|of|von|van|del|la|le|da|di|du|al|el)?\s*[A-ZÀ-ÖØ-Ý][\wÀ-ÿ'’.-]+)*)")
_STOP = {"The", "A", "An", "Le", "La", "Les", "El", "Los", "Las", "Der", "Die", "Das", "Il", "In", "On", "At", "After",
         "Before", "How", "Why", "What", "When", "Who", "New", "Live", "Video", "Photos", "Watch", "Update", "Breaking",
         "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March",
         "April", "May", "June", "July", "August", "September", "October", "November", "December"}


def extract_entities(text: str, gazetteer: list[str] | None = None) -> list[str]:
    found: dict[str, int] = {}
    for m in _CAP.finditer(text or ""):
        e = m.group(1).strip(" .-")
        if e in _STOP or len(e) < 3:
            continue
        if m.start() == 0 and " " not in e:  # lone sentence-initial word: not reliable
            continue
        found[e] = found.get(e, 0) + 1
    low = norm(text or "")
    for g in gazetteer or []:
        if g and re.search(rf"(?<!\w){re.escape(norm(g))}(?!\w)", low):
            found[g] = found.get(g, 0) + 3
    return [k for k, _ in sorted(found.items(), key=lambda kv: -kv[1])][:12]


_SENT = re.compile(r"(?<=[.!?。！？])\s+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text or "") if s.strip()]


STOPWORDS = set("""a an the of to in on for and or but is are was were be been it its this that with as by at from
le la les un une des du de et en dans pour sur par est sont au aux ce ces qui que
el los las una unos unas del y en para por con es son al se lo que
der die das und ein eine von zu mit auf für ist
il lo gli i e di che per con su
o os as um uma de do da em para com que
""".split())


def tokens(text: str) -> list[str]:
    return [t for t in norm(text).split() if len(t) > 2 and t not in STOPWORDS and not t.isdigit()]
