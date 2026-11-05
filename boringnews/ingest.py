"""Fetch articles from news RSS feeds and straight from government sources.

Fetchers (set per source in sources.yaml with `fetcher:`):
  rss               any RSS/Atom feed (news outlets, White House, Department of War, govinfo)
  federal_register  Federal Register API, no key needed; filter by document type and significance
  congress          Congress.gov API, needs a free key in CONGRESS_API_KEY (api.congress.gov/sign-up);
                    keeps only bills with a meaningful action (passed, signed, vetoed...)
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import mktime

import feedparser

from .db import Article
from .sources import Source

USER_AGENT = "BoringNewsBot/0.1 (daily digest; links to every source)"
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
STALE_AFTER_DAYS = 14
TIMEOUT = 20


@dataclass
class FeedHealth:
    source_id: str
    ok: bool
    items: int
    error: str | None = None
    newest: str | None = None   # ISO date of the newest item
    stale: bool = False         # newest item older than STALE_AFTER_DAYS


def clean(text: str | None, limit: int = 600) -> str:
    """Strip HTML, collapse whitespace, and trim. We only keep a short snippet."""
    text = html.unescape(TAG_RE.sub(" ", text or ""))
    text = WS_RE.sub(" ", text).strip()
    return text[:limit]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _noon_utc(day: str) -> str:
    """'2026-11-04' -> '2026-11-04T12:00:00+00:00' for sources that only give a date."""
    return f"{day[:10]}T12:00:00+00:00"


def _get_json(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------- RSS

def _published(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return _iso(datetime.fromtimestamp(mktime(t), tz=timezone.utc))
    return _iso(datetime.now(timezone.utc))


def fetch_rss(src: Source, since: datetime) -> list[Article]:
    parsed = feedparser.parse(src.url, agent=USER_AGENT)
    if parsed.get("bozo") and not parsed.entries:
        raise RuntimeError(str(parsed.get("bozo_exception", "unreadable feed")))
    out = []
    for e in parsed.entries:
        url, title = e.get("link"), clean(e.get("title"), 300)
        if url and title:
            out.append(Article(src.id, url, title, clean(e.get("summary") or e.get("description")), _published(e)))
    return out


# ---------------------------------------------------------------- Federal Register

FR_API = "https://www.federalregister.gov/api/v1/documents.json"
FR_FIELDS = ["title", "abstract", "html_url", "publication_date", "agencies", "type", "document_number"]


def federal_register_items(data: dict, source_id: str) -> list[Article]:
    out = []
    for doc in data.get("results", []):
        agencies = ", ".join(a.get("name", "") for a in doc.get("agencies", []) if a.get("name"))
        summary = clean(doc.get("abstract") or "")
        if agencies:
            summary = f"{doc.get('type', 'Document')} from {agencies}. {summary}".strip()
        out.append(Article(source_id, doc["html_url"], clean(doc["title"], 300), summary[:600],
                           _noon_utc(doc["publication_date"])))
    return out


def fetch_federal_register(src: Source, since: datetime) -> list[Article]:
    p = src.params
    params = {
        "conditions[publication_date][gte]": since.date().isoformat(),
        "conditions[type][]": p.get("types", ["RULE"]),
        "per_page": 100,
        "order": "newest",
        "fields[]": FR_FIELDS,
    }
    if p.get("significant"):
        params["conditions[significant]"] = 1
    return federal_register_items(_get_json(FR_API, params), src.id)


# ---------------------------------------------------------------- Congress.gov

CONGRESS_API = "https://api.congress.gov/v3/bill"
CONGRESS_PAGE = 250       # the most the API returns at once
CONGRESS_MAX_BILLS = 5000  # a limit on a runaway loop, far above a day's changes
# Only actions a general reader would want to know about. Introductions and
# committee referrals happen by the hundred every day; they are skipped.
SIGNIFICANT_ACTION = re.compile(
    r"became public law|signed by (the )?president|presented to (the )?president|vetoed|veto message"
    r"|passed (the )?(house|senate)|passed/agreed to in (house|senate)|agreed to in (the )?(house|senate)"
    r"|cloture .*(invoked|not invoked)|failed of passage|conference report",
    re.I,
)
BILL_PATH = {
    "HR": "house-bill", "S": "senate-bill",
    "HJRES": "house-joint-resolution", "SJRES": "senate-joint-resolution",
    "HCONRES": "house-concurrent-resolution", "SCONRES": "senate-concurrent-resolution",
    "HRES": "house-resolution", "SRES": "senate-resolution",
}
BILL_LABEL = {"HR": "H.R.", "S": "S.", "HJRES": "H.J.Res.", "SJRES": "S.J.Res.",
              "HCONRES": "H.Con.Res.", "SCONRES": "S.Con.Res.", "HRES": "H.Res.", "SRES": "S.Res."}


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def bill_summary(data: dict) -> str:
    """The newest Congressional Research Service summary, labeled with the bill
    version it describes, which may be older than the bill's latest action."""
    summaries = sorted(data.get("summaries", []), key=lambda s: s.get("updateDate", ""))
    if not summaries:
        return ""
    latest = summaries[-1]
    return clean(f"Congressional Research Service summary ({latest.get('actionDesc', 'latest')}): {latest.get('text', '')}", 1200)


