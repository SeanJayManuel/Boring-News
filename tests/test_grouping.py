"""Grouping, through its interface. No test here loads the embedding model: a stand-in
gives each article a chosen vector, so similarity is what the test says it is."""

import builtins
from datetime import datetime, timedelta, timezone

import numpy as np

from boringnews import cluster as grouping
from boringnews.cluster import WORDS, best_available, cluster, embedded
from boringnews.db import Article

START = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
FILLER = [Article("f", f"https://x.test/f{i}", f"Filler {i}", "A Plain note about nothing much.", START.isoformat())
          for i in range(40)]


def article(n, source, title, summary="", hours=0):
    return Article(source, f"https://x.test/{n}", title, summary, (START + timedelta(hours=hours)).isoformat())


def by_vector(vectors: dict):
    """An embedder that looks up each text's first word; anything else is its own direction."""
    def embed(texts):
        size = len(texts) + 4
        rows = []
        for i, t in enumerate(texts):
            v = np.zeros(size)
            key = t.split()[0]
            if key in vectors:
                v[:len(vectors[key])] = vectors[key]
            else:
                v[4 + i] = 1
            rows.append(v)
        return np.array(rows)
    return embed


def grouped(articles, vectors, **kw):
    groups = cluster(articles + FILLER, embedded(by_vector(vectors)), **kw)
    return sorted(sorted(a.url.rsplit("/", 1)[1] for a in g) for g in groups if not g[0].url.split("/")[-1].startswith("f"))


NAMED = "Talks in Vilnius ended. Officials from Lithuania met."


def test_alike_with_a_shared_rare_name_join():
    arts = [article(1, "a", "Alpha one", NAMED), article(2, "b", "Alpha two", NAMED)]
    assert grouped(arts, {"Alpha": [1, 0]}) == [["1", "2"]]


def test_alike_with_no_shared_name_stay_apart():
    arts = [article(1, "a", "Alpha one", "Talks with Vilnius ended."), article(2, "b", "Alpha two", "Rain near Oslo fell.")]
    assert grouped(arts, {"Alpha": [1, 0]}) == [["1"], ["2"]]


def test_a_shared_name_without_likeness_stays_apart():
    arts = [article(1, "a", "Alpha one", NAMED), article(2, "b", "Beta two", NAMED)]
    assert grouped(arts, {"Alpha": [1, 0], "Beta": [0, 1]}) == [["1"], ["2"]]


def test_one_close_pair_cant_chain_two_stories():
    arts = [article(1, "a", "Alpha one", NAMED), article(2, "b", "Alpha two", NAMED),
            article(3, "c", "Beta three", NAMED), article(4, "d", "Beta four", NAMED),
            article(5, "e", "Gamma bridge", NAMED)]
    groups = grouped(arts, {"Alpha": [1, 0], "Beta": [0, 1], "Gamma": [.75, .66]})
    assert not any({"1", "3"} <= set(g) for g in groups)


def test_live_blogs_join_nothing():
    arts = [article(1, "a", "Alpha one", NAMED), article(2, "b", "Alpha live updates", NAMED)]
    assert grouped(arts, {"Alpha": [1, 0]}) == [["1"], ["2"]]


def test_articles_outside_the_window_stay_apart():
    arts = [article(1, "a", "Alpha one", NAMED), article(2, "b", "Alpha two", NAMED, hours=60)]
    assert grouped(arts, {"Alpha": [1, 0]}, window_hours=48) == [["1"], ["2"]]


def test_one_official_sources_items_stay_apart():
    arts = [article(1, "reg", "Alpha one", NAMED), article(2, "reg", "Alpha two", NAMED)]
    assert grouped(arts, {"Alpha": [1, 0]}, separate=frozenset({"reg"})) == [["1"], ["2"]]


def test_a_name_in_too_many_articles_says_nothing():
    common = [article(i, "c", f"Other {i}", "Talks with Vilnius went on.") for i in range(10, 30)]
    arts = [article(1, "a", "Alpha one", "Talks with Vilnius ended."), article(2, "b", "Alpha two", "Talks with Vilnius ended.")]
    assert ["1"] in grouped(arts + common, {"Alpha": [1, 0]})


def test_word_grouping_works_with_no_model():
    arts = [article(1, "a", "Senate passes Vilnius treaty", NAMED), article(2, "b", "Senate passes Vilnius treaty today", NAMED)]
    assert len(cluster(arts, WORDS)) == 1


def test_small_inputs():
    assert cluster([]) == []
    assert len(cluster([article(1, "a", "One")])) == 1


def test_falls_back_to_words_when_the_model_cant_load(monkeypatch):
    real = builtins.__import__

    def no_fastembed(name, *args, **kw):
        if name == "fastembed":
            raise ImportError(name)
        return real(name, *args, **kw)

    monkeypatch.setattr(builtins, "__import__", no_fastembed)
    assert best_available() is WORDS


def test_each_method_is_recorded():
    assert WORDS.record() == {"method": "words", "model": None, "threshold": grouping.config.WORD_SIMILARITY}
    assert embedded(lambda t: t).record()["model"] == grouping.EMBEDDING_MODEL
