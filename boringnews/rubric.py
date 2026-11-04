"""The selection rubric: which stories make the edition, and why.

This file is the editorial policy in code. It is published on the
"How it works" page, and the web page applies the same rules in JavaScript
(web/app.js) so readers can change the threshold or drop sources.

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

v0.4 (2026-11-04): coverage counts weighted outlets (each side counts equally).
v0.3 (2026-11-04): only official records earn `record`; statements are listed
but add nothing, so an administration's press releases can't lift a story.
v0.2 (2026-11-04): added `record`, so stories backed by an official source
rank higher; thresholds recalibrated for the new weights.
v0.1 (2026-11-04): breadth 0.50, coverage 0.35, diversity 0.15.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Iterable

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


def explain(sc: Score) -> str:
    """One plain line telling the reader why the story is here."""
    if sc.outlets == 0 and sc.has_primary:
        if sc.has_record:
            return "A government record; no news coverage yet."
        return "A government statement; no news coverage yet."
    if not sc.leans:
        spectrum = "no rated outlets"
    elif len(sc.leans) == 1:
        spectrum = sc.leans[0]
    else:
        spectrum = ", ".join(sc.leans[:-1]) + " and " + sc.leans[-1]
    record = " Backed by a government record." if sc.has_record else ""
    outlet_word = "outlet" if sc.outlets == 1 else "outlets"
    return f"{sc.outlets} {outlet_word} across {spectrum}.{record} Score {sc.total:.2f}."
