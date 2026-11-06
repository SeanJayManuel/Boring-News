"""Reader control rules in web/core.js: what was left out and why, custom
weights, recipes and earlier days. A small edition keeps each case readable."""

import pytest

from boringnews import config, rubric
from boringnews.edition import Edition
from boringnews.sources import load_sources

from .core import run_core, select

SOURCES = load_sources(config.ROOT / "fixtures" / "parity_sources.yaml")


def story(id, topic, *sources, day=1):
    return {"id": id, "headline": f"Story {id}", "bullets": ["A fact."], "whats_next": None, "topic": topic,
            "checks": {}, "day": day,
            "articles": [{"source_id": s, "title": f"{s} on {id}", "url": f"https://x.test/{id}/{s}"} for s in sources]}


WIDE = story(1, "economy", "l1", "c1", "r1", "c2")     # every side, in the edition by default
PAPER = story(2, "government", "l1", "c1", "rec")      # two sides and a record
THIN = story(3, "world", "l1", "l2")                   # one side: below the default threshold
RECORD = story(4, "government", "rec")                 # a record no outlet covered
STATEMENT = story(5, "government", "st")               # a statement no outlet covered
SHORT = story(6, "tech", "l1", "st")                   # one outlet and a statement
LONE = story(7, "tech", "c1", "rec")                   # one outlet and a record: a good score, too few outlets
GONE = story(8, "world", "retired-source")             # its only source left the list
DATA = {**Edition("2026-11-04", [], SOURCES).page_data("https://example.org"),
        "stories": [WIDE, PAPER, THIN, RECORD, STATEMENT, SHORT, LONE, GONE]}


def reasons(query=""):
    res = select(DATA, query)
    assert res["hidden"] == len(res["filtered"])
    assert {i["id"] for i in res["items"]}.isdisjoint(f["id"] for f in res["filtered"])
    assert len(res["items"]) + len(res["filtered"]) == len(DATA["stories"])  # every story is in one list or the other
    return {f["id"]: f for f in res["filtered"]}


def test_a_story_outside_the_chosen_topics_says_so():
    hidden = reasons("topics=economy")
    assert hidden[2]["reason"] == "topic" and "isn't one you chose" in hidden[2]["why"]
    assert 1 not in hidden


def test_a_story_with_no_sources_left_blames_the_right_setting():
    assert reasons("exclude=rec")[4]["reason"] == "sources"
    assert "turned off" in reasons("exclude=rec")[4]["why"]
    hidden = reasons("statements=0")
    assert hidden[5]["reason"] == "sources" and "statements" in hidden[5]["why"]
    assert hidden[8]["reason"] == "sources" and "source list" in hidden[8]["why"]


def test_below_threshold_gives_the_numbers():
    hidden = reasons("threshold=strict&blindspots=0")
    assert hidden[3]["reason"] == "blindspot"
    assert "0.55" in hidden[3]["why"] and "Score" in hidden[3]["why"] and "one-sided" in hidden[3]["why"]


def test_too_few_outlets_is_not_called_a_low_score():
    data = {**DATA, "rubric": {**DATA["rubric"], "min_outlets": 9}, "stories": [WIDE]}
    why = select(data)["filtered"][0]["why"]
    assert "4 outlets" in why and "at least 9" in why and "Score" not in why


def test_reader_dropped_sources_are_named_in_a_lower_score():
    hidden = reasons("exclude=c1,c2,r1")
    assert hidden[1]["reason"] == "threshold" and "turned off" in hidden[1]["why"]


def test_hidden_official_items_say_so():
    hidden = reasons("official=0")
    assert hidden[4]["reason"] == "official" and "record" in hidden[4]["why"]
    assert hidden[5]["reason"] == "official" and "statement" in hidden[5]["why"]
    assert hidden[6]["reason"] == "official" and "at least 2" in hidden[6]["why"]  # covered, but fell short


def test_every_reason_has_a_label():
    out = run_core(DATA)
    assert [r["id"] for r in out["reasons"]] == ["topic", "sources", "threshold", "blindspot", "official"]
    assert all(r["label"] for r in out["reasons"])


# ---------- weights
def test_custom_weights_rerank_and_change_lanes():
    assert select(DATA)["order"][0] == 2
    record_only = select(DATA, "weights=0,0,0,100")
    assert record_only["query"] == "weights=0,0,0,100"
    assert [i["total"] for i in record_only["items"]][0] == 1
    assert 1 not in record_only["order"]    # no record, so it scores 0 under these weights
    assert select(DATA, "weights=100,0,0,0")["order"][0] == 1


def test_weights_are_shares_of_their_total():
    assert select(DATA, "weights=1,1,1,1")["items"] == select(DATA, "weights=25,25,25,25")["items"]
    assert all(i["total"] <= 1 for i in select(DATA, "weights=100,100,100,100")["items"])


def test_points_add_up_to_the_total_and_the_reason_says_whose_weights():
    item = select(DATA, "weights=70,10,10,10")["items"][0]
    assert sum(item["points"].values()) == pytest.approx(item["total"], abs=0.001)
    assert item["why"].endswith("with your weights.")
    plain = select(DATA)["items"][0]
    assert plain["why"].endswith(f"Score {plain['total']:.2f}.")
    assert plain["points"]["breadth"] == pytest.approx(rubric.WEIGHTS["breadth"] * 2 / 3, abs=0.001)


