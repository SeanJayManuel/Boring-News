"""Daily edition files: everything needed to check or reproduce an edition.

Each run writes archive/YYYY-MM-DD.json with:
  - the rubric (version, weights, thresholds) and hashes of the style guide
    and banned-word list in force that day
  - every source with its lean, weight and role
  - every article read in the edition window
  - how articles were grouped into stories, each story's score parts, the
    fact-check log, and which writer produced it

These files are the project's storage: they are committed to the repo and
published on the site (/archive/). The SQLite database is a local cache that
can be rebuilt from them:

    python -m boringnews.archive restore            # archive/ -> data/boringnews.db
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from . import config, rubric
from .db import Article, Story, connect, now_iso, replace_edition, upsert_articles
from .sources import Source

FORMAT = 1


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def build(edition_date: str, sources: dict[str, Source], articles: list[Article],
          clusters: list[list[Article]], stories: list[Story], model: str) -> dict:
    return {
        "format": FORMAT,
        "edition": edition_date,
        "generated_at": now_iso(),
        "rubric": {
            "version": rubric.VERSION, "weights": rubric.WEIGHTS, "thresholds": rubric.THRESHOLDS,
            "coverage_cap": rubric.COVERAGE_CAP, "min_outlets": rubric.MIN_OUTLETS, "spotlight": rubric.SPOTLIGHT,
        },
        "editorial": {
            "style_guide_sha256": _sha(config.STYLE_GUIDE_PATH),
            "banned_words_sha256": _sha(config.BANNED_WORDS_PATH),
            "model": model,
        },
        "sources": {sid: {"name": s.name, "lean": s.lean, "type": s.type, "role": s.role,
                          "weight": s.weight, "ratings": s.ratings} for sid, s in sources.items()},
        "articles": [{"source_id": a.source_id, "url": a.url, "title": a.title, "summary": a.summary,
                      "published_at": a.published_at} for a in articles],
        "clusters": [[a.url for a in g] for g in clusters],
        "stories": [
            {
                "headline": s.headline, "bullets": s.bullets, "whats_next": s.whats_next,
                "topic": s.topic, "region": s.region, "written_by": s.written_by,
                "checks": s.checks, "thread_id": s.thread_id, "day": s.day,
                "articles": [a.url for a in s.articles],
                "score": rubric.score(sources[a.source_id] for a in s.articles if a.source_id in sources).to_dict(),
            }
            for s in stories
        ],
    }


def write(directory: Path, data: dict) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{data['edition']}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return path


def restore(directory: Path, db_path: Path) -> int:
    """Rebuild the database from archive files, oldest first. Returns editions restored."""
    conn = connect(db_path)
    files = sorted(Path(directory).glob("*.json"))
    for f in files:
        data = json.loads(f.read_text())
        upsert_articles(conn, [Article(a["source_id"], a["url"], a["title"], a["summary"], a["published_at"])
                               for a in data["articles"]])
        ids = {r["url"]: r["id"] for r in conn.execute("SELECT id, url FROM articles")}
        by_url = {a["url"]: a for a in data["articles"]}
        stories = []
        for s in data["stories"]:
            arts = [Article(by_url[u]["source_id"], u, by_url[u]["title"], by_url[u]["summary"],
                            by_url[u]["published_at"], id=ids[u]) for u in s["articles"] if u in by_url]
            stories.append(Story(data["edition"], s["headline"], s["bullets"], s["whats_next"], s["topic"],
                                 s["region"], s["written_by"], arts, checks=s.get("checks", {}),
                                 thread_id=s.get("thread_id"), day=s.get("day", 1)))
        replace_edition(conn, data["edition"], stories)
    conn.close()
    return len(files)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="boringnews.archive")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("restore", help="rebuild the database from archive files")
    r.add_argument("--from", dest="src", default=str(config.ARCHIVE_DIR))
    r.add_argument("--db", default=str(config.DB_PATH))
    args = ap.parse_args(argv)
    n = restore(Path(args.src), Path(args.db))
    print(f"Restored {n} editions into {args.db}.")


if __name__ == "__main__":
    main()
