"""SQLite storage. Scores are not stored: they are computed from each story's
sources when read, so a rubric change or a reader's source exclusions apply
to every edition."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .topics import normalize

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY,
    source_id    TEXT NOT NULL,
    url          TEXT NOT NULL UNIQUE,
    title        TEXT NOT NULL,
    summary      TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);

CREATE TABLE IF NOT EXISTS stories (
    id           INTEGER PRIMARY KEY,
    edition_date TEXT NOT NULL,
    headline     TEXT NOT NULL,
    bullets      TEXT NOT NULL,          -- JSON list of strings
    whats_next   TEXT,
    topic        TEXT NOT NULL,
    region       TEXT NOT NULL,
    written_by   TEXT NOT NULL,          -- model id, 'mock', or 'fallback'
    created_at   TEXT NOT NULL,
    checks       TEXT NOT NULL DEFAULT '{}',  -- JSON: fact-check method and anything dropped
    thread_id    TEXT,                        -- same id for a story followed across days
    day          INTEGER NOT NULL DEFAULT 1   -- which day of that thread this is
);
CREATE INDEX IF NOT EXISTS idx_stories_edition ON stories(edition_date);

-- Other per-edition data, such as the market ticker. JSON per key.
CREATE TABLE IF NOT EXISTS extras (
    edition_date TEXT NOT NULL,
    key          TEXT NOT NULL,
    data         TEXT NOT NULL,
    PRIMARY KEY (edition_date, key)
);

CREATE TABLE IF NOT EXISTS story_articles (
    story_id   INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id),
    PRIMARY KEY (story_id, article_id)
);
"""


@dataclass
class Article:
    source_id: str
    url: str
    title: str
    summary: str
    published_at: str  # ISO 8601, UTC
    id: int | None = None

    @property
    def published(self) -> datetime:
        return datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))


# Columns added after the first schema; older databases get them on connect.
MIGRATIONS = {
    "checks": "ALTER TABLE stories ADD COLUMN checks TEXT NOT NULL DEFAULT '{}'",
    "thread_id": "ALTER TABLE stories ADD COLUMN thread_id TEXT",
    "day": "ALTER TABLE stories ADD COLUMN day INTEGER NOT NULL DEFAULT 1",
}


@dataclass
class Story:
    edition_date: str
    headline: str
    bullets: list[str]
    whats_next: str | None
    topic: str
    region: str
    written_by: str
    articles: list[Article] = field(default_factory=list)
    id: int | None = None
    checks: dict = field(default_factory=dict)
    thread_id: str | None = None
    day: int = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(stories)")}
    for col, sql in MIGRATIONS.items():
        if col not in have:
            conn.execute(sql)
    conn.commit()
    return conn


def upsert_articles(conn: sqlite3.Connection, articles: list[Article]) -> int:
    """Insert new articles, ignore ones already stored (by URL). Returns count inserted."""
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO articles (source_id, url, title, summary, published_at, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(a.source_id, a.url, a.title, a.summary, a.published_at, now_iso()) for a in articles],
    )
    conn.commit()
    return conn.total_changes - before


def articles_between(conn: sqlite3.Connection, start: str, end: str) -> list[Article]:
    rows = conn.execute(
        "SELECT * FROM articles WHERE published_at >= ? AND published_at <= ? ORDER BY published_at",
        (start, end),
    ).fetchall()
    return [_article(r) for r in rows]


def replace_edition(conn: sqlite3.Connection, edition_date: str, stories: list[Story]) -> None:
    """Write an edition, replacing any earlier run for the same date (re-runs are safe)."""
    with conn:
        conn.execute("DELETE FROM stories WHERE edition_date = ?", (edition_date,))
        for s in stories:
            cur = conn.execute(
                "INSERT INTO stories (edition_date, headline, bullets, whats_next, topic, region, written_by, "
                "created_at, checks, thread_id, day) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s.edition_date, s.headline, json.dumps(s.bullets), s.whats_next, s.topic, s.region,
                 s.written_by, now_iso(), json.dumps(s.checks), s.thread_id, s.day),
            )
            s.id = cur.lastrowid
            conn.executemany(
                "INSERT INTO story_articles (story_id, article_id) VALUES (?, ?)",
                [(s.id, a.id) for a in s.articles],
            )


def save_extra(conn: sqlite3.Connection, edition_date: str, key: str, value) -> None:
    with conn:
        conn.execute("INSERT OR REPLACE INTO extras (edition_date, key, data) VALUES (?, ?, ?)",
                     (edition_date, key, json.dumps(value)))


def load_extra(conn: sqlite3.Connection, edition_date: str, key: str, default=None):
    row = conn.execute("SELECT data FROM extras WHERE edition_date = ? AND key = ?", (edition_date, key)).fetchone()
    return json.loads(row[0]) if row else default


def editions(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT edition_date FROM stories ORDER BY edition_date DESC").fetchall()
    return [r[0] for r in rows]


def load_edition(conn: sqlite3.Connection, edition_date: str) -> list[Story]:
    rows = conn.execute("SELECT * FROM stories WHERE edition_date = ? ORDER BY id", (edition_date,)).fetchall()
    stories = []
    for r in rows:
        arts = conn.execute(
            "SELECT a.* FROM articles a JOIN story_articles sa ON sa.article_id = a.id "
            "WHERE sa.story_id = ? ORDER BY a.published_at",
            (r["id"],),
        ).fetchall()
        stories.append(
            Story(
                id=r["id"],
                edition_date=r["edition_date"],
                headline=r["headline"],
                bullets=json.loads(r["bullets"]),
                whats_next=r["whats_next"],
                topic=normalize(r["topic"]) or r["topic"],
                region=r["region"],
                written_by=r["written_by"],
                articles=[_article(a) for a in arts],
                checks=json.loads(r["checks"] or "{}"),
                thread_id=r["thread_id"],
                day=r["day"] or 1,
            )
        )
    return stories


def _article(r: sqlite3.Row) -> Article:
    return Article(
        id=r["id"],
        source_id=r["source_id"],
        url=r["url"],
        title=r["title"],
        summary=r["summary"],
        published_at=r["published_at"],
    )
