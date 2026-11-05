"""A run with bad days: sources, the ticker and the writer can all fail, and
the edition still comes out."""

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import yaml

from boringnews import config, ingest, pipeline
from boringnews.db import connect, editions
from boringnews.edition import Edition
from boringnews.ingest import FeedHealth, fetch_all
from boringnews.inputs import FixtureInputs
from boringnews.pipeline import check_feeds, main, run, run_blockers
from boringnews.rewrite import MockWriter
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
    usage = None

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


def editorial(archive):
    return json.loads((archive / f"{DATE}.json").read_text())["editorial"]


def test_fallback_and_mock_runs_record_no_tokens(tmp_path):
    run(FixtureInputs(SOURCES), None, tmp_path / "t.db", DATE, tmp_path / "a")
    assert editorial(tmp_path / "a")["usage"] is None
    mock = MockWriter(config.FIXTURE_REWRITES_PATH, config.FIXTURE_ARTICLES_PATH)
    run(FixtureInputs(SOURCES), mock, tmp_path / "m.db", DATE, tmp_path / "b")
    assert editorial(tmp_path / "b")["usage"] is None


@pytest.fixture
def stand_in():
    """A throwaway OpenAI-compatible server that always answers with unusable text."""
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            body = json.dumps({"choices": [{"message": {"content": "no"}, "finish_reason": "stop"}],
                               "usage": {"prompt_tokens": 7, "completion_tokens": 3}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", calls
    server.shutdown()
    server.server_close()


def clear_keys(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "BN_WRITER_URL", "BN_WRITER_MODEL", "CONGRESS_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_a_run_against_a_local_server_names_the_model_and_totals_its_tokens(tmp_path, monkeypatch, stand_in):
    url, calls = stand_in
    clear_keys(monkeypatch)
    monkeypatch.setenv("BN_WRITER_URL", url)
    monkeypatch.setenv("BN_WRITER_MODEL", "stand-in")
    archive = tmp_path / "a"
    code = main(["run", "--fixtures", "--date", DATE, "--db", str(tmp_path / "t.db"), "--archive", str(archive)])
    assert code == 0 and calls and {path for path, _ in calls} == {"/v1/chat/completions"}
    record = editorial(archive)
    assert record["model"] == "stand-in"
    assert record["usage"] == {"input_tokens": 7 * len(calls), "output_tokens": 3 * len(calls)}


@pytest.mark.parametrize("env, extra, expected", [
    ({"CONGRESS_API_KEY": "x"}, [], "ANTHROPIC_API_KEY"),
    ({"ANTHROPIC_API_KEY": "", "CONGRESS_API_KEY": "x"}, [], "ANTHROPIC_API_KEY"),  # an unset Actions secret is empty
    ({"ANTHROPIC_API_KEY": "x"}, [], "CONGRESS_API_KEY"),
    ({"ANTHROPIC_API_KEY": "x", "CONGRESS_API_KEY": ""}, [], "CONGRESS_API_KEY"),
    ({"BN_WRITER_URL": "http://localhost:1", "CONGRESS_API_KEY": "x"}, [], "BN_WRITER_MODEL"),
    ({"ANTHROPIC_API_KEY": "x", "CONGRESS_API_KEY": "x"}, ["--mock-llm"], "--mock-llm"),
])
def test_require_writer_stops_before_anything_is_written(tmp_path, monkeypatch, capsys, env, extra, expected):
    clear_keys(monkeypatch)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(pipeline, "LiveInputs", FixtureInputs)  # never the network, even if the check is broken
    db, archive = tmp_path / "t.db", tmp_path / "a"
    assert main(["run", "--require-writer", "--date", DATE, "--db", str(db), "--archive", str(archive), *extra]) != 0
    assert not db.exists() and not archive.exists()
    assert expected in capsys.readouterr().err


@pytest.mark.parametrize("env", [
    {"ANTHROPIC_API_KEY": "x", "CONGRESS_API_KEY": "x"},
    {"BN_WRITER_URL": "http://localhost:1", "BN_WRITER_MODEL": "m", "CONGRESS_API_KEY": "x"},
])
def test_require_writer_passes_with_the_live_keys(monkeypatch, env):
    clear_keys(monkeypatch)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert run_blockers(mock=False, fixtures=False) == []


def test_sample_runs_need_a_writer_but_not_the_congress_key(monkeypatch):
    clear_keys(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert run_blockers(mock=False, fixtures=True) == []


def workflow(name):
    return yaml.safe_load((config.ROOT / ".github" / "workflows" / name).read_text())


def test_nightly_build_requires_a_writer():
    steps = workflow("nightly.yml")["jobs"]["edition"]["steps"]
    build = next(s for s in steps if s.get("name") == "Build today's edition")
    assert "--require-writer" in build["run"]


def test_pull_request_tests_cannot_publish():
    text = (config.ROOT / ".github" / "workflows" / "tests.yml").read_text()
    flow = yaml.safe_load(text)
    triggers = flow[True]  # YAML reads a bare `on` as true
    assert "pull_request" in triggers and triggers["push"]["branches"] == ["main"]
    assert flow["permissions"] == {"contents": "read"}
    assert "secrets." not in text and "wrangler" not in text and "git push" not in text
    steps = flow["jobs"]["tests"]["steps"]
    assert any(s.get("with", {}).get("python-version") == "3.12" for s in steps)
    assert any(s.get("with", {}).get("node-version") == "20" for s in steps)
    assert [s["run"] for s in steps if "run" in s] == ["pip install -r requirements.txt", "npm ci", "pytest -q"]


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


def test_required_writer_stops_when_every_story_falls_back(tmp_path):
    with pytest.raises(SystemExit, match="fallback writer"):
        run(FixtureInputs(SOURCES), BrokenWriter(), tmp_path / "t.db", DATE, tmp_path / "archive", require_writer=True)
    assert editions(connect(tmp_path / "t.db")) == []
    assert not (tmp_path / "archive").exists()
