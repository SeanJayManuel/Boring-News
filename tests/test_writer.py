"""What happens to a writer's text: every writer goes through the same parsing,
retries, linting and fact check, so these use scripted replies."""

import json
from types import SimpleNamespace

from boringnews import config
from boringnews.db import Article
from boringnews.pipeline import pick_writer
from boringnews.rewrite import ClaudeWriter, MockWriter, load_banned, write_story
from boringnews.sources import load_sources

SOURCES = load_sources(config.FIXTURE_SOURCES_PATH)
BANNED = load_banned(config.BANNED_WORDS_PATH)
ARTS = [Article("capital-wire", "https://x/1", "Westmark adds 14,200 jobs in October",
                "Unemployment held at 4.1% as Westmark added 14,200 jobs.", "2026-11-04T12:00:00+00:00")]
GOOD = {"headline": "Westmark adds 14,200 jobs", "bullets": ["Unemployment held at 4.1%."], "whats_next": None, "topic": "economy"}


class Scripted:
    model = "test-model"
    checks_facts = False

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, messages, max_tokens=800):
        self.calls.append((system, list(messages)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)


def write(writer):
    return write_story(ARTS, SOURCES, BANNED, writer, "STYLE GUIDE")


def test_style_guide_and_output_rules_reach_the_writer():
    w = Scripted(GOOD)
    d = write(w)
    system = w.calls[0][0]
    assert system.startswith("STYLE GUIDE") and "Return ONLY a JSON object" in system
    assert d.headline == GOOD["headline"] and d.written_by == "test-model"


def test_json_is_found_inside_chatter():
    assert write(Scripted("Sure! " + json.dumps(GOOD) + " Done.")).written_by == "test-model"


def test_unparseable_reply_gets_one_retry():
    w = Scripted("not json", GOOD)
    assert write(w).written_by == "test-model" and len(w.calls) == 2
    assert "not valid JSON" in w.calls[1][1][-1]["content"]


def test_two_unparseable_replies_use_the_fallback():
    assert write(Scripted("no", "still no")).written_by == "fallback"


def test_banned_word_gets_one_retry_naming_it():
    bad = dict(GOOD, bullets=[f"Unemployment held at 4.1%, a {BANNED[0]} result."])
    w = Scripted(bad, GOOD)
    assert write(w).bullets == GOOD["bullets"]
    assert BANNED[0] in w.calls[1][1][-1]["content"]


def test_banned_word_twice_uses_the_fallback():
    bad = dict(GOOD, bullets=[f"Unemployment held at 4.1%, a {BANNED[0]} result."])
    assert write(Scripted(bad, bad)).written_by == "fallback"


def test_only_five_bullets_are_kept():
    many = dict(GOOD, bullets=[f"Unemployment held at 4.1%, part {c}." for c in "abcdefg"])
    assert len(write(Scripted(many)).bullets) == 5


def test_old_topic_from_the_model_is_normalized():
    assert write(Scripted(dict(GOOD, topic="courts"))).topic == "government"


def test_writer_error_uses_the_fallback():
    assert write(Scripted(TimeoutError())).written_by == "fallback"


def test_failed_fact_check_replaces_the_draft_and_says_why():
    unsourced = dict(GOOD, bullets=["Wages rose 99%."])
    d = write(Scripted(unsourced))
    assert d.written_by == "fallback"
    assert d.checks["replaced_draft"]["reason"] == "every bullet failed the fact check"
    assert d.checks["replaced_draft"]["dropped"][0]["text"] == "Wages rose 99%."


def test_unsourced_headline_replaces_the_draft():
    d = write(Scripted(dict(GOOD, headline="Westmark adds 99 jobs")))
    assert d.written_by == "fallback" and d.checks["replaced_draft"]["reason"] == "headline failed the fact check"


def test_claude_writer_only_returns_text():
    seen = {}

    def create(**kw):
        seen.update(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text="hello")])

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    w = ClaudeWriter("claude-test", client=client)
    assert w.complete("sys", [{"role": "user", "content": "hi"}], max_tokens=5) == "hello"
    assert seen == {"model": "claude-test", "max_tokens": 5, "system": "sys", "messages": [{"role": "user", "content": "hi"}]}


def test_claude_writer_also_checks_facts_and_mock_does_not():
    assert ClaudeWriter("m", client=object()).checks_facts
    assert not pick_writer(True).checks_facts


def test_mock_writer_goes_through_the_same_parsing():
    w = MockWriter(config.FIXTURE_REWRITES_PATH, config.FIXTURE_ARTICLES_PATH)
    assert w.complete("sys", [{"role": "user", "content": "Title: nothing we know\n"}]) == ""
    assert write_story(ARTS, SOURCES, BANNED, w).written_by == "fallback"


def test_no_key_means_the_fallback_writer(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert pick_writer(False) is None
