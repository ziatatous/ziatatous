"""On-demand translation, always flagged 'machine translation' by the API. Argos (local) by default, DeepL optional."""
import logging

from .. import config, http

log = logging.getLogger("netwatch.translate")


def _argos(text: str, src: str, dst: str) -> str:
    import argostranslate.translate as at  # optional dependency
    return at.translate(text, src, dst)


def _deepl(text: str, src: str, dst: str) -> str:
    k = config.key("DEEPL_API_KEY")
    base = "https://api-free.deepl.com" if k.endswith(":fx") else "https://api.deepl.com"
    import httpx
    r = httpx.post(f"{base}/v2/translate", headers={"Authorization": f"DeepL-Auth-Key {k}"},
                   data={"text": text, "source_lang": src.upper(), "target_lang": dst.upper()}, timeout=30)
    r.raise_for_status()
    return r.json()["translations"][0]["text"]


def available() -> dict:
    out = dict(deepl=bool(config.key("DEEPL_API_KEY")), argos=False)
    try:
        import argostranslate.translate  # noqa: F401
        out["argos"] = True
    except Exception:  # noqa: BLE001
        pass
    return out


def translate(text: str, src: str, dst: str) -> dict:
    if not text or src == dst:
        return dict(text=text, engine="none", machine=False)
    av = available()
    errs = []
    for eng, fn in (("deepl", _deepl), ("argos", _argos)):
        if not av[eng]:
            continue
        try:
            return dict(text=fn(text, src, dst), engine=eng, machine=True)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{eng}: {e}")
    raise RuntimeError("no translation engine available (" + "; ".join(errs or ["install argostranslate or set DEEPL_API_KEY"]) + ")")
