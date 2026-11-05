"""Build an edition: ingest -> cluster -> score -> rewrite -> store.

Usage:
    python -m boringnews.pipeline run                 # live feeds, a model if one is set up
    python -m boringnews.pipeline run --require-writer  # stop, writing nothing, unless the live keys are set
    python -m boringnews.pipeline run --fixtures      # demo edition from invented sample data
    python -m boringnews.pipeline run --fixtures --mock-llm
    python -m boringnews.pipeline check-feeds         # report which feeds work
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta, timezone

from . import config, rubric, threads
from .cluster import WORDS, Grouping, best_available, cluster
from .db import Story, articles_between, connect, upsert_articles
from .edition import Edition
from .inputs import FixtureInputs, LiveInputs
from .rewrite import ClaudeWriter, LocalWriter, MockWriter, load_banned, write_story
from .sources import load_sources


def edition_window(edition_date: str, lookback_hours: int) -> tuple[str, str]:
    d = date.fromisoformat(edition_date)
    end = datetime.combine(d, time(23, 59, 59), tzinfo=timezone.utc)
    start = end - timedelta(hours=lookback_hours)
    return start.isoformat(), end.isoformat()


def pick_writer(mock: bool):
    if mock:
        return MockWriter(config.FIXTURE_REWRITES_PATH, config.FIXTURE_ARTICLES_PATH)
    if os.environ.get("BN_WRITER_URL"):
        if not os.environ.get("BN_WRITER_MODEL"):  # the name is published with every story
            raise SystemExit("BN_WRITER_URL is set, so BN_WRITER_MODEL must name the model.")
        return LocalWriter(os.environ["BN_WRITER_URL"], os.environ["BN_WRITER_MODEL"])
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeWriter(config.MODEL)
    print("No BN_WRITER_URL or ANTHROPIC_API_KEY set: using the no-model fallback writer.")
    return None


def run_blockers(mock: bool, fixtures: bool) -> list[str]:
    """Why a run that must use a real writer can't go ahead. Empty if it can.
    Sample data needs no Congress key. FRED_API_KEY is optional: the ticker never blocks an edition."""
    blockers = []
    if mock:
        blockers.append("--mock-llm is not a real writer")
    if os.environ.get("BN_WRITER_URL"):
        if not os.environ.get("BN_WRITER_MODEL"):
            blockers.append("BN_WRITER_URL is set but BN_WRITER_MODEL is not")
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        blockers.append("set ANTHROPIC_API_KEY or BN_WRITER_URL")
    if not fixtures and not os.environ.get("CONGRESS_API_KEY"):
        blockers.append("CONGRESS_API_KEY is not set")
    return blockers


def run(inputs, writer, db_path, edition_date: str, archive_dir=None, require_writer: bool = False,
        grouping: Grouping = WORDS) -> Edition:
    """Build, store and (with archive_dir) publish the edition for a date.
    `inputs` is a LiveInputs or FixtureInputs; `writer` is None for the fallback writer.
    With `require_writer`, stops before storing if the writer produced nothing: a bad
    key, an outage or a model that rejects the request all look like this."""
    sources = inputs.sources
    conn = connect(db_path)
    banned = load_banned(config.BANNED_WORDS_PATH)
    style_guide = config.STYLE_GUIDE_PATH.read_text() if writer else ""

    # 1. Ingest
    start, end = edition_window(edition_date, config.LOOKBACK_HOURS)
    fetched, health = inputs.articles(datetime.fromisoformat(start))
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
    clusters = cluster(articles, grouping, config.CLUSTER_WINDOW_HOURS, separate=official_ids)
    print(f"{len(articles)} articles in window -> {len(clusters)} clusters, grouped by {grouping.method}.")

    # 3. Score; only write up clusters that pass the loosest reader setting
    stories, sports = [], []
    for group in cap_official(clusters, sources):
        sc = rubric.score(sources[a.source_id] for a in group)
        if not rubric.is_candidate(sc):
            continue
        if rubric.is_sports(group, sources):  # before the writer, so it costs nothing
            sports.append(group)
            print(f"  [{sc.total:.2f}] left out as sports: {group[0].title}  ({len(group)} articles)")
            continue
        # 4. Rewrite
        draft = write_story(group, sources, banned, writer, style_guide)
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

    if require_writer and stories and all(s.written_by == "fallback" for s in stories):
        raise SystemExit("Not storing the edition: every story used the fallback writer.")

    # 5. Follow developing stories from the previous edition
    linked = threads.link(conn, edition_date, stories, config.THREAD_SIMILARITY)
    if linked:
        print(f"{linked} stories continue from the previous edition.")

    # 6. Yesterday's market closes for the ticker (never blocks the edition)
    ticker, problems = inputs.markets()
    for p in problems:
        print(f"  ticker: {p}")
    print(f"Ticker: {len(ticker)} market closes.")

    # 7. Store, and write the public edition file
    edition = Edition(edition_date, stories, sources, ticker, [h.source_id for h in health if not h.ok])
    edition.save(conn)
    print(f"Edition {edition_date}: {len(stories)} stories stored in {db_path}.")
    if archive_dir:
        path = edition.write_file(archive_dir, articles, clusters, writer.model if writer else "none (fallback writer)",
                                  writer.usage if writer else None, sports, grouping.record())
        print(f"Edition file written to {path}.")
    return edition


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


def check_feeds(inputs) -> int:
    _, health = inputs.articles()
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
    r.add_argument("--require-writer", action="store_true",
                   help="exit with an error, writing nothing, if a real writer or a live key is missing")
    r.add_argument("--date", help="edition date, YYYY-MM-DD (default: today, UTC)")
    r.add_argument("--db", default=str(config.DB_PATH))
    r.add_argument("--archive", help="folder for the edition file (default: archive/; none with --fixtures)")
    r.add_argument("--no-archive", action="store_true", help="don't write the edition file")
    sub.add_parser("check-feeds", help="test every feed in sources.yaml")
    args = p.parse_args(argv)
    if args.cmd == "check-feeds":
        return check_feeds(LiveInputs(load_sources(config.SOURCES_PATH)))
    if args.require_writer:
        blockers = run_blockers(args.mock_llm, args.fixtures)
        if blockers:
            print("Not building the edition: " + "; ".join(blockers) + ".", file=sys.stderr)
            return 1
    sources = load_sources(config.sources_path(args.fixtures))
    inputs = FixtureInputs(sources) if args.fixtures else LiveInputs(sources)
    archive_dir = args.archive or (None if args.fixtures else str(config.ARCHIVE_DIR))
    run(inputs, pick_writer(args.mock_llm), args.db, args.date or datetime.now(timezone.utc).date().isoformat(),
        None if args.no_archive else archive_dir, args.require_writer,
        WORDS if args.fixtures else best_available())
    return 0


if __name__ == "__main__":
    sys.exit(main())
