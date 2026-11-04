"""Yesterday's market closes for the ticker, from FRED (St. Louis Fed).

Once a day, like everything else: each series' latest close and its change
from the close before. No intraday prices, no streaming.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from . import config

FRED_API = "https://api.stlouisfed.org/fred/series/observations"
TIMEOUT = 20


def load_series(path: Path | None = None) -> list[dict]:
    data = yaml.safe_load(Path(path or config.MARKETS_PATH).read_text()) or {}
    return data.get("series") or []


def summarize(spec: dict, observations: list[tuple[str, float]]) -> dict | None:
    """Latest close and change from the previous one. `observations` newest first."""
    if len(observations) < 2:
        return None
    (day, value), (_, prev) = observations[0], observations[1]
    item = {
        "id": spec["id"], "label": spec["label"], "kind": spec.get("kind", "index"),
        "date": day, "value": value, "previous": prev,
        "decimals": spec.get("decimals", 2), "prefix": spec.get("prefix", ""), "suffix": spec.get("suffix", ""),
        "source_url": f"https://fred.stlouisfed.org/series/{spec['id']}",
    }
    if item["kind"] == "rate":
        item["change"] = round(value - prev, 4)          # percentage points
    else:
        item["change"] = round((value - prev) / prev * 100, 4) if prev else 0.0  # percent
    return item


def parse_fred(data: dict) -> list[tuple[str, float]]:
    """FRED marks missing days (holidays) with '.'; skip them. Newest first."""
    out = []
    for o in data.get("observations", []):
        if o.get("value") not in (None, "", "."):
            out.append((o["date"], float(o["value"])))
    return sorted(out, reverse=True)


def fetch(series: list[dict], key: str | None = None) -> tuple[list[dict], list[str]]:
    """Returns (ticker items, problems). Never raises: a missing ticker never blocks an edition."""
    key = key or os.environ.get("FRED_API_KEY")
    if not key:
        return [], ["FRED_API_KEY not set; ticker skipped (free key: https://fred.stlouisfed.org/docs/api/api_key.html)"]
    items, problems = [], []
    for spec in series:
        params = {"series_id": spec["id"], "api_key": key, "file_type": "json",
                  "sort_order": "desc", "limit": 10}
        try:
            req = urllib.request.Request(f"{FRED_API}?{urllib.parse.urlencode(params)}",
                                         headers={"User-Agent": "BoringNewsBot/0.1"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                item = summarize(spec, parse_fred(json.loads(resp.read().decode("utf-8"))))
            if item:
                items.append(item)
            else:
                problems.append(f"{spec['id']}: not enough recent data")
        except Exception as exc:
            problems.append(f"{spec['id']}: {exc}")
    return items, problems


def load_fixture(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    by_id = {s["id"]: s for s in load_series()}
    items = []
    for row in data["series"]:
        spec = by_id.get(row["id"], {"id": row["id"], "label": row["id"]})
        item = summarize(spec, [(row["date"], row["value"]), (row["previous_date"], row["previous"])])
        if item:
            items.append(item)
    return items
