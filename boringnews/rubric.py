"""The selection rubric: which stories make the edition, and why.

This file is the editorial policy in code. It is published on the
"How it works" page, and web/core.js applies the same score and lane in
JavaScript so readers can change the threshold or drop sources.

    score = 0.40 * breadth + 0.25 * coverage + 0.10 * diversity + 0.25 * record

breadth   share of left / center / right that covered the story (0, 1/3, 2/3, 1)
coverage  distinct outlets, log-scaled, capped at 10 outlets. Each outlet counts by its
          weight, so a side with more outlets on the list can't inflate coverage.
diversity distinct outlet types (wire, national, regional, international) / 3, capped at 1
record    1 if an official RECORD documents it (a law, a rule, a court ruling, a vote,
          official statistics), else 0. Official STATEMENTS (press releases) never count.

A story makes the edition with score >= threshold AND at least two outlets.
Official items that no outlet covered are listed too, under their topic,
because they matter whether or not anyone wrote about them.

The top SPOTLIGHT stories by score are the day's spotlight.

Sports are left out, whatever their score: see `is_sports`. That rule decides
what is written and not how anything scores, so it doesn't change VERSION.

v0.4 (2026-11-04): coverage counts weighted outlets (each side counts equally).
v0.3 (2026-11-04): only official records earn `record`; statements are listed
but add nothing, so an administration's press releases can't lift a story.
v0.2 (2026-11-04): added `record`, so stories backed by an official source
rank higher; thresholds recalibrated for the new weights.
v0.1 (2026-11-04): breadth 0.50, coverage 0.35, diversity 0.15.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from typing import Iterable
from urllib.parse import urlsplit

from .sources import Source

VERSION = "0.4"
WEIGHTS = {"breadth": 0.40, "coverage": 0.25, "diversity": 0.10, "record": 0.25}
THRESHOLDS = {"broad": 0.30, "standard": 0.40, "strict": 0.55}
COVERAGE_CAP = 10
MIN_OUTLETS = 2
SPOTLIGHT = 5
SPECTRUM = ("left", "center", "right")
OUTLET_TYPES = ("wire", "national", "regional", "international")


@dataclass
class Score:
    total: float
    breadth: float
    coverage: float
    diversity: float
    record: float
    outlets: int
    leans: list[str]
    types: list[str]
    has_primary: bool
    has_record: bool = False
    has_statement: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def score(sources: Iterable[Source]) -> Score:
    sources = list({s.id: s for s in sources}.values())  # one vote per outlet
    outlets = [s for s in sources if s.type != "primary"]
    leans = sorted({s.lean for s in outlets if s.lean in SPECTRUM}, key=SPECTRUM.index)
    types = sorted({s.type for s in outlets if s.type in OUTLET_TYPES}, key=OUTLET_TYPES.index)
    has_record = any(s.type == "primary" and s.role == "record" for s in sources)
    has_statement = any(s.type == "primary" and s.role != "record" for s in sources)
    has_primary = has_record or has_statement

    parts = {
        "breadth": len(leans) / len(SPECTRUM),
        "coverage": min(math.log2(1 + sum(s.weight for s in outlets)) / math.log2(1 + COVERAGE_CAP), 1.0),
        "diversity": min(len(types) / 3, 1.0),
        "record": 1.0 if has_record else 0.0,
    }
    total = sum(WEIGHTS[k] * v for k, v in parts.items())
    return Score(
        total=round(total, 3),
        **{k: round(v, 3) for k, v in parts.items()},
        outlets=len(outlets),
        leans=leans,
        types=types,
        has_primary=has_primary,
        has_record=has_record,
        has_statement=has_statement,
    )


def lane(sc: Score, threshold: str = "standard", official: bool = True) -> str | None:
    """'main' (covered across outlets), 'official' (on the record, little coverage), or None."""
    if sc.outlets >= MIN_OUTLETS and sc.total >= THRESHOLDS[threshold]:
        return "main"
    if sc.has_primary and official:
        return "official"
    return None


def is_candidate(sc: Score) -> bool:
    """Worth writing up at all: passes the loosest setting a reader could pick."""
    return lane(sc, threshold="broad", official=True) is not None


# No sports in the edition, for now (roadmap D8). An article counts as sports when a
# whole part of its URL path is one of these sections: outlets file sports there, and
# guessing from words would catch real news (a sanctions story that mentions the NBA).
SPORTS_SECTIONS = ("sport", "sports", "football")  # football: The Guardian's soccer section
# A headline with one of these is news that happens to involve sports: a vote, a law, a
# court, a crime. They can only keep a story, never drop one. Some are phrases because
# sports pages use the bare word for something else ("ruled out", "Aaron Judge", "Barry Bonds").
HARD_NEWS_WORDS = (
    "antitrust", "appeals court", "arrested", "ballot", "bond measure", "bond vote", "charged", "charges",
    "city council", "congress", "convicted", "federal court", "federal judge", "governor", "guilty", "indicted",
    "law", "laws", "lawmakers", "lawsuit", "lawsuits", "legislation", "legislature", "mayor", "police",
    "prosecutors", "referendum", "ruling", "senate", "sentenced", "sue", "sued", "sues", "supreme court",
    "taxpayers", "voters",
)
_HARD_NEWS = re.compile(r"\b(?:" + "|".join(HARD_NEWS_WORDS) + r")\b", re.I)


def in_sports_section(url: str) -> bool:
    return any(part.lower() in SPORTS_SECTIONS for part in urlsplit(url).path.split("/"))


def is_sports(group: list, sources: dict[str, Source]) -> bool:
    """Leave this group of articles out? Only if more than half of its outlets filed it
    only in sports sections, no official source is in it, and no headline is hard news.
    A false drop silently loses real news, so every doubt keeps the group."""
    if any(sources[a.source_id].type == "primary" for a in group):
        return False
    if any(_HARD_NEWS.search(a.title) for a in group):
        return False
    outlets = {a.source_id for a in group}
    sports = {o for o in outlets if all(in_sports_section(a.url) for a in group if a.source_id == o)}
    return len(sports) * 2 > len(outlets)
