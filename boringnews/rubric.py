"""The selection rubric: which story clusters make the edition, and why.

This file is the editorial policy in code. It is published on the
"How we choose" page, and the web page applies the same rules in JavaScript
(static/app.js) so readers can change the threshold or drop sources.

    score = 0.50 * breadth + 0.35 * coverage + 0.15 * diversity

breadth   share of left / center / right that covered the story (0, 1/3, 2/3, 1)
coverage  distinct outlets, log-scaled, capped at 10 outlets
diversity distinct outlet types (wire, national, regional, international) / 3, capped at 1

A story needs score >= threshold AND at least two outlets. Items that come from
primary sources (rules, court opinions, official releases) but that few outlets
covered go to the "underreported" lane instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Iterable

from .sources import Source

VERSION = "0.1"
WEIGHTS = {"breadth": 0.50, "coverage": 0.35, "diversity": 0.15}
THRESHOLDS = {"broad": 0.35, "standard": 0.50, "strict": 0.65}
COVERAGE_CAP = 10
MIN_OUTLETS = 2
SPECTRUM = ("left", "center", "right")
OUTLET_TYPES = ("wire", "national", "regional", "international")


@dataclass
class Score:
    total: float
    breadth: float
    coverage: float
    diversity: float
    outlets: int
    leans: list[str]
    types: list[str]
    has_primary: bool

    def to_dict(self) -> dict:
        return asdict(self)


def score(sources: Iterable[Source]) -> Score:
    sources = list({s.id: s for s in sources}.values())  # one vote per outlet
    outlets = [s for s in sources if s.type != "primary"]
    leans = sorted({s.lean for s in outlets if s.lean in SPECTRUM}, key=SPECTRUM.index)
    types = sorted({s.type for s in outlets if s.type in OUTLET_TYPES}, key=OUTLET_TYPES.index)

    breadth = len(leans) / len(SPECTRUM)
    coverage = min(math.log2(1 + len(outlets)) / math.log2(1 + COVERAGE_CAP), 1.0)
    diversity = min(len(types) / 3, 1.0)
    total = (
        WEIGHTS["breadth"] * breadth
        + WEIGHTS["coverage"] * coverage
        + WEIGHTS["diversity"] * diversity
    )
    return Score(
        total=round(total, 3),
        breadth=round(breadth, 3),
        coverage=round(coverage, 3),
        diversity=round(diversity, 3),
        outlets=len(outlets),
        leans=leans,
        types=types,
        has_primary=any(s.type == "primary" for s in sources),
    )


def lane(sc: Score, threshold: str = "standard", underreported: bool = True) -> str | None:
    """Return 'main', 'underreported', or None if the story doesn't make the edition."""
    if sc.outlets >= MIN_OUTLETS and sc.total >= THRESHOLDS[threshold]:
        return "main"
    if sc.has_primary and underreported:
        return "underreported"
    return None


def is_candidate(sc: Score) -> bool:
    """Worth writing up at all: passes the loosest setting a reader could pick."""
    return lane(sc, threshold="broad", underreported=True) is not None


def explain(sc: Score) -> str:
    """One plain line telling the reader why the story is here."""
    if sc.outlets == 0 and sc.has_primary:
        return "From a primary source; little or no news coverage yet."
    if not sc.leans:
        spectrum = "no rated outlets"
    elif len(sc.leans) == 3:
        spectrum = "left, center and right"
    else:
        spectrum = " and ".join(sc.leans) + " only"
    outlet_word = "outlet" if sc.outlets == 1 else "outlets"
    return f"Covered by {sc.outlets} {outlet_word} ({spectrum}). Score {sc.total:.2f}."
