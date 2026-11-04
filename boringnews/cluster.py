"""Group articles about the same event.

MVP approach: TF-IDF over title + summary, cosine similarity, then join any
two articles above a threshold that were published close together
(single-link clustering via union-find). Cheap, deterministic, no API calls.
Phase 2 swaps TF-IDF for sentence embeddings.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .db import Article


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        self.parent[self.find(i)] = self.find(j)


def cluster(articles: list[Article], similarity: float = 0.15, window_hours: int = 48,
            separate: frozenset[str] = frozenset()) -> list[list[Article]]:
    """`separate`: source ids whose items are never joined to each other.
    Official sources go here: two documents from the same agency are two
    events, even when their boilerplate ("Final rule: ...") looks alike."""
    if not articles:
        return []
    if len(articles) == 1:
        return [articles]

    # Titles carry the event; count them twice relative to the summary.
    texts = [f"{a.title}. {a.title}. {a.summary}" for a in articles]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    sim = cosine_similarity(vec.fit_transform(texts))

    uf = _UnionFind(len(articles))
    window = window_hours * 3600
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            if sim[i, j] < similarity:
                continue
            if articles[i].source_id == articles[j].source_id and articles[i].source_id in separate:
                continue
            if abs((articles[i].published - articles[j].published).total_seconds()) > window:
                continue
            uf.union(i, j)

    groups: dict[int, list[Article]] = {}
    for i, a in enumerate(articles):
        groups.setdefault(uf.find(i), []).append(a)
    # Biggest clusters first; stable within equal sizes.
    return sorted(groups.values(), key=lambda g: (-len(g), g[0].published_at))
