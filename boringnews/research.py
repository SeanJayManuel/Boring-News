"""The research index behind the Research tab: the last 30 days of editions in
one small file, so coverage lookup and records search run in the browser.

    stories  every story: date, headline, bullets, category, thread, and each
             source article (outlet, headline, link)
    records  every item from a government source, with whether any news
             outlet covered the same story

Scores aren't stored here; the page computes them with web/core.js, the same
code as everywhere else.
"""

from __future__ import annotations

from .db import editions, load_edition
from .sources import Source

DAYS = 30


def build(conn, sources: dict[str, Source], days: int = DAYS) -> dict:
    dates = editions(conn)[:days]
    stories, records = [], []
    for d in dates:
        for s in load_edition(conn, d):
            key = f"{d}-{s.id}"
            arts = [a for a in s.articles if a.source_id in sources]
            outlets = [a for a in arts if sources[a.source_id].type != "primary"]
            stories.append({
                "key": key, "id": s.id, "date": d, "headline": s.headline, "bullets": s.bullets,
                "topic": s.topic, "day": s.day, "thread_id": s.thread_id,
                "articles": [{"source_id": a.source_id, "title": a.title, "url": a.url} for a in arts],
            })
            for a in arts:
                src = sources[a.source_id]
                if src.type != "primary":
                    continue
                records.append({
                    "date": d, "published_at": a.published_at, "source_id": a.source_id,
                    "role": src.role, "title": a.title, "summary": a.summary, "url": a.url,
                    "story": key, "story_headline": s.headline, "outlets": len(outlets),
                })
    return {"days": dates, "stories": stories, "records": records}
