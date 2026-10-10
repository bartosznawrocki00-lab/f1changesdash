"""Baza SQLite: schemat, zapis bez duplikatów, śledzenie przetworzonych dokumentów."""
import hashlib
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "upgrades.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS upgrades (
    id          TEXT PRIMARY KEY,          -- hash(rok+GP+zespół+komponent) = deduplikacja
    year        INTEGER NOT NULL,
    grand_prix  TEXT NOT NULL,
    team        TEXT NOT NULL,
    component   TEXT NOT NULL,
    description TEXT,
    reason      TEXT DEFAULT '',           -- 'Primary reason for update' z dokumentu FIA
    change_detail TEXT DEFAULT '',         -- 'Geometric differences compared to previous version'
    source_url  TEXT,
    is_demo     INTEGER DEFAULT 0,
    added_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS submissions (   -- każdy zespół z dokumentu, także bez zmian
    year        INTEGER NOT NULL,
    grand_prix  TEXT NOT NULL,
    team        TEXT NOT NULL,
    n_updates   INTEGER NOT NULL,
    source_url  TEXT,
    PRIMARY KEY (year, grand_prix, team)
);
CREATE TABLE IF NOT EXISTS processed_docs (
    url          TEXT PRIMARY KEY,
    grand_prix   TEXT,
    year         INTEGER,
    n_rows       INTEGER,
    processed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init():
    with connect() as c:
        c.executescript(SCHEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(upgrades)")}
        for col in ("reason", "change_detail"):   # migracja starszych baz
            if col not in cols:
                c.execute(f"ALTER TABLE upgrades ADD COLUMN {col} TEXT DEFAULT ''")


def make_id(year, grand_prix, team, component) -> str:
    key = "|".join(str(x).strip().lower() for x in (year, grand_prix, team, component))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def upsert_upgrades(rows: list[dict]) -> int:
    """Wstawia nowe wiersze; istniejące (ten sam klucz) pomija. Zwraca liczbę nowych."""
    new = 0
    with connect() as c:
        for r in rows:
            cur = c.execute(
                "INSERT OR IGNORE INTO upgrades "
                "(id, year, grand_prix, team, component, description, reason, change_detail, source_url, is_demo) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    make_id(r["year"], r["grand_prix"], r["team"], r["component"]),
                    int(r["year"]), r["grand_prix"], r["team"].strip(), r["component"].strip(),
                    r.get("description", ""), r.get("reason", ""), r.get("change_detail", ""),
                    r.get("source_url", ""), int(r.get("is_demo", 0)),
                ),
            )
            new += cur.rowcount
    return new


def is_processed(url: str) -> bool:
    with connect() as c:
        return c.execute("SELECT 1 FROM processed_docs WHERE url=?", (url,)).fetchone() is not None


def mark_processed(url, grand_prix, year, n_rows):
    with connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO processed_docs (url, grand_prix, year, n_rows) VALUES (?,?,?,?)",
            (url, grand_prix, year, n_rows),
        )


def upsert_submission(year, grand_prix, team, n_updates, source_url=""):
    with connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO submissions (year, grand_prix, team, n_updates, source_url) "
            "VALUES (?,?,?,?,?)", (int(year), grand_prix, team, int(n_updates), source_url))
