"""Balanced weights, rating inputs, the fact check, edition files and story threads."""

import json

import pytest

from boringnews import archive, config, rubric, threads
from boringnews.db import Article, Story, connect, editions, load_edition
from boringnews.pipeline import main as pipeline_main
from boringnews.rewrite import Draft, check_facts, numbers
from boringnews.sources import lean_from_ratings, load_sources

SOURCES = load_sources(config.FIXTURE_SOURCES_PATH)


# ---------------------------------------------------------------- balance and ratings

def write_sources(tmp_path, body):
    p = tmp_path / "s.yaml"
    p.write_text("sources:\n" + body)
    return load_sources(p)


def test_each_side_counts_equally_toward_coverage(tmp_path):
    s = write_sources(tmp_path, "".join(
        f"  - {{id: l{i}, name: L{i}, url: x, lean: left, type: national}}\n" for i in range(4)) +
        "  - {id: c, name: C, url: x, lean: center, type: national}\n"
        "  - {id: r, name: R, url: x, lean: right, type: national}\n")
    assert s["l0"].weight == 0.5 and s["c"].weight == 2.0 and s["r"].weight == 2.0
    # All four left outlets together count the same as the one center outlet.
    four_left = rubric.score([s["l0"], s["l1"], s["l2"], s["l3"]])
    one_center = rubric.score([s["c"]])
    assert four_left.coverage == one_center.coverage


def test_balanced_list_weights_are_one():
    assert all(s.weight == 1.0 for s in SOURCES.values())


def test_lean_from_several_ratings():
    assert lean_from_ratings({"a": "lean left", "b": "left"}) == "left"
    assert lean_from_ratings({"a": "lean left", "b": "center", "c": "lean right"}) == "center"
    assert lean_from_ratings({"a": "lean right", "b": "center"}) == "right"


def test_ratings_override_starting_label(tmp_path):
    s = write_sources(tmp_path, "  - {id: x, name: X, url: x, lean: left, type: national, "
                                "ratings: {raterA: center, raterB: lean right}}\n")
    assert s["x"].lean == "right" and s["x"].ratings == {"raterA": "center", "raterB": "lean right"}


def test_bad_rating_label_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        write_sources(tmp_path, "  - {id: x, name: X, url: x, type: national, ratings: {r: far-left}}\n")


# ---------------------------------------------------------------- fact check

ARTS = [Article("capital-wire", "u1", "Westmark adds 14,200 jobs in October",
                "Unemployment held at 4.1% on 2026-11-03.", "2026-11-04T12:00:00+00:00")]


def draft(bullets, headline="Westmark adds 14,200 jobs", nxt=None):
    return Draft(headline, list(bullets), nxt, "economy", "us-state", "test")


def test_numbers_are_normalized():
    assert numbers("14,200 jobs at 4.1%, on November 3") == {"14200", "4.1", "11", "3"}
    assert "5" not in numbers("officials may decide")


def test_bullet_with_unsourced_number_is_dropped():
    d = check_facts(draft(["Unemployment held at 4.1%.", "Wages rose 3.2%."]), ARTS, SOURCES)
    assert d.bullets == ["Unemployment held at 4.1%."]
    assert d.checks["dropped"][0]["text"] == "Wages rose 3.2%."
    assert "3.2" in d.checks["dropped"][0]["reason"]


def test_model_check_can_drop_bullets():
    class FakeWriter:
        def verify(self, bullets, articles, sources):
            return {1: {"supported": True}, 2: {"supported": False, "reason": "not in any article"}}
    d = check_facts(draft(["Unemployment held at 4.1%.", "Economists expected more."]), ARTS, SOURCES, FakeWriter())
    assert d.bullets == ["Unemployment held at 4.1%."] and d.checks["method"] == "numbers+model"


def test_failed_model_check_is_logged_not_fatal():
    class Broken:
        def verify(self, *a):
            raise TimeoutError
    d = check_facts(draft(["Unemployment held at 4.1%."]), ARTS, SOURCES, Broken())
    assert d.bullets and "model check failed" in d.checks["method"]


def test_demo_edition_logs_the_caught_bullet(tmp_path):
    db = tmp_path / "t.db"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", "2026-11-04", "--db", str(db)])
    water = [s for s in load_edition(connect(db), "2026-11-04") if "Selby" in s.headline][0]
    assert all("400,000" not in b for b in water.bullets)
    assert water.checks["dropped"][0]["text"].startswith("The basin supplies water")


# ---------------------------------------------------------------- edition files

def test_edition_file_round_trip(tmp_path):
    db, arch = tmp_path / "a.db", tmp_path / "archive"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", "2026-11-04", "--db", str(db), "--archive", str(arch)])
    data = json.loads((arch / "2026-11-04.json").read_text())
    assert data["rubric"]["version"] == rubric.VERSION
    assert len(data["stories"]) == 17 and len(data["articles"]) == 50
    assert all("score" in s and "checks" in s for s in data["stories"])

    restored = tmp_path / "restored.db"
    assert archive.restore(arch, restored) == 1
    a = load_edition(connect(db), "2026-11-04")
    b = load_edition(connect(restored), "2026-11-04")
    assert [(s.headline, s.bullets, sorted(x.url for x in s.articles), s.checks) for s in a] == \
           [(s.headline, s.bullets, sorted(x.url for x in s.articles), s.checks) for s in b]


# ---------------------------------------------------------------- threads

def test_developing_story_continues_across_days(tmp_path):
    db = tmp_path / "t.db"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", "2026-11-04", "--db", str(db)])
    conn = connect(db)
    day1 = load_edition(conn, "2026-11-04")
    voter = next(s for s in day1 if "voter ID" in s.headline)

    follow_up = Story("2026-11-05", "Westmark appeals ruling that blocked voter ID rule", ["x"], None,
                      "courts", "us-state", "test",
                      articles=[Article("capital-wire", "https://example.com/new", "Westmark appeals voter ID ruling",
                                        "The secretary of state appealed Judge Alma Reyes's voter ID ruling.",
                                        "2026-11-05T12:00:00+00:00")])
    unrelated = Story("2026-11-05", "Port of Kessland reopens after strike", ["y"], None, "world", "world", "test",
                      articles=[Article("global-report", "https://example.com/port", "Kessland port reopens",
                                        "Dockworkers ended a strike.", "2026-11-05T12:00:00+00:00")])
    assert threads.link(conn, "2026-11-05", [follow_up, unrelated], config.THREAD_SIMILARITY) == 1
    assert follow_up.day == 2 and follow_up.thread_id == voter.thread_id
    assert unrelated.day == 1 and unrelated.thread_id == "2026-11-05-2"
