"""The reader site.

    uvicorn boringnews.web:app --reload

Routes
    /                       today's edition (or ?date=YYYY-MM-DD); prefs read from the query string
    /feed.xml               RSS, filtered by the same query parameters
    /api/edition.json       the edition as JSON (same data the page embeds)
    /healthz                liveness check
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response

from . import config
from .db import connect, editions, load_edition
from .feeds import render_rss
from .prefs import Prefs, apply
from .render import page_data, render_page
from .sources import load_sources

SAMPLE = os.environ.get("BN_SAMPLE") == "1"
app = FastAPI(title="Boring News", docs_url=None, redoc_url=None)


def _sources():
    return load_sources(config.FIXTURE_SOURCES_PATH if SAMPLE else config.SOURCES_PATH)


def _edition(date: str | None):
    conn = connect(config.DB_PATH)
    try:
        all_dates = editions(conn)
        if not all_dates:
            raise HTTPException(404, "No editions yet. Run: python -m boringnews.pipeline run")
        d = date or all_dates[0]
        if d not in all_dates:
            raise HTTPException(404, f"No edition for {d}")
        return d, all_dates, load_edition(conn, d)
    finally:
        conn.close()


@app.get("/", response_class=HTMLResponse)
def index(date: str | None = Query(None)):
    d, all_dates, stories = _edition(date)
    return render_page(page_data(d, all_dates, stories, _sources(), config.BASE_URL, sample=SAMPLE))


@app.get("/api/edition.json")
def edition_json(date: str | None = Query(None)):
    d, all_dates, stories = _edition(date)
    return JSONResponse(page_data(d, all_dates, stories, _sources(), config.BASE_URL, sample=SAMPLE))


@app.get("/feed.xml")
def feed(
    date: str | None = None,
    topics: str | None = None,
    regions: str | None = None,
    exclude: str | None = None,
    threshold: str = "standard",
    official: str = "1",
    statements: str = "1",
    spotlight: str = "0",
    length: str = "full",
):
    prefs = Prefs.from_query({
        "topics": topics, "regions": regions, "exclude": exclude,
        "threshold": threshold, "official": official, "statements": statements, "spotlight": spotlight, "length": length,
    })
    d, _, stories = _edition(date)
    sources = _sources()
    xml = render_rss(d, apply(stories, sources, prefs), sources, prefs, config.BASE_URL)
    return Response(xml, media_type="application/rss+xml; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=900"})


@app.get("/healthz")
def healthz():
    return {"ok": True}
