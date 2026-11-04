"""Load the source list (outlets and official sources, their lean and type)."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path

import yaml

LEANS = ("left", "center", "right", "unrated")
TYPES = ("wire", "national", "regional", "international", "primary")
FETCHERS = ("rss", "federal_register", "congress", "fixture")


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
    params: dict = field(default_factory=dict, hash=False, compare=False)

    def to_dict(self) -> dict:
        return asdict(self)


def load_sources(path: Path) -> dict[str, Source]:
    data = yaml.safe_load(Path(path).read_text())
    out: dict[str, Source] = {}
    for raw in data.get("sources", []):
        src = Source(
            id=raw["id"],
            name=raw["name"],
            url=raw.get("url", ""),
            lean=raw.get("lean", "unrated"),
            type=raw.get("type", "national"),
            fetcher=raw.get("fetcher", "fixture" if raw.get("url") == "fixture" else "rss"),
            topic=raw.get("topic"),
            max_items=raw.get("max_items"),
            params=raw.get("params") or {},
        )
        if src.lean not in LEANS:
            raise ValueError(f"{src.id}: unknown lean {src.lean!r} (use one of {LEANS})")
        if src.type not in TYPES:
            raise ValueError(f"{src.id}: unknown type {src.type!r} (use one of {TYPES})")
        if src.fetcher not in FETCHERS:
            raise ValueError(f"{src.id}: unknown fetcher {src.fetcher!r} (use one of {FETCHERS})")
        if src.id in out:
            raise ValueError(f"duplicate source id {src.id!r}")
        out[src.id] = src
    return out
