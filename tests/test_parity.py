"""The score and lane are the only rules that exist twice: rubric.py decides what
gets written up and records it in the edition file, and web/core.js works them
out again for each reader's settings. These tests check both agree."""

import itertools

import pytest

from boringnews import config, rubric
from boringnews.edition import Edition
from boringnews.sources import load_sources

from .core import run_core

SOURCES = load_sources(config.ROOT / "fixtures" / "parity_sources.yaml")
DATA = Edition("2026-11-04", [], SOURCES).page_data("https://example.org")


def test_weights_in_this_list_are_not_all_one():
    assert {s.weight for s in SOURCES.values()} > {1.0}


def test_js_score_matches_python():
    ids = list(SOURCES)
    groups = [list(c) for n in (1, 2, 3, 5, len(ids)) for c in itertools.combinations(ids, n)]
    js = run_core(DATA, scores=groups)["scores"]
    for group, j in zip(groups, js):
        p = rubric.score(SOURCES[i] for i in group)
        assert j["total"] == pytest.approx(p.total, abs=1e-9), group
        assert j["outlets"] == p.outlets and j["leans"] == p.leans and j["ratedOutlets"] == p.rated_outlets, group
        assert (j["hasPrimary"], j["hasRecord"], j["hasStatement"]) == (p.has_primary, p.has_record, p.has_statement), group
        for part in rubric.WEIGHTS:
            assert j["parts"][part] == pytest.approx(getattr(p, part), abs=0.0005 + 1e-9), group
        for threshold, lanes in j["lanes"].items():
            assert lanes == [rubric.lane(p, threshold, True), rubric.lane(p, threshold, False),
                             rubric.lane(p, threshold, True, blindspots=False)], group
    assert any("blindspot" in lanes for j in js for lanes in j["lanes"].values())
