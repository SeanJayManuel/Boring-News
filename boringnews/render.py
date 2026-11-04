"""Render the reader page. The page is one self-contained HTML file: the
edition's stories, the source list and the rubric are embedded as JSON, and
static/app.js filters them by the reader's preferences in the browser."""

from __future__ import annotations

import json

from . import config, rubric
from .db import Story
from .sources import Source
from .topics import REGIONS, TOPICS

WEB = config.ROOT / "web"


def page_data(edition_date: str, editions: list[str], stories: list[Story],
              sources: dict[str, Source], base_url: str, sample: bool = False) -> dict:
    used = {a.source_id for s in stories for a in s.articles}
    return {
        "edition": edition_date,
        "editions": editions,
        "sample": sample,
        "base_url": base_url,
        "rubric": {
            "version": rubric.VERSION,
            "weights": rubric.WEIGHTS,
            "thresholds": rubric.THRESHOLDS,
            "coverage_cap": rubric.COVERAGE_CAP,
            "min_outlets": rubric.MIN_OUTLETS,
        },
        "topics": TOPICS,
        "regions": REGIONS,
        "sources": {
            sid: {"name": s.name, "lean": s.lean, "type": s.type}
            for sid, s in sources.items()
            if sid in used or not sample
        },
        "stories": [
            {
                "id": s.id,
                "headline": s.headline,
                "bullets": s.bullets,
                "whats_next": s.whats_next,
                "topic": s.topic,
                "region": s.region,
                "written_by": s.written_by,
                "articles": [
                    {"source_id": a.source_id, "title": a.title, "url": a.url, "published_at": a.published_at}
                    for a in s.articles
                ],
            }
            for s in stories
        ],
    }


def render_page(data: dict) -> str:
    template = (WEB / "index.html").read_text()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (
        template.replace("/*__CSS__*/", (WEB / "style.css").read_text())
        .replace("/*__APP__*/", (WEB / "app.js").read_text())
        .replace('"__DATA__"', payload)
    )