@pytest.mark.parametrize("q", ["weights=40,25,10,25", "weights=80,50,20,50", "weights=8,5,2,5"])
def test_the_published_weights_in_any_scale_are_the_default(q):
    res = select(DATA, q)
    assert res["query"] == ""
    assert res["rss"] == select(DATA)["rss"]
    assert "your weights" not in res["rss"]


@pytest.mark.parametrize("q", ["weights=", "weights=1,2,3", "weights=1,2,3,4,5", "weights=a,b,c,d", "weights=-1,1,1,1",
                               "weights=0,0,0,0", "weights=1.5,1,1,1", "weights=101,1,1,1", "weights=,,,", "weights=1,,1,1"])
def test_a_bad_weights_value_is_ignored(q):
    res = select(DATA, q)
    assert res["query"] == "" and res["items"] == select(DATA)["items"]


def test_feed_carries_weights_in_its_own_address():
    assert 'feed.xml?weights=0,0,0,100"' in select(DATA, "weights=0,0,0,100")["rss"]


# ---------- recipes
def test_recipe_name_round_trips_and_titles_the_feed():
    res = select(DATA, "topics=economy&recipe=Morning%20%26%20night")
    assert res["query"] == "topics=economy&recipe=Morning%20%26%20night"
    assert "<title>The Standard Edition (reader recipe: Morning &amp; night)</title>" in res["rss"]
    assert "<title>The Standard Edition</title>" in select(DATA)["rss"]


def test_a_recipe_name_is_cleaned_and_cut():
    assert select(DATA, "recipe=%20%20a%0A%E2%80%AEb%20%20%20c%20")["query"] == "recipe=ab%20c"
    assert select(DATA, "recipe=" + "x" * 500)["query"] == "recipe=" + "x" * 60
    assert "<script" not in select(DATA, "recipe=%3Cscript%3E")["rss"]
    assert select(DATA, "recipe=" + "x" * 59 + "%F0%9F%93%B0")["query"] == "recipe=" + "x" * 59  # half an emoji is dropped


def test_built_in_recipes_mean_what_they_say():
    # List settings drop unknown ids, so a typo here would quietly widen a recipe.
    recipes = run_core(DATA)["recipes"]
    assert len(recipes) >= 3
    for r in recipes:
        assert r["name"] and r["note"]
        assert select(DATA, r["query"])["query"] == r["query"], r["name"]
        settings, _, name = r["query"].rpartition("&recipe=")
        assert settings and name, r["name"]  # every recipe changes something and carries its name


# ---------- earlier days
INDEX = {"days": ["2026-11-04", "2026-11-03", "2026-11-02"], "records": [], "stories": [
    {"key": "2026-11-04-9", "id": 9, "date": "2026-11-04", "day": 3, "thread_id": "2026-11-02-1", "headline": "Today"},
    {"key": "2026-11-03-5", "id": 5, "date": "2026-11-03", "day": 2, "thread_id": "2026-11-02-1", "headline": "Yesterday"},
    {"key": "2026-11-02-1", "id": 1, "date": "2026-11-02", "day": 1, "thread_id": "2026-11-02-1", "headline": "First"},
    {"key": "2026-11-04-7", "id": 7, "date": "2026-11-04", "day": 1, "thread_id": "2026-11-04-1", "headline": "Other"},
    {"key": "2026-11-04-6", "id": 6, "date": "2026-11-04", "day": 4, "thread_id": "2026-10-20-2", "headline": "Old"},
    {"key": "2026-11-03-2", "id": 2, "date": "2026-11-03", "day": 3, "thread_id": "2026-10-20-2", "headline": "Old 3"},
    {"key": "2026-11-04-8", "id": 8, "date": "2026-11-04", "day": 2, "thread_id": None, "headline": "No thread"},
    {"key": "2026-11-03-3", "id": 3, "date": "2026-11-03", "day": 1, "thread_id": None, "headline": "No thread either"},
]}


def earlier(*threads, index=INDEX):
    return run_core(DATA, index=index, threads=list(threads))["threads"]


def test_earlier_days_are_in_order_and_match_only_their_thread():
    found = earlier(["2026-11-04", 9])[0]
    assert [d["headline"] for d in found["days"]] == ["First", "Yesterday"] and found["missing"] == 0


def test_earlier_days_stop_at_the_edition_being_read():
    assert [d["headline"] for d in earlier(["2026-11-03", 5])[0]["days"]] == ["First"]


def test_days_older_than_the_index_are_counted():
    found = earlier(["2026-11-04", 6])[0]
    assert [d["headline"] for d in found["days"]] == ["Old 3"] and found["missing"] == 2


def test_no_index_no_thread_or_an_unknown_story_gives_nothing():
    assert earlier(["2026-11-04", 9], index=None) == [None]
    assert earlier(["2026-11-04", 999]) == [None]
    assert earlier(["2026-11-04", 8]) == [None]
