"""The public data under api/v1/, and the only module that knows its layout.

Everything here is a plain file written at export, so it costs nothing to serve
and works on any host. functions/mcp.js reads these files; docs/api.md promises
what stays stable. Nothing here adds a new shape:

    index.json            every edition and file, with their addresses
    latest.json           the newest edition file
    editions/DATE.json    edition files, byte for byte (see edition.py)
    sources.json          the outlets and the rubric, as in edition files
    research.json         the index from research.py, with a version on top
    bulk/YYYY-MM.zip      each month's edition files

Bulk files are one a month rather than one for the archive: Cloudflare Pages
refuses a deploy holding any file over 25 MiB, and a single archive would reach
that in time. They're also repeatable, so a nightly deploy only uploads this
month's.
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from itertools import groupby
from pathlib import Path

from . import config
from .edition import FORMAT, Edition

API_VERSION = 1

_API = Path("api") / f"v{API_VERSION}"
_EDITION_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)  # the zip format's earliest date; file times would change the bytes

# Cloudflare joins a header that several rules set, so each file must match only
# one Cache-Control rule. These rules don't reach /mcp: _headers isn't applied to
# function responses, so functions/mcp.js sets its own.
_HEADERS = """\
/api/*
  Access-Control-Allow-Origin: *

/api/v1/index.json
  Cache-Control: public, max-age=900
/api/v1/latest.json
  Cache-Control: public, max-age=900
/api/v1/sources.json
  Cache-Control: public, max-age=900
/api/v1/research.json
  Cache-Control: public, max-age=900
/api/v1/editions/*
  Cache-Control: public, max-age=86400
/api/v1/bulk/*
  Cache-Control: public, max-age=86400
/api/docs.md
  Cache-Control: public, max-age=3600
  Content-Type: text/plain; charset=utf-8
"""

# With no top-level 404.html, Pages answers every missing path with 200 and the
# home page, which would hand API users HTML for a date that doesn't exist.
_NOT_FOUND = """\
<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Not found</title>
<p>There's nothing at this address. <a href="/">Go to today's edition</a>.</p>
</html>
"""


def _zip(files: list[Path], path: Path) -> None:
    with zipfile.ZipFile(path, "w") as z:
        for f in files:
            info = zipfile.ZipInfo(f.name, date_time=_ZIP_TIME)
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def write(out: Path, edition: Edition, research_index: dict, base_url: str, sample: bool,
          corrections: list[dict]) -> list[Path]:
    """Write the public data into an exported site whose archive/ is already in place."""
    api = out / _API
    (api / "editions").mkdir(parents=True, exist_ok=True)
    (api / "bulk").mkdir(exist_ok=True)
    written: list[Path] = []

    def link(path: Path) -> dict:
        return {"path": path.as_posix(), "url": f"{base_url}/{path.as_posix()}"}

    def dump(name: str, data: dict) -> dict:
        (api / name).write_text(json.dumps(data, ensure_ascii=False))
        written.append(api / name)
        return link(_API / name)

    header = {"api_version": API_VERSION, "sample": sample}
    files = {
        "sources": dump("sources.json", {**header, **edition.public_sources()}),
        "research": dump("research.json", {**header, **research_index}),
    }

    # Newest first, which is also how the month groups below come out.
    archived = sorted((f for f in (out / "archive").glob("*.json") if _EDITION_FILE.fullmatch(f.name)), reverse=True) \
        if (out / "archive").is_dir() else []
    editions = []
    for f in archived:
        shutil.copy(f, api / "editions" / f.name)
        written.append(api / "editions" / f.name)
        editions.append({"date": f.stem, **link(_API / "editions" / f.name)})
    if archived:
        shutil.copy(archived[0], api / "latest.json")
        written.append(api / "latest.json")
        files["latest_edition"] = link(_API / "latest.json")

    bulk = []
    for month, group in groupby(archived, key=lambda f: f.stem[:7]):
        month_files = sorted(group)
        path = api / "bulk" / f"{month}.zip"
        _zip(month_files, path)
        written.append(path)
        bulk.append({"month": month, "editions": len(month_files), "bytes": path.stat().st_size,
                     **link(_API / "bulk" / path.name)})

    (out / "api" / "docs.md").write_text((config.ROOT / "docs" / "api.md").read_text())
    (out / "_headers").write_text(_HEADERS)
    (out / "404.html").write_text(_NOT_FOUND)
    written += [out / "api" / "docs.md", out / "_headers", out / "404.html"]
    files["docs"] = {"path": "api/docs.md", "url": f"{base_url}/api/docs.md"}

    dump("index.json", {
        **header, "edition_format": FORMAT, "latest": editions[0]["date"] if editions else None,
        "editions": editions, "bulk": bulk, "files": files, "corrections": corrections,
    })
    return written
