def load_all() -> None:
    """Import every collector module so they self-register."""
    from . import rss, events, markets, official, agenda, sources_loader, wikidata, corpos, rsf  # noqa: F401
