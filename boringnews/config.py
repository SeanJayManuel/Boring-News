"""Paths and settings. Everything can be overridden with environment variables."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("BN_DB", ROOT / "data" / "boringnews.db"))
SOURCES_PATH = Path(os.environ.get("BN_SOURCES", ROOT / "sources.yaml"))
FIXTURE_SOURCES_PATH = ROOT / "fixtures" / "sources.yaml"
FIXTURE_ARTICLES_PATH = ROOT / "fixtures" / "articles.json"
FIXTURE_REWRITES_PATH = ROOT / "fixtures" / "rewrites.json"
STYLE_GUIDE_PATH = ROOT / "editorial" / "style_guide.md"
BANNED_WORDS_PATH = ROOT / "editorial" / "banned_words.txt"

# Public base URL, used for links inside RSS feeds.
BASE_URL = os.environ.get("BN_BASE_URL", "http://localhost:8000").rstrip("/")

# Model used to write neutral summaries. A small model is enough for this job.
MODEL = os.environ.get("BN_MODEL", "claude-haiku-5-5")

# How far back an edition looks for articles, and how close in time two
# articles must be to be considered the same story.
LOOKBACK_HOURS = int(os.environ.get("BN_LOOKBACK_HOURS", "36"))
CLUSTER_WINDOW_HOURS = int(os.environ.get("BN_CLUSTER_WINDOW_HOURS", "48"))
CLUSTER_SIMILARITY = float(os.environ.get("BN_CLUSTER_SIMILARITY", "0.15"))
