"""Render the reader page. The page is one self-contained HTML file: the page
data is embedded as JSON, and web/core.js and web/app.js filter it by the
reader's settings in the browser."""

from __future__ import annotations

import html
import json

import yaml

from . import config

WEB = config.ROOT / "web"


def load_corrections() -> list[dict]:
    if not config.CORRECTIONS_PATH.exists():
        return []
    data = yaml.safe_load(config.CORRECTIONS_PATH.read_text()) or {}
    return [{k: str(v) for k, v in c.items()} for c in (data.get("corrections") or [])]


def render_page(data: dict) -> str:
    template = (WEB / "index.html").read_text()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (
        template.replace("__REPO_URL__", html.escape(data["repo_url"]))
        .replace("__BASE_URL__", html.escape(data["base_url"]))
        .replace("/*__CSS__*/", (WEB / "style.css").read_text())
        .replace("/*__CORE__*/", (WEB / "core.js").read_text())
        .replace("/*__APP__*/", (WEB / "app.js").read_text())
        .replace('"__DATA__"', payload)
    )
