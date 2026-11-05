"""Where an edition's articles and market closes come from. A run takes one of
these; both give the same shapes, so `pipeline.run` has one path and tests can
hand it their own failing sources.

    articles(since) -> (articles, [FeedHealth])
    markets()       -> (closes, [problem text])
"""

from __future__ import annotations

from datetime import datetime

from . import config, markets
from .db import Article
from .ingest import FeedHealth, fetch_all, load_fixtures
from .sources import Source


class LiveInputs:
    def __init__(self, sources: dict[str, Source]):
        self.sources = sources

    def articles(self, since: datetime | None = None) -> tuple[list[Article], list[FeedHealth]]:
        return fetch_all(self.sources, since=since)

    def markets(self) -> tuple[list[dict], list[str]]:
        return markets.fetch(markets.load_series())


class FixtureInputs:
    """The invented sample data."""

    def __init__(self, sources: dict[str, Source]):
        self.sources = sources

    def articles(self, since: datetime | None = None) -> tuple[list[Article], list[FeedHealth]]:
        return load_fixtures(config.FIXTURE_ARTICLES_PATH), []

    def markets(self) -> tuple[list[dict], list[str]]:
        return markets.load_fixture(config.FIXTURE_MARKETS_PATH), []
