"""Group articles about the same event. docs/clustering.md is the plain-language
version, and any change here must update it.

Two articles can join when they read alike (`Grouping.similarity`). With embeddings
they must also share a name that few of the day's articles use: embeddings rate
two stories from one news cycle as alike, and a name tells them apart.

Groups then form by average linkage: a group joins another only if its articles read
alike on average. One close pair can't chain two stories together, and a live blog,
which touches every story of the day, never joins anything.

Sentence embeddings match on meaning, so outlets using different words still group.
They need a model, so `WORDS` (TF-IDF, no download) is the fallback and the setting
for sample data and tests. Every edition file records which one ran.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from typing import Callable

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import config
from .db import Article

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# A name in more of the day's articles than this says nothing about the event.
RARE_NAME_SHARE = 0.05
RARE_NAME_FLOOR = 12  # on a quiet day a share would be smaller than one story's coverage
_NEVER = 1e6  # a distance no average can bring under the threshold

_BOILERPLATE = re.compile(r"Continue reading\.\.\.|Sign up for [^.]*?email|\{beacon\}|Presented by \w+|© [A-Z]\w+ \w+")
_BYLINE = re.compile(r"\s\|\s[A-Z][\w .'’-]+$")  # "| Author" on opinion headlines
_LIVE = re.compile(r"\blive\b(?!s)|live updates|^\d+/\d+:|The Latest\b|– video$", re.I)
_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]+")
_NOT_NAMES = frozenset(
    "the a an in on at of for to and but or as by with from new after before says said will has have his her he she "
    "it its they their this that these those who what how why when where while not no is are was were be been more "
    "most over than".split())


def _title(a: Article) -> str:
    return _BYLINE.sub("", a.title)


def _summary(a: Article) -> str:
    return re.sub(r"\s+", " ", _BOILERPLATE.sub(" ", a.summary or "")).strip()[:300]


def _word_similarity(articles: list[Article]) -> np.ndarray:
    # Titles carry the event; count them twice relative to the summary.
    texts = [f"{_title(a)}. {_title(a)}. {_summary(a)}" for a in articles]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    return cosine_similarity(vec.fit_transform(texts))


@dataclass(frozen=True)
class Grouping:
    method: str
    threshold: float  # each method has its own scale, so each has its own threshold
    similarity: Callable[[list[Article]], np.ndarray] = field(repr=False)
    model: str | None = None
    needs_shared_name: bool = False

    def record(self) -> dict:
        """What an edition file says about how its stories were grouped."""
        return {"method": self.method, "model": self.model, "threshold": self.threshold}


WORDS = Grouping("words", config.WORD_SIMILARITY, _word_similarity)


def embedded(embed: Callable[[list[str]], np.ndarray], model: str = EMBEDDING_MODEL) -> Grouping:
    """`embed` turns texts into one vector each."""
    def similarity(articles: list[Article]) -> np.ndarray:
        vectors = np.asarray(embed([f"{_title(a)}. {_summary(a)}" for a in articles]))
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors @ vectors.T
    return Grouping("embeddings", config.EMBEDDING_SIMILARITY, similarity, model, needs_shared_name=True)


def best_available(cache_dir: Path = config.MODEL_CACHE) -> Grouping:
    """Embeddings if the model loads, else `WORDS`. A failed download shouldn't cost
    a day's edition, and the edition file shows which method ran."""
    try:
        from fastembed import TextEmbedding
        model = TextEmbedding(EMBEDDING_MODEL, cache_dir=str(cache_dir))
    except Exception as e:
        print(f"  embedding model unavailable, grouping by words: {e}")
        return WORDS
    return embedded(lambda texts: np.array(list(model.embed(texts))))


def _names(articles: list[Article]) -> list[set[str]]:
    """Each article's proper names. A word is a name if the day's text capitalises it
    mid-sentence and rarely uses it in lower case. Headlines that capitalise every
    word can't teach this, so only sentence-case ones count."""
    capital, lower = Counter(), Counter()
    for a in articles:
        title = _title(a)
        words = _WORD.findall(title)
        sentence_case = sum(w[0].isupper() for w in words) * 2 <= len(words)
        for sentence in re.split(r"(?<=[.!?])\s+", _BOILERPLATE.sub(" ", a.summary or "")) + ([title] if sentence_case else []):
            for k, word in enumerate(_WORD.findall(sentence)):
                word = re.sub(r"['’]s$", "", word)
                if word[0].isupper() and k > 0:
                    capital[word.lower()] += 1
                elif word[0].islower():
                    lower[word.lower()] += 1
    names = {w for w, n in capital.items() if lower[w] <= n * 0.25 and w not in _NOT_NAMES and len(w) > 2}
    found = []
    for a in articles:
        words = _WORD.findall(f"{_title(a)} {_summary(a)}")
        found.append({re.sub(r"['’]s$", "", w).lower() for w in words if w[0].isupper()} & names)
    return found


def _share_rare_name(articles: list[Article]) -> np.ndarray:
    names = _names(articles)
    used = Counter(n for s in names for n in s)
    limit = max(RARE_NAME_FLOOR, ceil(RARE_NAME_SHARE * len(articles)))
    rare = [{n for n in s if used[n] <= limit} for s in names]
    n = len(articles)
    shared = np.zeros((n, n), bool)
    for i in range(n):
        for j in range(i + 1, n):
            shared[i, j] = shared[j, i] = bool(rare[i] & rare[j])
    return shared


def cluster(articles: list[Article], grouping: Grouping = WORDS, window_hours: int = 48,
            separate: frozenset[str] = frozenset()) -> list[list[Article]]:
    """`separate`: source ids whose items are never joined to each other.
    Official sources go here: two documents from the same agency are two
    events, even when their boilerplate ("Final rule: ...") looks alike."""
    if not articles:
        return []
    if len(articles) == 1:
        return [articles]

    n = len(articles)
    distance = 1 - grouping.similarity(articles)
    live = np.array([bool(_LIVE.search(a.title)) for a in articles])
    distance[live[:, None] | live[None, :]] = _NEVER
    if grouping.needs_shared_name:
        distance[~_share_rare_name(articles)] = _NEVER
    window = window_hours * 3600
    for i in range(n):
        for j in range(i + 1, n):
            same_official = articles[i].source_id == articles[j].source_id and articles[i].source_id in separate
            if same_official or abs((articles[i].published - articles[j].published).total_seconds()) > window:
                distance[i, j] = distance[j, i] = _NEVER
    np.fill_diagonal(distance, 0)
    labels = AgglomerativeClustering(n_clusters=None, metric="precomputed", linkage="average",
                                     distance_threshold=1 - grouping.threshold).fit_predict((distance + distance.T) / 2)

    groups: dict[int, list[Article]] = {}
    for label, a in zip(labels, articles):
        groups.setdefault(int(label), []).append(a)
    # Biggest clusters first; stable within equal sizes.
    return sorted(groups.values(), key=lambda g: (-len(g), g[0].published_at))
