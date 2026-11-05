"""What a reader's settings do lives in one place: web/core.js, which the page
and the Cloudflare function run. Python asks it for feeds through node rather
than keeping a second copy of the rules."""

from __future__ import annotations

import json
import shutil
import subprocess

from . import config


def feeds(data: dict, queries: list[str]) -> list[str]:
    """RSS for each settings query (like "topics=economy"), from page data."""
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Building RSS feeds needs node: install it from https://nodejs.org")
    out = subprocess.run([node, str(config.ROOT / "web" / "feed_cli.cjs")], input=json.dumps({"data": data, "queries": queries}),
                         capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"web/feed_cli.cjs failed: {out.stderr.strip()}")
    return json.loads(out.stdout)
