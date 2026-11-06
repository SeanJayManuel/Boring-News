"""Paths and settings. Everything can be overridden with environment variables."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("BN_DB", ROOT / "data" / "boringnews.db"))
ARCHIVE_DIR = Path(os.environ.get("BN_ARCHIVE", ROOT / "archive"))
CORRECTIONS_PATH = ROOT / "corrections.yaml"
LEDGER_PATH = ROOT / "LEDGER.md"
MARKETS_PATH = ROOT / "markets.yaml"
FIXTURE_MARKETS_PATH = ROOT / "fixtures" / "markets.json"
SOURCES_PATH = Path(os.environ.get("BN_SOURCES", ROOT / "sources.yaml"))
FIXTURE_SOURCES_PATH = ROOT / "fixtures" / "sources.yaml"
FIXTURE_ARTICLES_PATH = ROOT / "fixtures" / "articles.json"
FIXTURE_REWRITES_PATH = ROOT / "fixtures" / "rewrites.json"
STYLE_GUIDE_PATH = ROOT / "editorial" / "style_guide.md"
BANNED_WORDS_PATH = ROOT / "editorial" / "banned_words.txt"


def sources_path(sample: bool) -> Path:
    return FIXTURE_SOURCES_PATH if sample else SOURCES_PATH


# Public base URL, used for links inside RSS feeds.
BASE_URL = os.environ.get("BN_BASE_URL", "http://localhost:8000").rstrip("/")

# Where the code lives (linked from the page).
REPO_URL = os.environ.get("BN_REPO_URL", "https://github.com/SeanJayManuel/Boring-News")

# A private way to reach us, shown on the About page. Empty until the mailbox works.
CONTACT_EMAIL = os.environ.get("BN_CONTACT_EMAIL", "")

# Model used to write neutral summaries. A small model is enough for this job.
MODEL = os.environ.get("BN_MODEL", "claude-haiku-5-5")

# How far back an edition looks for articles, and how close in time two
# articles must be to be considered the same story.
LOOKBACK_HOURS = int(os.environ.get("BN_LOOKBACK_HOURS", "36"))
CLUSTER_WINDOW_HOURS = int(os.environ.get("BN_CLUSTER_WINDOW_HOURS", "48"))
# Two scales, so two settings. Both come from one day of real news: provisional (roadmap L6).
EMBEDDING_SIMILARITY = float(os.environ.get("BN_EMBEDDING_SIMILARITY", "0.60"))
WORD_SIMILARITY = float(os.environ.get("BN_WORD_SIMILARITY", "0.14"))
MODEL_CACHE = ROOT / "data" / "models"

# Two stories on consecutive days are the same developing story when their
# headlines and article titles are this similar, or when they share an article.
THREAD_SIMILARITY = float(os.environ.get("BN_THREAD_SIMILARITY", "0.25"))
