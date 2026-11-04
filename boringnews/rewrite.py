"""Turn a cluster of articles into one calm story.

Three writers, tried in order:
  1. Claude (needs ANTHROPIC_API_KEY): follows editorial/style_guide.md
  2. mock: canned example output from fixtures/rewrites.json (demo only)
  3. fallback: no model. Picks the most neutral source headline and the
     first sentences of source summaries that pass the banned-word linter.

Every result goes through the linter. A model draft that fails is retried once
with the violations named; if it still fails, the fallback is used.

Then every draft is fact-checked against its sources (`check_facts`):
  - numbers: every number in a bullet must appear in the sources
  - model (when a key is set): a second call confirms each bullet is supported
Unsupported bullets are dropped and logged in `Draft.checks`, which is
published with the edition.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .db import Article
from .sources import Source
from .topics import TOPIC_DESCRIPTIONS, TOPICS, guess_region, guess_topic, normalize

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
    checks: dict = field(default_factory=dict)


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

OUTPUT_CONTRACT = """
Return ONLY a JSON object, no prose, with these keys:
  "headline":   string, under 12 words
  "bullets":    array of 3 to 5 strings, one fact each
  "whats_next": string or null (a scheduled vote, ruling, deadline or effective date only)
  "topic":      the one category that fits best:
""" + "".join(f"                {k}: {v}\n" for k, v in TOPIC_DESCRIPTIONS.items())


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
        "topic": normalize(data.get("topic")),
        "region": None,
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


def _verify_with_model(writer, bullets, articles, sources) -> dict[int, dict]:
    listing = "\n".join(f"{i}. {b}" for i, b in enumerate(bullets, 1))
    content = build_prompt(articles, sources).rsplit("\n", 1)[0] + "\n\nStatements:\n" + listing
    resp = writer.client.messages.create(
        model=writer.model, max_tokens=600, system=VERIFY_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    start, end = text.find("["), text.rfind("]")
    items = json.loads(text[start : end + 1])
    return {int(x["n"]): x for x in items}


ClaudeWriter.verify = lambda self, bullets, articles, sources: _verify_with_model(self, bullets, articles, sources)


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
        topic=normalize(data.get("topic")) or normalize(hint) or guess_topic(text),
        region=data.get("region") or guess_region(text, types),
        written_by=written_by,
    )


# ---------------------------------------------------------------- fact check

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}


def numbers(text: str) -> set[str]:
    """Numbers in a text, normalized: '14,200' -> '14200', '03' -> '3'.
    Month names count as their number, so 'November 3' matches '2026-11-03'."""
    out = set()
    for n in NUM_RE.findall(text):
        n = n.replace(",", "").rstrip(".")
        whole, _, frac = n.partition(".")
        out.add((whole.lstrip("0") or "0") + ("." + frac if frac else ""))
    for name, i in MONTHS.items():  # capitalized whole words only, so the verb "may" isn't May
        if re.search(rf"\b{name.capitalize()}\b", text):
            out.add(str(i))
    return out


def unsupported_numbers(text: str, source_text: str) -> set[str]:
    return numbers(text) - numbers(source_text)


VERIFY_PROMPT = """Below are news articles and a list of numbered statements written from them.
For each statement, decide if the articles support it. A statement is supported only if
every fact in it appears in at least one article; attributed claims ("X said") are
supported if the article reports that X said it.

Return ONLY a JSON array, one object per statement: {"n": <number>, "supported": true|false, "reason": "<short>"}.
"""


def check_facts(draft: Draft, articles: list[Article], sources: dict[str, Source], writer=None) -> Draft:
    source_text = " ".join(a.title + " " + a.summary for a in articles)
    dropped = []
    kept = []
    for b in draft.bullets:
        bad = unsupported_numbers(b, source_text)
        if bad:
            dropped.append({"text": b, "reason": "numbers not in sources: " + ", ".join(sorted(bad))})
        else:
            kept.append(b)
    method = "numbers"

    if writer is not None and hasattr(writer, "verify") and kept:
        try:
            verdicts = writer.verify(kept, articles, sources)
            method = "numbers+model"
            still = []
            for i, b in enumerate(kept, 1):
                v = verdicts.get(i, {"supported": True})
                if v.get("supported", True):
                    still.append(b)
                else:
                    dropped.append({"text": b, "reason": "model: " + str(v.get("reason", "not supported"))})
            kept = still
        except Exception as exc:  # a failed check never blocks the edition; it is logged
            method = f"numbers (model check failed: {exc.__class__.__name__})"

    whats_next = draft.whats_next
    if whats_next and unsupported_numbers(whats_next, source_text):
        dropped.append({"text": whats_next, "reason": "what's next: numbers not in sources"})
        whats_next = None

    headline_ok = not unsupported_numbers(draft.headline, source_text)
    if not headline_ok:
        dropped.append({"text": draft.headline, "reason": "headline: numbers not in sources"})

    draft.bullets = kept
    draft.whats_next = whats_next
    draft.checks = {"method": method, "checked": len(kept) + len(dropped), "dropped": dropped,
                    "headline_ok": headline_ok}
    return draft


def write_story(articles, sources, banned, writer=None) -> Draft:
    if writer is not None:
        try:
            draft = writer.write(articles, sources)
        except Exception as exc:  # API errors shouldn't kill the edition
            print(f"  writer error, using fallback: {exc}")
            draft = None
        if draft is not None and not lint_draft(draft, banned):
            draft = check_facts(draft, articles, sources, writer)
            if draft.bullets and draft.checks["headline_ok"]:
                return draft
            reason = "every bullet failed the fact check" if not draft.bullets else "headline failed the fact check"
            fb = check_facts(fallback(articles, sources, banned), articles, sources)
            fb.checks["replaced_draft"] = {"reason": reason, "dropped": draft.checks["dropped"]}
            return fb
    return check_facts(fallback(articles, sources, banned), articles, sources)
