"""What happens to a writer's text: every writer goes through the same parsing,
retries, linting and fact check, so these use scripted replies."""

import io
import json
from types import SimpleNamespace

import pytest

from boringnews import config
from boringnews.db import Article
from boringnews.pipeline import pick_writer
from boringnews.rewrite import ClaudeWriter, FailedReply, LocalWriter, MockWriter, load_banned, write_story
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


class FakeClaude:
    """Stands in for the SDK client. Replies are (text, stop_reason) pairs."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append({**kw, "messages": list(kw["messages"])})
        text, stop = self.replies.pop(0)
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)],
            stop_reason=stop, usage=SimpleNamespace(input_tokens=100, output_tokens=20))


def claude(*replies):
    client = FakeClaude(*replies)
    return ClaudeWriter("claude-test", client=client), client


SUPPORTED = '[{"n": 1, "supported": true}]'


def test_claude_writer_only_returns_text():
    w, client = claude(("hello", "end_turn"))
    assert w.complete("sys", [{"role": "user", "content": "hi"}], max_tokens=5) == "hello"
    assert client.calls == [{"model": "claude-test", "max_tokens": 5, "system": "sys",
                             "output_config": {"effort": "low"},
                             "messages": [{"role": "user", "content": "hi"}]}]


def test_story_and_fact_check_calls_use_low_effort_and_room_to_finish():
    w, client = claude((json.dumps(GOOD), "end_turn"), (SUPPORTED, "end_turn"))
    d = write(w)
    assert d.written_by == "claude-test" and d.checks["method"] == "numbers+model"
    assert [c["max_tokens"] for c in client.calls] == [2000, 2000]
    assert all(c["output_config"] == {"effort": "low"} for c in client.calls)


def test_truncated_reply_is_not_parsed_even_if_it_looks_complete(capsys):
    shorter = dict(GOOD, bullets=["Westmark added 14,200 jobs."])
    w, client = claude((json.dumps(GOOD), "max_tokens"), (json.dumps(shorter), "end_turn"), (SUPPORTED, "end_turn"))
    assert write(w).bullets == shorter["bullets"]
    assert len(client.calls[1]["messages"]) == 1  # the partial text isn't sent back
    assert "max_tokens" in capsys.readouterr().out


def test_two_truncated_replies_use_the_fallback():
    w, _ = claude(("{", "max_tokens"), ("{", "max_tokens"))
    assert write(w).written_by == "fallback"


def test_refusal_is_not_retried(capsys):
    w, client = claude((json.dumps(GOOD), "refusal"))
    assert write(w).written_by == "fallback"
    assert len(client.calls) == 1 and "refusal" in capsys.readouterr().out


def test_truncated_fact_check_is_logged_not_trusted():
    w, _ = claude((json.dumps(GOOD), "end_turn"), (SUPPORTED, "max_tokens"))
    d = write(w)
    assert d.written_by == "claude-test" and "model check failed: FailedReply" in d.checks["method"]


def test_failed_replies_still_count_toward_tokens():
    w, _ = claude((json.dumps(GOOD), "max_tokens"), (json.dumps(GOOD), "refusal"))
    assert w.usage is None
    write(w)
    assert w.usage == {"input_tokens": 200, "output_tokens": 40}


# A local server, spoken to through an injected opener: no sockets, no model.

class FakeServer:
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return io.BytesIO(json.dumps(self.replies.pop(0)).encode())


def reply(text, finish="stop", usage=(10, 5)):
    body = {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish}]}
    if usage:
        body["usage"] = {"prompt_tokens": usage[0], "completion_tokens": usage[1]}
    return body


def local(*replies):
    server = FakeServer(*replies)
    return LocalWriter("http://localhost:11434/", "llama3.2", opener=server), server


def test_local_writer_posts_a_chat_completion():
    w, server = local(reply("hello"))
    assert w.complete("sys", [{"role": "user", "content": "hi"}]) == "hello"
    request, timeout = server.requests[0]
    assert request.full_url == "http://localhost:11434/v1/chat/completions" and request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json" and timeout >= 60
    assert json.loads(request.data) == {
        "model": "llama3.2", "max_tokens": 2000,
        "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]}


def test_local_writer_gets_the_same_treatment_and_is_named_on_the_story():
    w, server = local(reply(json.dumps(GOOD)), reply(SUPPORTED))
    assert w.checks_facts
    d = write(w)
    assert d.written_by == "llama3.2" and d.checks["method"] == "numbers+model"
    assert len(server.requests) == 2 and w.usage == {"input_tokens": 20, "output_tokens": 10}


def test_local_truncated_reply_is_retried_and_filtered_reply_is_not():
    w, server = local(reply(json.dumps(GOOD), "length"), reply(json.dumps(GOOD)), reply(SUPPORTED))
    assert write(w).written_by == "llama3.2" and len(server.requests) == 3
    w, server = local(reply(json.dumps(GOOD), "content_filter"))
    assert write(w).written_by == "fallback" and len(server.requests) == 1


def test_local_server_that_reports_no_tokens_records_none_rather_than_zero():
    w, _ = local(reply("hello", usage=None))
    w.complete("sys", [{"role": "user", "content": "hi"}])
    assert w.usage is None


def test_local_server_failure_uses_the_fallback():
    def down(request, timeout):
        raise OSError("connection refused")

    assert write(LocalWriter("http://localhost:1", "m", opener=down)).written_by == "fallback"


def test_claude_writer_also_checks_facts_and_mock_does_not():
    assert ClaudeWriter("m", client=object()).checks_facts
    assert not pick_writer(True).checks_facts


def test_mock_writer_goes_through_the_same_parsing():
    w = MockWriter(config.FIXTURE_REWRITES_PATH, config.FIXTURE_ARTICLES_PATH)
    assert w.complete("sys", [{"role": "user", "content": "Title: nothing we know\n"}]) == ""
    assert write_story(ARTS, SOURCES, BANNED, w).written_by == "fallback"


def test_no_key_means_the_fallback_writer(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BN_WRITER_URL", raising=False)
    assert pick_writer(False) is None


def test_writer_url_wins_over_an_anthropic_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("BN_WRITER_URL", "http://localhost:8080")
    monkeypatch.setenv("BN_WRITER_MODEL", "gemma")
    w = pick_writer(False)
    assert isinstance(w, LocalWriter) and w.model == "gemma"


def test_writer_url_without_a_model_stops_rather_than_publishing_a_blank_name(monkeypatch):
    monkeypatch.setenv("BN_WRITER_URL", "http://localhost:8080")
    monkeypatch.delenv("BN_WRITER_MODEL", raising=False)
    with pytest.raises(SystemExit, match="BN_WRITER_MODEL"):
        pick_writer(False)
