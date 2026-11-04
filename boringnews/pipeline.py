"""Build an edition: ingest -> cluster -> score -> rewrite -> store.

Usage:
    python -m boringnews.pipeline run                 # live feeds, Claude if ANTHROPIC_API_KEY is set
    python -m boringnews.pipeline run --fixtures      # demo edition from invented sample data
    python -m boringnews.pipeline run --fixtures --mock-llm
    python -m boringnews.pipeline check-feeds         # report which feeds work
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta, timezone

from . import archive, config, markets, rubric, threads
from .cluster import cluster
from .db import Story, articles_between, connect, replace_edition, save_extra, upsert_articles
from .ingest import fetch_all, load_fixtures
from .rewrite import ClaudeWriter, MockWriter, load_banned, write_story
from .sources import load_sources


def edition_window(edition_date: str, lookback_hours: int) -> tuple[str, str]:
    d = date.fromisoformat(edition_date)
    end = datetime.combine(d, time(23, 59, 59), tzinfo=timezone.utc)
    start = end - timedelta(hours=lookback_hours)
    return start.isoformat(), end.isoformat()


def pick_writer(args):
    banned = load_banned(config.BANNED_WORDS_PATH)
    if args.mock_llm:
        return MockWriter(config.FIXTURE_REWRITES_PATH), banned
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeWriter(config.MODEL, config.STYLE_GUIDE_PATH.read_text(), banned), banned
    print("No ANTHROPIC_API_KEY set: using the no-model fallback writer.")
    return None, banned


def run(args) -> int:
    sources_path = config.FIXTURE_SOURCES_PATH if args.fixtures else config.SOURCES_PATH
    sources = load_sources(sources_path)
    conn = connect(args.db)

    # 1. Ingest
    edition_date = args.date or datetime.now(timezone.utc).date().isoformat()
    start, end = edition_window(edition_date, config.LOOKBACK_HOURS)
    if args.fixtures:
        fetched = load_fixtures(config.FIXTURE_ARTICLES_PATH)
    else:
        fetched, health = fetch_all(sources, since=datetime.fromisoformat(start))
        for h in health:
            if not h.ok:
                print(f"  source problem: {h.source_id}: {h.error}")
            elif h.stale:
                print(f"  source looks stale: {h.source_id}: newest item {h.newest}")
    added = upsert_articles(conn, fetched)
    print(f"Ingested {len(fetched)} articles ({added} new).")

    # 2. Cluster this edition's window
    articles = [a for a in articles_between(conn, start, end) if a.source_id in sources]
    official_ids = frozenset(sid for sid, s in sources.items() if s.type == "primary")
    clusters = cluster(articles, config.CLUSTER_SIMILARITY, config.CLUSTER_WINDOW_HOURS, separate=official_ids)
    print(f"{len(articles)} articles in window -> {len(clusters)} clusters.")

    # 3. Score; only write up clusters that pass the loosest reader setting
    writer, banned = pick_writer(args)
    stories = []
    for group in cap_official(clusters, sources):
        sc = rubric.score(sources[a.source_id] for a in group)
        if not rubric.is_candidate(sc):
            continue
        # 4. Rewrite
        draft = write_story(group, sources, banned, writer)
        stories.append(
            Story(
                edition_date=edition_date,
                headline=draft.headline,
                bullets=draft.bullets,
                whats_next=draft.whats_next,
                topic=draft.topic,
                region=draft.region,
                written_by=draft.written_by,
                articles=group,
                checks=draft.checks,
            )
        )
        dropped = len(draft.checks.get("dropped", []))
        note = f", {dropped} dropped by fact check" if dropped else ""
        print(f"  [{sc.total:.2f}] {draft.headline}  ({len(group)} articles, {draft.written_by}{note})")

    # 5. Follow developing stories from the previous edition
    linked = threads.link(conn, edition_date, stories, config.THREAD_SIMILARITY)
    if linked:
        print(f"{linked} stories continue from the previous edition.")

    # 6. Store, and write the public edition file
    replace_edition(conn, edition_date, stories)
    print(f"Edition {edition_date}: {len(stories)} stories stored in {args.db}.")

    # 7. Yesterday's market closes for the ticker (never blocks the edition)
    if args.fixtures:
        ticker = markets.load_fixture(config.FIXTURE_MARKETS_PATH)
    else:
        ticker, problems = markets.fetch(markets.load_series())
        for p in problems:
            print(f"  ticker: {p}")
    save_extra(conn, edition_date, "markets", ticker)
    print(f"Ticker: {len(ticker)} market closes.")
    archive_dir = args.archive or (None if args.fixtures else str(config.ARCHIVE_DIR))
    if archive_dir and not args.no_archive:
        model = getattr(writer, "model", None) or ("mock" if args.mock_llm else "none (fallback writer)")
        path = archive.write(archive_dir, archive.build(edition_date, sources, articles, clusters, stories, model, ticker))
        print(f"Edition file written to {path}.")
    return 0


def cap_official(clusters, sources):
    """Official sources can publish dozens of items a day. Keep at most
    `max_items` of each one's items that no outlet covered (newest first);
    items that news outlets also covered are never dropped."""
    kept, seen = [], {}
    for group in sorted(clusters, key=lambda g: max(a.published_at for a in g), reverse=True):
        ids = {a.source_id for a in group}
        only = next(iter(ids)) if len(ids) == 1 else None
        src = sources.get(only) if only else None
        if src and src.type == "primary" and src.max_items:
            seen[only] = seen.get(only, 0) + 1
            if seen[only] > src.max_items:
                continue
        kept.append(group)
    # Restore the original order (biggest clusters first).
    order = {id(g): i for i, g in enumerate(clusters)}
    return sorted(kept, key=lambda g: order[id(g)])


def check_feeds(args) -> int:
    sources = load_sources(config.SOURCES_PATH)
    _, health = fetch_all(sources)
    width = max(len(h.source_id) for h in health)
    for h in health:
        if not h.ok:
            status = f"FAIL  {h.error}"
        else:
            status = f"OK    {h.items:3d} items" + (f", newest {h.newest}" if h.newest else "")
            if h.stale:
                status += "  STALE: nothing new in 14+ days"
        print(f"{h.source_id:<{width}}  {status}")
    return 0 if all(h.ok for h in health) else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="boringnews.pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="build an edition")
    r.add_argument("--fixtures", action="store_true", help="use invented sample data instead of live feeds")
    r.add_argument("--mock-llm", action="store_true", help="use canned example rewrites (demo)")
    r.add_argument("--date", help="edition date, YYYY-MM-DD (default: today, UTC)")
    r.add_argument("--db", default=str(config.DB_PATH))
    r.add_argument("--archive", help="folder for the edition file (default: archive/; none with --fixtures)")
    r.add_argument("--no-archive", action="store_true", help="don't write the edition file")
    sub.add_parser("check-feeds", help="test every feed in sources.yaml")
    args = p.parse_args(argv)
    return run(args) if args.cmd == "run" else check_feeds(args)


if __name__ == "__main__":
    sys.exit(main())
