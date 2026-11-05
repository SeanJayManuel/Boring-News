"""A run with bad days: sources, the ticker and the writer can all fail, and
the edition still comes out."""

from datetime import datetime, timedelta, timezone

from boringnews import config, ingest
from boringnews.db import connect, editions
from boringnews.edition import Edition
from boringnews.ingest import FeedHealth, fetch_all
from boringnews.inputs import FixtureInputs
from boringnews.pipeline import check_feeds, run
from boringnews.sources import Source, load_sources

SOURCES = load_sources(config.FIXTURE_SOURCES_PATH)
DATE = "2026-11-04"


class BadDay(FixtureInputs):
    def articles(self, since=None):
        arts, _ = super().articles(since)
        return arts, [FeedHealth("capital-wire", False, 0, "HTTP 503"),
                      FeedHealth("metro-ledger", True, 3, None, "2026-01-01", True)]

    def markets(self):
        return [], ["FRED key missing"]


class BrokenWriter:
    model = "broken"
    checks_facts = False

    def complete(self, *a, **k):
        raise TimeoutError


def test_fixtures_and_fakes_give_the_same_run(tmp_path):
    e = run(FixtureInputs(SOURCES), None, tmp_path / "t.db", DATE)
    assert isinstance(e, Edition) and e.date == DATE and len(e.stories) == 17 and e.markets
    assert {s.written_by for s in e.stories} == {"fallback"}


def test_a_bad_day_still_publishes_and_says_what_went_wrong(tmp_path, capsys):
    e = run(BadDay(SOURCES), BrokenWriter(), tmp_path / "t.db", DATE, tmp_path / "archive")
    out = capsys.readouterr().out
    assert "source problem: capital-wire: HTTP 503" in out
    assert "source looks stale: metro-ledger" in out
    assert "ticker: FRED key missing" in out
    assert "writer error, using fallback" in out
    assert e.stories and editions(connect(tmp_path / "t.db")) == [DATE]
    assert (tmp_path / "archive" / f"{DATE}.json").exists()


def test_check_feeds_reports_each_source_and_fails_on_a_problem(capsys):
    assert check_feeds(BadDay(SOURCES)) == 1
    out = capsys.readouterr().out
    assert "FAIL  HTTP 503" in out and "STALE" in out


def source(sid, kind="rss", type_="national"):
    return Source(id=sid, name=sid, url="x", lean="center", type=type_, fetcher=kind)


def article(sid, age_days):
    when = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    return ingest.Article(sid, f"https://x/{sid}", "t", "s", when)


def test_one_failing_source_does_not_stop_the_others(monkeypatch):
    def fetcher(src, since):
        if src.id == "down":
            raise OSError("no route")
        return [] if src.id in ("quiet", "empty") else [article(src.id, 30 if src.id == "old" else 0)]

    monkeypatch.setitem(ingest.FETCHERS, "rss", fetcher)
    sources = {s.id: s for s in [source("up"), source("down"), source("old"), source("empty"), source("quiet", type_="primary")]}
    arts, health = fetch_all(sources)
    h = {x.source_id: x for x in health}
    assert sorted(a.source_id for a in arts) == ["old", "up"]
    assert h["up"].ok and not h["up"].stale
    assert not h["down"].ok and h["down"].error == "no route"
    assert h["old"].ok and h["old"].stale
    assert not h["empty"].ok and h["empty"].error == "no items"
    assert h["quiet"].ok  # an official source with nothing new is normal
