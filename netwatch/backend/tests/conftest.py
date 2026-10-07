import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_tmp = tempfile.mkdtemp(prefix="netwatch-test-")
os.environ["NETWATCH_DB"] = os.path.join(_tmp, "test.db")
os.environ["NETWATCH_DATA_DIR"] = _tmp

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    from app import config, db
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(str(config.DB_PATH) + suffix)
        except FileNotFoundError:
            pass
    db.init()
    yield
