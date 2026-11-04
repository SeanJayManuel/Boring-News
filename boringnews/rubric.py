"""The selection rubric: which stories make the edition, and why.

This file is the editorial policy in code. It is published on the
"How it works" page, and the web page applies the same rules in JavaScript
(web/app.js) so readers can change the threshold or drop sources.

    score = 0.40 * breadth + 0.25 * coverage + 0.10 * diversity + 0.25 * record

breadth   share of left / center / right that covered the story (0, 1/3, 2/3, 1)
coverage  distinct outlets, log-scaled, capped at 10 outlets
diversity distinct outlet types (wire, national, regional, international) / 3, capped at 1
record    1 if an official source (Congress, an agency, a court) documents it, else 0

A story makes the edition with score >= threshold AND at least two outlets.
Official items that no outlet covered are listed too, under their topic,
because they matter whether or not anyone wrote about them.

The top SPOTLIGHT stories by score are the day's spotlight.

v0.2 (2026-11-04): added `record`, so stories backed by an official source
rank higher; thresholds recalibrated for the new weights.
v0.1 (2026-11-04): breadth 0.50, coverage 0.35, diversity 0.15.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Iterable

from .sources import Source

VERSION = "0.2"
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

    def to_dict(self) -> dict:
        return asdict(self)


def score(sources: Iterable[Source]) -> Score:
    sources = list({s.id: s for s in sources}.values())  # one vote per outlet
    outlets = [s for s in sources if s.type != "primary"]
    leans = sorted({s.lean for s in outlets if s.lean in SPECTRUM}, key=SPECTRUM.index)
    types = sorted({s.type for s in outlets if s.type in OUTLET_TYPES}, key=OUTLET_TYPES.index)
    has_primary = any(s.type == "primary" for s in sources)

    parts = {
        "breadth": len(leans) / len(SPECTRUM),
        "coverage": min(math.log2(1 + len(outlets)) / math.log2(1 + COVERAGE_CAP), 1.0),
        "diversity": min(len(types) / 3, 1.0),
        "record": 1.0 if has_primary else 0.0,
    }
    total = sum(WEIGHTS[k] * v for k, v in parts.items())
    return Score(
        total=round(total, 3),
        **{k: round(v, 3) for k, v in parts.items()},
        outlets=len(outlets),
        leans=leans,
        types=types,
        has_primary=has_primary,
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


def explain(sc: Score) -> str:
    """One plain line telling the reader why the story is here."""
    if sc.outlets == 0 and sc.has_primary:
        return "From an official source; no news coverage yet."
    if not sc.leans:
        spectrum = "no rated outlets"
    else:
        spectrum = ", ".join(sc.leans[:-1]) + (" and " if len(sc.leans) > 1 else "") + sc.leans[-1]
    record = " On the official record." if sc.has_primary else ""
    outlet_word = "outlet" if sc.outlets == 1 else "outlets"
    return f"{sc.outlets} {outlet_word} across {spectrum}.{record} Score {sc.total:.2f}."
