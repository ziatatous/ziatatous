"""Central configuration, read from environment / .env (no key lives in code)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT  # project root (netwatch/)
load_dotenv(BASE / ".env")

DATA_DIR = Path(os.getenv("NETWATCH_DATA_DIR", BASE / "data"))
DB_PATH = Path(os.getenv("NETWATCH_DB", DATA_DIR / "netwatch.db"))
FRONTEND_DIST = BASE / "frontend" / "dist"
CONTACT = os.getenv("NETWATCH_CONTACT", "netwatch-local@example.com")
USER_AGENT = f"NETWATCH/0.1 (personal local reader; {CONTACT})"
HOST = os.getenv("NETWATCH_HOST", "127.0.0.1")
PORT = int(os.getenv("NETWATCH_PORT", "8000"))
RETENTION_FULLTEXT_DAYS = int(os.getenv("NETWATCH_RETENTION_FULLTEXT_DAYS", "30"))
RETENTION_META_DAYS = int(os.getenv("NETWATCH_RETENTION_META_DAYS", "365"))
CLUSTER_MODE = os.getenv("NETWATCH_CLUSTER_MODE", "tfidf")


def key(name: str) -> str:
    return os.getenv(name, "").strip()
