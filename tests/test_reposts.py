"""Repeated reports, what each side reported, and how both reach the writer."""

from boringnews.db import Article
from boringnews.reposts import reposts
from boringnews.rewrite import Draft, _parse, _to_draft, build_prompt, check_facts, lint_draft
from boringnews.sources import Source

LONG = "The mayor declared a local emergency after a storm surge flooded downtown and cut power to about 18,000 customers."


def article(source, url, title, summary=LONG, when="2026-11-04T08:00:00Z"):
    return Article(source, url, title, summary, when)


def source(sid, lean, kind="national"):
    return Source(id=sid, name=sid.title(), url="fixture", lean=lean, type=kind)


SOURCES = {"a": source("a", "left"), "b": source("b", "center"), "c": source("c", "right")}


def test_the_same_text_is_one_report_and_the_earliest_is_the_original():
    first = article("a", "u1", "Port Avery declares emergency", when="2026-11-04T08:00:00Z")
    later = article("b", "u2", "Emergency declared in Port Avery", when="2026-11-04T09:00:00Z")
    assert reposts([later, first]) == {"u2": first}


def test_the_same_long_headline_is_one_report():
    copies = reposts([article("a", "u1", "Port Avery declares an emergency today", "One."),
                      article("b", "u2", "Port Avery declares an emergency today", "Two.", "2026-11-04T09:00:00Z")])
    assert set(copies) == {"u2"}


def test_separate_reports_on_one_event_are_not_reposts():
    assert reposts([article("a", "u1", "Storm floods Port Avery", "Power is out for 18,000 customers after flooding."),
                    article("b", "u2", "Mayor declares emergency", "The mayor acted after seawater reached downtown streets.")]) == {}


def test_two_stories_from_one_outlet_are_not_reposts():
    assert reposts([article("a", "u1", "Port Avery declares emergency"), article("a", "u2", "Port Avery declares emergency")]) == {}


def test_writer_is_told_about_a_repeated_report_and_each_outlets_side():
    prompt = build_prompt([article("a", "u1", "One"), article("b", "u2", "Two", when="2026-11-04T09:00:00Z")], SOURCES)
    assert "[1] A, left\n" in prompt and "[2] B, center (repeats the A report)" in prompt


def draft(sides):
    return Draft("Headline", ["The mayor declared an emergency."], None, "states", "us", "test", sides=sides)


def test_a_side_with_no_articles_is_removed_from_the_writers_reply():
    reply = '{"headline": "H", "bullets": ["B."], "sides": {"left": ["L."], "right": ["R."], "other": ["X."]}}'
    made = _to_draft(_parse(reply), [article("a", "u1", "One"), article("b", "u2", "Two")], SOURCES, "test")
    assert made.sides == {"left": ["L."]}


def test_each_side_is_checked_only_against_its_own_articles():
    articles = [article("a", "u1", "One", "Power is out for 18,000 customers."), article("b", "u2", "Two", "No deaths were reported."),
                article("c", "u3", "Three", "The mayor spoke.")]
    checked = check_facts(draft({"left": ["About 18,000 lost power."], "center": ["About 18,000 lost power."],
                                 "right": ["The mayor spoke."]}), articles, SOURCES)
    assert set(checked.sides) == {"left", "right"}
    assert checked.checks["dropped"][0]["reason"].startswith("center: numbers not in that side's sources")


def test_one_side_left_after_checking_is_not_kept():
    articles = [article("a", "u1", "One", "No numbers here."), article("b", "u2", "Two", "None here either.")]
    assert check_facts(draft({"left": ["Fine."], "center": ["About 18,000 lost power."]}), articles, SOURCES).sides == {}


def test_loaded_words_are_caught_in_a_side_summary():
    assert lint_draft(draft({"left": ["It was a historic vote."]}), ["historic"]) == ["historic"]
