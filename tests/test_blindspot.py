"""Stories only one side ran: written up, listed apart, and described only as far
as the day's reading supports."""

import pytest

from boringnews import config, db, rubric
from boringnews.edition import Edition, restore
from boringnews.sources import load_sources

from .core import select

SOURCES = load_sources(config.ROOT / "fixtures" / "parity_sources.yaml")


def score(*ids):
    return rubric.score(SOURCES[i] for i in ids)


def data(*groups, feeds_down=()):
    d = Edition("2026-11-04", [], SOURCES, [], list(feeds_down)).page_data("https://example.org")
    d["stories"] = [
        {"id": i, "headline": f"Story {i}", "bullets": ["A fact."], "whats_next": "", "topic": "government", "checks": {},
         "day": 1, "articles": [{"source_id": s, "title": "T", "url": f"https://x.test/{i}/{s}"} for s in g]}
        for i, g in enumerate(groups, 1)
    ]
    return d


@pytest.mark.parametrize("ids", [("l2", "l3"), ("c1", "c2"), ("r1", "r2")])
def test_two_outlets_on_any_side_are_a_blind_spot(ids):
    sc = score(*ids)
    assert rubric.lane(sc, "strict") == "blindspot" and rubric.is_candidate(sc)


def test_one_outlet_with_an_unrated_one_is_not():
    assert rubric.lane(score("l2", "u1"), "strict") is None


def test_unrated_outlets_dont_hide_a_blind_spot():
    assert rubric.lane(score("l2", "l3", "u1"), "strict") == "blindspot"


def test_two_sides_are_not_a_blind_spot():
    assert not rubric.is_blindspot(score("l2", "r2"))


def test_a_story_above_the_threshold_stays_in_the_main_list():
    assert rubric.lane(score("l1", "l2", "l3", "l4"), "broad") == "main"


def test_it_can_be_turned_off():
    assert rubric.lane(score("l2", "l3"), "strict", blindspots=False) is None


def test_a_blind_spot_outranks_the_government_lane():
    assert rubric.lane(score("l2", "l3", "st"), "strict", official=False) == "blindspot"


def test_never_in_the_spotlight():
    res = select(data(("l2", "l3"), ("l1", "c1", "r1")), "spotlight=1&threshold=strict")
    assert [x["lane"] for x in res["items"]] == ["main"]


def test_says_what_was_read():
    res = select(data(("r1", "r2")), "threshold=strict")
    assert res["items"][0]["lane"] == "blindspot"
    assert res["items"][0]["why"].startswith("Among the outlets we read, only right outlets ran this.")
    assert "One side only: Story 1" in res["rss"] and "Government" not in res["rss"].split("<item>")[1].split("</title>")[0]


def test_leaving_out_a_source_changes_the_words():
    res = select(data(("r1", "r2")), "threshold=strict&exclude=l1")
    assert res["items"][0]["why"].startswith("Among the outlets you kept, only right outlets ran this.")


def test_no_claim_when_a_missing_sides_feed_failed():
    res = select(data(("r1", "r2"), feeds_down=["l1"]), "threshold=strict")
    assert "We couldn't read L1 today" in res["items"][0]["why"] and "only right" not in res["items"][0]["why"]
    assert "Coverage unclear: Story 1" in res["rss"]


def test_a_failed_feed_on_the_same_side_changes_nothing():
    res = select(data(("r1", "r2"), feeds_down=["r3"]), "threshold=strict")
    assert res["items"][0]["why"].startswith("Among the outlets we read")


def test_a_reader_who_turned_it_off_sees_why():
    res = select(data(("r1", "r2")), "threshold=strict&blindspots=0")
    assert res["items"] == [] and res["filtered"][0]["reason"] == "blindspot"


def test_failed_feeds_survive_a_rebuild_from_edition_files(tmp_path):
    conn = db.connect(tmp_path / "a.db")
    edition = Edition("2026-11-04", [], SOURCES, [], ["l1"])
    edition.save(conn)
    edition.write_file(tmp_path / "archive", [], [], "none")
    restore(tmp_path / "archive", tmp_path / "b.db")
    assert db.load_extra(db.connect(tmp_path / "b.db"), "2026-11-04", "feeds_down") == ["l1"]
