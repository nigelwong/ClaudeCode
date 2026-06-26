import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _bootstrap(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_PATH.read_text())


@contextmanager
def get_connection(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _bootstrap(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()