def congress_items(data: dict, source_id: str, since: datetime, summary_for=lambda bill: "") -> list[Article]:
    """`summary_for` is only called for bills that are kept, since each one is a request."""
    out = []
    for b in data.get("bills", []):
        action = b.get("latestAction") or {}
        text, day = action.get("text", ""), action.get("actionDate", "")
        if not day or day < since.date().isoformat() or not SIGNIFICANT_ACTION.search(text):
            continue
        btype, number, congress = b.get("type", "").upper(), b.get("number", ""), int(b.get("congress", 0))
        if btype not in BILL_PATH:
            continue
        url = f"https://www.congress.gov/bill/{_ordinal(congress)}-congress/{BILL_PATH[btype]}/{number}"
        label = f"{BILL_LABEL[btype]} {number}"
        summary = " ".join(filter(None, [clean(f"Latest action on {day}: {text}"), summary_for(b)]))
        out.append(Article(source_id, url, clean(f"{label}: {b.get('title', '')}", 300), summary, _noon_utc(day)))
    return out


def fetch_congress(src: Source, since: datetime) -> list[Article]:
    key = os.environ.get("CONGRESS_API_KEY")
    if not key:
        raise RuntimeError("CONGRESS_API_KEY not set (free key: https://api.congress.gov/sign-up/)")
    params = {
        "format": "json",
        "fromDateTime": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "toDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sort": "updateDate desc",
        "limit": CONGRESS_PAGE,
        "api_key": key,
    }
    bills = []
    for offset in range(0, CONGRESS_MAX_BILLS, CONGRESS_PAGE):
        page = _get_json(CONGRESS_API, {**params, "offset": offset}).get("bills", [])
        bills += page
        if len(page) < CONGRESS_PAGE:
            break

    def summary_for(bill: dict) -> str:
        url = f"{CONGRESS_API}/{bill['congress']}/{bill['type'].lower()}/{bill['number']}/summaries"
        try:
            return bill_summary(_get_json(url, {"format": "json", "api_key": key}))
        except (OSError, ValueError):  # a bill is still a record without its summary
            return ""

    return congress_items({"bills": bills}, src.id, since, summary_for)


# ---------------------------------------------------------------- dispatch

FETCHERS = {"rss": fetch_rss, "federal_register": fetch_federal_register, "congress": fetch_congress}


def fetch_source(src: Source, since: datetime) -> tuple[list[Article], FeedHealth]:
    fn = FETCHERS.get(src.fetcher)
    if fn is None:
        return [], FeedHealth(src.id, False, 0, f"no live fetcher for {src.fetcher!r}")
    try:
        articles = fn(src, since)
    except Exception as exc:  # network errors, bad URLs, missing keys
        return [], FeedHealth(src.id, False, 0, str(exc))
    newest = max((a.published_at for a in articles), default=None)
    stale = bool(newest) and newest < _iso(datetime.now(timezone.utc) - timedelta(days=STALE_AFTER_DAYS))
    # An official source with nothing new today is normal, not an error.
    ok = bool(articles) or src.type == "primary"
    return articles, FeedHealth(src.id, ok, len(articles), None if ok else "no items", newest[:10] if newest else None, stale)


def fetch_all(sources: dict[str, Source], since: datetime | None = None) -> tuple[list[Article], list[FeedHealth]]:
    since = since or datetime.now(timezone.utc) - timedelta(days=2)
    all_articles, health = [], []
    for src in sources.values():
        arts, h = fetch_source(src, since)
        all_articles.extend(arts)
        health.append(h)
    return all_articles, health


def load_fixtures(path: Path) -> list[Article]:
    data = json.loads(Path(path).read_text())
    return [
        Article(
            source_id=a["source_id"],
            url=a["url"],
            title=a["title"],
            summary=a.get("summary", ""),
            published_at=a["published_at"].replace("Z", "+00:00"),
        )
        for a in data["articles"]
    ]
