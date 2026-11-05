"""The reader site.

    uvicorn boringnews.web:app --reload

Routes
    /                       today's edition (or ?date=YYYY-MM-DD); settings read from the query string
    /feed.xml               RSS, filtered by the same query parameters (needs node)
    /api/edition.json       the edition as JSON (same data the page embeds)
    /api/docs.md            the public API docs
    /healthz                liveness check
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from . import config, research
from .db import connect
from .edition import Edition, NoEdition
from .reader import feeds
from .render import load_corrections, render_page
from .sources import load_sources

SAMPLE = os.environ.get("BN_SAMPLE") == "1"
app = FastAPI(title="Standard Edition", docs_url=None, redoc_url=None)


def _edition(date: str | None) -> Edition:
    conn = connect(config.DB_PATH)
    try:
        return Edition.load(conn, load_sources(config.sources_path(SAMPLE)), date)
    except NoEdition as exc:
        raise HTTPException(404, str(exc))
    finally:
        conn.close()


def _page_data(date: str | None, research_url: str | None = None) -> dict:
    return _edition(date).page_data(config.BASE_URL, sample=SAMPLE, corrections=load_corrections(),
                                    research_url=research_url)


@app.get("/", response_class=HTMLResponse)
def index(date: str | None = Query(None)):
    return render_page(_page_data(date, research_url="research.json"))


@app.get("/api/edition.json")
def edition_json(date: str | None = Query(None)):
    return JSONResponse(_page_data(date))


@app.get("/feed.xml")
def feed(request: Request, date: str | None = None):
    xml = feeds(_page_data(date), [request.url.query])[0]
    return Response(xml, media_type="application/rss+xml; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=900"})


@app.get("/research.json")
def research_json():
    conn = connect(config.DB_PATH)
    try:
        return JSONResponse(research.build(conn, load_sources(config.sources_path(SAMPLE))))
    finally:
        conn.close()


@app.get("/api/docs.md", response_class=PlainTextResponse)
def api_docs():
    return (config.ROOT / "docs" / "api.md").read_text()


@app.get("/healthz")
def healthz():
    return {"ok": True}
