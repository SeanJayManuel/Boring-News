"""Turn a cluster of articles into one calm story.

Three writers, tried in order:
  1. Claude (needs ANTHROPIC_API_KEY): follows editorial/style_guide.md
  2. mock: canned example output from fixtures/rewrites.json (demo only)
  3. fallback: no model. Picks the most neutral source headline and the
     first sentences of source summaries that pass the banned-word linter.

Every result goes through the linter. A model draft that fails is retried once
with the violations named; if it still fails, the fallback is used.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .db import Article
from .sources import Source
from .topics import REGIONS, TOPICS, guess_region, guess_topic

QUOTE_RE = re.compile(r"\"[^\"]*\"|“[^”]*”")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
TYPE_PRIORITY = {"wire": 0, "primary": 1, "national": 2, "international": 3, "regional": 4}
LEAN_PRIORITY = {"center": 0, "unrated": 1, "left": 2, "right": 2}


@dataclass
class Draft:
    headline: str
    bullets: list[str]
    whats_next: str | None
    topic: str
    region: str
    written_by: str


# ---------------------------------------------------------------- linter

def load_banned(path: Path) -> list[str]:
    words = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line.lower())
    return words


def lint(text: str, banned: list[str]) -> list[str]:
    """Return banned terms found outside quotation marks."""
    unquoted = QUOTE_RE.sub(" ", text).lower()
    found = []
    for term in banned:
        if re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", unquoted):
            found.append(term)
    return found


def lint_draft(d: Draft, banned: list[str]) -> list[str]:
    text = " ".join([d.headline, *d.bullets, d.whats_next or ""])
    return lint(text, banned)


# ---------------------------------------------------------------- prompt

OUTPUT_CONTRACT = f"""
Return ONLY a JSON object, no prose, with these keys:
  "headline":   string, under 12 words
  "bullets":    array of 3 to 5 strings, one fact each
  "whats_next": string or null (a scheduled vote, ruling, deadline or effective date only)
  "topic":      one of {list(TOPICS)}
  "region":     one of {list(REGIONS)}
"""


def build_prompt(articles: list[Article], sources: dict[str, Source]) -> str:
    parts = ["Here are news articles about the same event, from outlets across the political spectrum.\n"]
    for i, a in enumerate(articles, 1):
        src = sources.get(a.source_id)
        name = src.name if src else a.source_id
        parts.append(f"[{i}] {name}\nTitle: {a.title}\nSummary: {a.summary}\n")
    parts.append(
        "Write one Boring News story from these articles, following the style guide exactly. "
        "Use only facts found in the articles. Do not copy the outlets' wording."
    )
    return "\n".join(parts)


def _parse(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in model output")
    data = json.loads(text[start : end + 1])
    bullets = [str(b).strip() for b in data.get("bullets", []) if str(b).strip()]
    if not data.get("headline") or not bullets:
        raise ValueError("model output missing headline or bullets")
    return {
        "headline": str(data["headline"]).strip(),
        "bullets": bullets[:5],
        "whats_next": (str(data["whats_next"]).strip() or None) if data.get("whats_next") else None,
        "topic": data.get("topic") if data.get("topic") in TOPICS else None,
        "region": data.get("region") if data.get("region") in REGIONS else None,
    }


# ---------------------------------------------------------------- writers

class ClaudeWriter:
    def __init__(self, model: str, style_guide: str, banned: list[str]):
        import anthropic  # imported here so the package works without the SDK configured

        self.client = anthropic.Anthropic()
        self.model = model
        self.system = style_guide + "\n\n" + OUTPUT_CONTRACT
        self.banned = banned

    def _call(self, messages: list[dict]) -> str:
        resp = self.client.messages.create(
            model=self.model, max_tokens=800, system=self.system, messages=messages
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    def write(self, articles: list[Article], sources: dict[str, Source]) -> Draft | None:
        messages = [{"role": "user", "content": build_prompt(articles, sources)}]
        for _attempt in range(2):
            text = self._call(messages)
            try:
                data = _parse(text)
            except (ValueError, json.JSONDecodeError):
                messages += [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": "That was not valid JSON with the required keys. Return only the JSON object."},
                ]
                continue
            draft = _to_draft(data, articles, sources, self.model)
            problems = lint_draft(draft, self.banned)
            if not problems:
                return draft
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"These words break the style guide: {', '.join(problems)}. Rewrite without them. Return only the JSON object."},
            ]
        return None


class MockWriter:
    """Demo writer: returns the canned output whose match_url is in the cluster."""

    def __init__(self, path: Path):
        data = json.loads(Path(path).read_text())
        self.by_url = {r["match_url"]: r for r in data["rewrites"]}

    def write(self, articles: list[Article], sources: dict[str, Source]) -> Draft | None:
        for a in articles:
            if a.url in self.by_url:
                return _to_draft(self.by_url[a.url], articles, sources, "mock")
        return None


def fallback(articles: list[Article], sources: dict[str, Source], banned: list[str]) -> Draft:
    def rank(a: Article):
        s = sources.get(a.source_id)
        return (
            TYPE_PRIORITY.get(s.type, 9) if s else 9,
            LEAN_PRIORITY.get(s.lean, 9) if s else 9,
            len(a.title),
        )

    ordered = sorted(articles, key=rank)
    clean_titles = [a.title for a in ordered if not lint(a.title, banned)]
    headline = clean_titles[0] if clean_titles else ordered[0].title

    bullets, seen = [], set()
    for a in ordered:
        first = SENTENCE_RE.split(a.summary.strip())[0] if a.summary else ""
        key = first.lower()[:60]
        if first and key not in seen and not lint(first, banned):
            bullets.append(first)
            seen.add(key)
        if len(bullets) == 3:
            break
    if not bullets:
        bullets = ["See the linked sources for details."]
    return _to_draft(
        {"headline": headline, "bullets": bullets, "whats_next": None, "topic": None, "region": None},
        articles, sources, "fallback",
    )


def _to_draft(data: dict, articles: list[Article], sources: dict[str, Source], written_by: str) -> Draft:
    text = " ".join([a.title + " " + a.summary for a in articles])
    srcs = [sources[a.source_id] for a in articles if a.source_id in sources]
    types = {s.type for s in srcs}
    hints = {s.topic for s in srcs if s.topic}
    hint = next(iter(hints)) if len(hints) == 1 and all(s.topic for s in srcs) else None
    return Draft(
        headline=data["headline"],
        bullets=list(data["bullets"]),
        whats_next=data.get("whats_next"),
        topic=data.get("topic") or hint or guess_topic(text),
        region=data.get("region") or guess_region(text, types),
        written_by=written_by,
    )


def write_story(articles, sources, banned, writer=None) -> Draft:
    if writer is not None:
        try:
            draft = writer.write(articles, sources)
        except Exception as exc:  # API errors shouldn't kill the edition
            print(f"  writer error, using fallback: {exc}")
            draft = None
        if draft is not None and not lint_draft(draft, banned):
            return draft
    return fallback(articles, sources, banned)
