"""Follow a developing story across days.

Each new story is matched to at most one story from the previous edition:
first by shared articles (the edition window overlaps, so a story still in
the news often keeps some of yesterday's articles), then by how similar their
headlines and article titles are. A match continues that story's thread, so
the page can say "Day 3" instead of presenting it as new.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .db import Story, load_edition


def previous_edition(conn, edition_date: str) -> str | None:
    row = conn.execute("SELECT MAX(edition_date) FROM stories WHERE edition_date < ?", (edition_date,)).fetchone()
    return row[0] if row else None


def _text(s: Story) -> str:
    return " ".join([s.headline, s.headline] + [a.title for a in s.articles])


def link(conn, edition_date: str, stories: list[Story], similarity: float = 0.25) -> int:
    """Set thread_id and day on each story. Returns how many continue a thread."""
    for i, s in enumerate(stories, 1):
        s.thread_id, s.day = f"{edition_date}-{i}", 1
    prev_date = previous_edition(conn, edition_date)
    if not prev_date or not stories:
        return 0
    prev = load_edition(conn, prev_date)
    if not prev:
        return 0

    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    m = vec.fit_transform([_text(s) for s in stories] + [_text(p) for p in prev])
    sim = cosine_similarity(m[: len(stories)], m[len(stories):])

    pairs = []
    for i, s in enumerate(stories):
        urls = {a.url for a in s.articles}
        for j, p in enumerate(prev):
            shared = bool(urls & {a.url for a in p.articles})
            if shared or sim[i, j] >= similarity:
                pairs.append((1 if shared else 0, sim[i, j], i, j))
    used_new, used_prev, linked = set(), set(), 0
    for _, _, i, j in sorted(pairs, reverse=True):  # shared articles first, then most similar
        if i in used_new or j in used_prev:
            continue
        p = prev[j]
        stories[i].thread_id = p.thread_id or f"{prev_date}-{p.id}"
        stories[i].day = (p.day or 1) + 1
        used_new.add(i)
        used_prev.add(j)
        linked += 1
    return linked
