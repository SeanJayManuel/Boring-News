"""Reader preferences. They live in the URL query string so a custom feed is
just a link, and the same parameters drive the web page and /feed.xml.

    topics=economy,courts        only these topics (empty = all)
    regions=us-national,world    only these regions (empty = all)
    exclude=ny-post,npr          drop these outlets, then re-score
    threshold=broad|standard|strict
    underreported=1|0            include the primary-source lane
    length=full|headlines

static/app.js implements the same rules for the web page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlencode

from . import rubric
from .db import Story
from .sources import Source
from .topics import REGIONS, TOPICS


def _csv(value: str | None, allowed=None) -> list[str]:
    items = [v.strip() for v in (value or "").split(",") if v.strip()]
    if allowed is not None:
        items = [v for v in items if v in allowed]
    return sorted(set(items))


@dataclass
class Prefs:
    topics: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    threshold: str = "standard"
    underreported: bool = True
    length: str = "full"

    @classmethod
    def from_query(cls, q) -> "Prefs":
        threshold = q.get("threshold", "standard")
        length = q.get("length", "full")
        return cls(
            topics=_csv(q.get("topics"), TOPICS),
            regions=_csv(q.get("regions"), REGIONS),
            exclude=_csv(q.get("exclude")),
            threshold=threshold if threshold in rubric.THRESHOLDS else "standard",
            underreported=q.get("underreported", "1") not in ("0", "false", "no"),
            length=length if length in ("full", "headlines") else "full",
        )

    def to_query(self) -> str:
        """Only non-default values, so the default feed URL stays clean."""
        q = {}
        if self.topics:
            q["topics"] = ",".join(self.topics)
        if self.regions:
            q["regions"] = ",".join(self.regions)
        if self.exclude:
            q["exclude"] = ",".join(self.exclude)
        if self.threshold != "standard":
            q["threshold"] = self.threshold
        if not self.underreported:
            q["underreported"] = "0"
        if self.length != "full":
            q["length"] = self.length
        return urlencode(q, safe=",")


@dataclass
class Selected:
    story: Story
    lane: str
    score: rubric.Score
    why: str
    articles: list  # the story's articles after source exclusions


def apply(stories: list[Story], sources: dict[str, Source], prefs: Prefs) -> list[Selected]:
    """Filter and order an edition for one reader."""
    out = []
    for s in stories:
        if prefs.topics and s.topic not in prefs.topics:
            continue
        if prefs.regions and s.region not in prefs.regions:
            continue
        kept = [a for a in s.articles if a.source_id in sources and a.source_id not in prefs.exclude]
        if not kept:
            continue
        sc = rubric.score(sources[a.source_id] for a in kept)
        ln = rubric.lane(sc, prefs.threshold, prefs.underreported)
        if ln is None:
            continue
        out.append(Selected(s, ln, sc, rubric.explain(sc), kept))
    out.sort(key=lambda x: (x.lane != "main", -x.score.total, x.story.id or 0))
    return out
