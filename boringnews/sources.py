"""Load the source list (outlets and official sources, their lean and type)."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field, replace
from pathlib import Path

import yaml

LEANS = ("left", "center", "right", "unrated")
TYPES = ("wire", "national", "regional", "international", "primary")
FETCHERS = ("rss", "federal_register", "congress", "fixture")
# For official sources only. A record has legal or statistical standing (a law,
# a rule, a court ruling, a vote, official statistics) and adds to a story's
# score. A statement is an institution describing its own work (a press
# release); it is listed but never adds to the score.
ROLES = ("record", "statement")

# Lean from published ratings. Each rating service's label maps to a number;
# the average decides the bucket. Lets the source list cite several raters
# instead of one, and shows the inputs on the site.
RATING_SCALE = {"left": -2, "lean left": -1, "center": 0, "lean right": 1, "right": 2}


def lean_from_ratings(ratings: dict[str, str]) -> str:
    values = [RATING_SCALE[v.lower()] for v in ratings.values()]
    mean = sum(values) / len(values)
    if mean <= -0.5:
        return "left"
    if mean >= 0.5:
        return "right"
    return "center"


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    url: str
    lean: str
    type: str
    fetcher: str = "rss"          # how to read it: rss, federal_register, congress
    topic: str | None = None      # default topic for items from this source
    max_items: int | None = None  # cap per edition (official sources can be very busy)
    role: str | None = None       # official sources only: record or statement
    ratings: dict = field(default_factory=dict, hash=False, compare=False)  # rater -> label
    weight: float = 1.0           # coverage weight; balances sides with more outlets on the list
    params: dict = field(default_factory=dict, hash=False, compare=False)

    def to_dict(self) -> dict:
        return asdict(self)


def load_sources(path: Path) -> dict[str, Source]:
    data = yaml.safe_load(Path(path).read_text())
    out: dict[str, Source] = {}
    for raw in data.get("sources", []):
        ratings = raw.get("ratings") or {}
        for rater, label in ratings.items():
            if str(label).lower() not in RATING_SCALE:
                raise ValueError(f"{raw['id']}: rating {rater}={label!r} must be one of {list(RATING_SCALE)}")
        src = Source(
            id=raw["id"],
            name=raw["name"],
            url=raw.get("url", ""),
            lean=lean_from_ratings(ratings) if ratings else raw.get("lean", "unrated"),
            type=raw.get("type", "national"),
            fetcher=raw.get("fetcher", "fixture" if raw.get("url") == "fixture" else "rss"),
            topic=raw.get("topic"),
            max_items=raw.get("max_items"),
            params=raw.get("params") or {},
            # Official sources must earn the record boost explicitly.
            role=(raw.get("role") or "statement") if raw.get("type") == "primary" else None,
            ratings=ratings,
        )
        if src.lean not in LEANS:
            raise ValueError(f"{src.id}: unknown lean {src.lean!r} (use one of {LEANS})")
        if src.type not in TYPES:
            raise ValueError(f"{src.id}: unknown type {src.type!r} (use one of {TYPES})")
        if src.fetcher not in FETCHERS:
            raise ValueError(f"{src.id}: unknown fetcher {src.fetcher!r} (use one of {FETCHERS})")
        if src.role is not None and src.role not in ROLES:
            raise ValueError(f"{src.id}: unknown role {src.role!r} (use one of {ROLES})")
        if src.id in out:
            raise ValueError(f"duplicate source id {src.id!r}")
        out[src.id] = src
    return balance(out)


def balance(sources: dict[str, Source]) -> dict[str, Source]:
    """Weight rated outlets so each side counts equally toward coverage,
    however many outlets of that lean are on the list. With 4 left, 3 center
    and 3 right outlets, a left outlet counts 0.83 and the others 1.11."""
    rated = [s for s in sources.values() if s.type != "primary" and s.lean in ("left", "center", "right")]
    counts = {lean: sum(1 for s in rated if s.lean == lean) for lean in ("left", "center", "right")}
    per_side = len(rated) / 3 if rated else 0
    out = {}
    for sid, s in sources.items():
        if s in rated and counts[s.lean]:
            s = replace(s, weight=round(per_side / counts[s.lean], 4))
        out[sid] = s
    return out
