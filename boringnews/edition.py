"""One day's edition, and the only module that knows its shape.

The pipeline builds an Edition and saves it. From there it has three forms:
the database (a local cache), the edition file (archive/YYYY-MM-DD.json, the
project's storage) and the page data (edition.json, which web/core.js and
web/app.js read). All three are written and read here.

An edition file holds everything needed to check or reproduce an edition:
  - the rubric (version, weights, thresholds) and hashes of the style guide
    and banned-word list in force that day
  - every source with its lean, weight and role
  - every article read in the edition window
  - how articles were grouped into stories, each story's id, score parts and
    fact-check log, and which writer produced it

Edition files are committed to the repo and published on the site (/archive/).
`restore` rebuilds the database from them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import config, db, rubric
from .db import Article, Story
from .sources import Source
from .topics import LEGACY, TOPIC_DESCRIPTIONS, TOPICS

FORMAT = 2  # 2 added story ids, which RSS guids and #story-N links depend on.


class NoEdition(LookupError):
    """The database has no edition, or none for the date asked for."""


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def _rubric() -> dict:
    return {
        "version": rubric.VERSION, "weights": rubric.WEIGHTS, "thresholds": rubric.THRESHOLDS,
        "coverage_cap": rubric.COVERAGE_CAP, "min_outlets": rubric.MIN_OUTLETS, "spotlight": rubric.SPOTLIGHT,
    }


def _sources(sources: dict[str, Source]) -> dict:
    return {sid: s.record() for sid, s in sources.items()}


@dataclass
class Edition:
    date: str
    stories: list[Story]
    sources: dict[str, Source]
    markets: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, conn, sources: dict[str, Source], date: str | None = None) -> "Edition":
        """The edition for `date`, or the latest one."""
        dates = db.editions(conn)
        if not dates:
            raise NoEdition("No editions yet. Run: python -m boringnews.pipeline run")
        date = date or dates[0]
        if date not in dates:
            raise NoEdition(f"No edition for {date}")
        return cls(date, db.load_edition(conn, date), sources, db.load_extra(conn, date, "markets", []))

    def save(self, conn) -> None:
        """Store it, replacing any earlier run for the same date. Sets story ids."""
        db.replace_edition(conn, self.date, self.stories)
        db.save_extra(conn, self.date, "markets", self.markets)

    def page_data(self, base_url: str, sample: bool = False, data_url: str | None = None,
                  corrections: list[dict] | None = None) -> dict:
        """What the reader page and the feed function work from."""
        return {
            "edition": self.date,
            "sample": sample,
            "base_url": base_url,
            "repo_url": config.REPO_URL,
            "data_url": data_url,
            "corrections": corrections or [],
            "markets": self.markets,
            "rubric": _rubric(),
            "topics": TOPICS,
            "topic_descriptions": TOPIC_DESCRIPTIONS,
            "topic_aliases": LEGACY,
            "sources": _sources(self.sources),
            "stories": [
                {
                    "id": s.id,
                    "headline": s.headline,
                    "bullets": s.bullets,
                    "whats_next": s.whats_next,
                    "topic": s.topic,
                    "checks": s.checks,
                    "day": s.day,
                    "articles": [{"source_id": a.source_id, "title": a.title, "url": a.url} for a in s.articles],
                }
                for s in self.stories
            ],
        }

    def file_data(self, articles: list[Article], clusters: list[list[Article]], model: str) -> dict:
        """The public record of the run. Needs saved stories, for their ids."""
        return {
            "format": FORMAT,
            "edition": self.date,
            "generated_at": db.now_iso(),
            "rubric": _rubric(),
            "editorial": {
                "style_guide_sha256": _sha(config.STYLE_GUIDE_PATH),
                "banned_words_sha256": _sha(config.BANNED_WORDS_PATH),
                "model": model,
            },
            "sources": _sources(self.sources),
            "articles": [{"source_id": a.source_id, "url": a.url, "title": a.title, "summary": a.summary,
                          "published_at": a.published_at} for a in articles],
            "clusters": [[a.url for a in g] for g in clusters],
            "markets": self.markets,
            "stories": [
                {
                    "id": s.id,
                    "headline": s.headline, "bullets": s.bullets, "whats_next": s.whats_next,
                    "topic": s.topic, "region": s.region, "written_by": s.written_by,
                    "checks": s.checks, "thread_id": s.thread_id, "day": s.day,
                    "articles": [a.url for a in s.articles],
                    "score": rubric.score(self.sources[a.source_id] for a in s.articles
                                          if a.source_id in self.sources).to_dict(),
                }
                for s in self.stories
            ],
        }

    def write_file(self, directory: Path, articles: list[Article], clusters: list[list[Article]], model: str) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.date}.json"
        path.write_text(json.dumps(self.file_data(articles, clusters, model), ensure_ascii=False, indent=1))
        return path


def _restore_file(conn, data: dict) -> None:
    if data.get("format", 1) > FORMAT:
        raise ValueError(f"edition {data['edition']} has format {data['format']}; this code reads up to {FORMAT}")
    by_url = {a["url"]: a for a in data["articles"]}
    db.upsert_articles(conn, [Article(a["source_id"], a["url"], a["title"], a["summary"], a["published_at"])
                              for a in data["articles"]])
    ids = db.article_ids(conn, list(by_url))
    stories = [
        Story(
            edition_date=data["edition"],
            headline=s["headline"],
            bullets=s["bullets"],
            whats_next=s["whats_next"],
            topic=s["topic"],
            region=s["region"],
            written_by=s["written_by"],
            articles=[Article(by_url[u]["source_id"], u, by_url[u]["title"], by_url[u]["summary"],
                              by_url[u]["published_at"], id=ids[u]) for u in s["articles"] if u in by_url],
            id=s.get("id"),
            checks=s.get("checks", {}),
            thread_id=s.get("thread_id"),
            day=s.get("day", 1),
        )
        for s in data["stories"]
    ]
    db.replace_edition(conn, data["edition"], stories)
    db.save_extra(conn, data["edition"], "markets", data.get("markets", []))


def restore(directory: Path, db_path: Path) -> int:
    """Rebuild the database from edition files, oldest first. Returns editions restored."""
    conn = db.connect(db_path)
    files = sorted(Path(directory).glob("*.json"))
    for f in files:
        _restore_file(conn, json.loads(f.read_text()))
    conn.close()
    return len(files)
