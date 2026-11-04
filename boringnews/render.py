"""Render the reader page. The page is one self-contained HTML file: the
edition's stories, the source list and the rubric are embedded as JSON, and
static/app.js filters them by the reader's preferences in the browser."""

from __future__ import annotations

import json

import yaml

from . import config, rubric
from .db import Story
from .sources import Source
from .topics import REGIONS, TOPICS

WEB = config.ROOT / "web"


def load_corrections() -> list[dict]:
    if not config.CORRECTIONS_PATH.exists():
        return []
    data = yaml.safe_load(config.CORRECTIONS_PATH.read_text()) or {}
    return [{k: str(v) for k, v in c.items()} for c in (data.get("corrections") or [])]


def page_data(edition_date: str, editions: list[str], stories: list[Story],
              sources: dict[str, Source], base_url: str, sample: bool = False,
              data_url: str | None = None, markets: list[dict] | None = None) -> dict:
    return {
        "edition": edition_date,
        "editions": editions,
        "sample": sample,
        "base_url": base_url,
        "repo_url": config.REPO_URL,
        "data_url": data_url,
        "corrections": load_corrections(),
        "markets": markets or [],
        "rubric": {
            "version": rubric.VERSION,
            "weights": rubric.WEIGHTS,
            "thresholds": rubric.THRESHOLDS,
            "coverage_cap": rubric.COVERAGE_CAP,
            "min_outlets": rubric.MIN_OUTLETS,
            "spotlight": rubric.SPOTLIGHT,
        },
        "topics": TOPICS,
        "regions": REGIONS,
        "sources": {
            sid: {"name": s.name, "lean": s.lean, "type": s.type, "role": s.role,
                  "weight": s.weight, "ratings": s.ratings}
            for sid, s in sources.items()
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
                "checks": s.checks,
                "thread_id": s.thread_id,
                "day": s.day,
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
        .replace("/*__CORE__*/", (WEB / "core.js").read_text())
        .replace("/*__APP__*/", (WEB / "app.js").read_text())
        .replace('"__DATA__"', payload)
    )
