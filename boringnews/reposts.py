"""Find articles that repeat another outlet's report, usually wire copy.

Outlets running one report aren't separate sources, so the page says so and the
writer is told. It doesn't change a story's score yet (roadmap T7).
"""

from __future__ import annotations

import re

from .db import Article

WORD_RE = re.compile(r"[a-z0-9]+")
SAME_TITLE_WORDS = 5   # a shared headline this long is one report, not coincidence
SAME_TEXT_WORDS = 12   # shorter texts overlap by chance
SAME_TEXT = 0.75       # share of words in common


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _same_report(a: Article, b: Article) -> bool:
    title_a, title_b = _words(a.title), _words(b.title)
    if len(title_a) >= SAME_TITLE_WORDS and title_a == title_b:
        return True
    text_a, text_b = set(title_a + _words(a.summary)), set(title_b + _words(b.summary))
    if min(len(text_a), len(text_b)) < SAME_TEXT_WORDS:
        return False
    return len(text_a & text_b) / len(text_a | text_b) >= SAME_TEXT


def reposts(articles: list[Article]) -> dict[str, Article]:
    """Maps each repeated article's URL to the earliest article it repeats."""
    originals: list[Article] = []
    copies: dict[str, Article] = {}
    for a in sorted(articles, key=lambda x: x.published_at):
        first = next((o for o in originals if o.source_id != a.source_id and _same_report(o, a)), None)
        if first:
            copies[a.url] = first
        else:
            originals.append(a)
    return copies
