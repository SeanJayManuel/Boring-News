"""Reader preferences. They live in the URL query string so a custom feed is
just a link, and the same parameters drive the web page and /feed.xml.

    topics=economy,courts        only these topics (empty = all)
    exclude=ny-post,npr          drop these sources, then re-score every story
    threshold=broad|standard|strict
    official=1|0                 include official items no outlet covered
    statements=1|0               include official statements (press releases)
    spotlight=1                  only the top 5 stories (default: the full edition)
    length=full|headlines

web/app.js implements the same rules for the web page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlencode

from . import rubric
from .db import Story
from .sources import Source
from .topics import TOPICS

FALSE = ("0", "false", "no")


def _csv(value: str | None, allowed=None) -> list[str]:
    items = [v.strip() for v in (value or "").split(",") if v.strip()]
    if allowed is not None:
        items = [v for v in items if v in allowed]
    return sorted(set(items))


@dataclass
class Prefs:
    topics: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    threshold: str = "standard"
    official: bool = True
    statements: bool = True
    spotlight: bool = False
    length: str = "full"

    @classmethod
    def from_query(cls, q) -> "Prefs":
        threshold = q.get("threshold") or "standard"
        length = q.get("length") or "full"
        return cls(
            topics=_csv(q.get("topics"), TOPICS),
            exclude=_csv(q.get("exclude")),
            threshold=threshold if threshold in rubric.THRESHOLDS else "standard",
            official=(q.get("official") or "1") not in FALSE,
            statements=(q.get("statements") or "1") not in FALSE,
            spotlight=(q.get("spotlight") or "0") not in FALSE,
            length=length if length in ("full", "headlines") else "full",
        )

    def to_query(self) -> str:
        """Only non-default values, so the default feed URL stays clean."""
        q = {}
        if self.topics:
            q["topics"] = ",".join(self.topics)
        if self.exclude:
            q["exclude"] = ",".join(self.exclude)
        if self.threshold != "standard":
            q["threshold"] = self.threshold
        if not self.official:
            q["official"] = "0"
        if not self.statements:
            q["statements"] = "0"
        if self.spotlight:
            q["spotlight"] = "1"
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
    """Filter, score and order an edition for one reader: highest score first."""
    out = []
    excluded = set(prefs.exclude)
    if not prefs.statements:
        excluded |= {sid for sid, src in sources.items() if src.type == "primary" and src.role != "record"}
    for s in stories:
        if prefs.topics and s.topic not in prefs.topics:
            continue
        kept = [a for a in s.articles if a.source_id in sources and a.source_id not in excluded]
        if not kept:
            continue
        sc = rubric.score(sources[a.source_id] for a in kept)
        ln = rubric.lane(sc, prefs.threshold, prefs.official)
        if ln is None:
            continue
        out.append(Selected(s, ln, sc, rubric.explain(sc), kept))
    out.sort(key=lambda x: (-x.score.total, x.story.id or 0))
    if prefs.spotlight:
        out = [x for x in out if x.lane == "main"][: rubric.SPOTLIGHT]
    return out
