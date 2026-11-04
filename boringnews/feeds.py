"""RSS 2.0 output. One item per story."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from html import escape
from xml.sax.saxutils import escape as xml_escape

from .prefs import Prefs, Selected
from .sources import Source
from .topics import TOPICS


def _item_html(sel: Selected, sources: dict[str, Source], prefs: Prefs) -> str:
    parts = []
    if prefs.length == "full":
        parts.append("<ul>" + "".join(f"<li>{escape(b)}</li>" for b in sel.story.bullets) + "</ul>")
        if sel.story.whats_next:
            parts.append(f"<p><b>What's next:</b> {escape(sel.story.whats_next)}</p>")
    parts.append(f"<p><i>{escape(sel.why)}</i></p>")
    links = ", ".join(
        f'<a href="{escape(a.url)}">{escape(sources[a.source_id].name)}</a>' for a in sel.articles
    )
    parts.append(f"<p>Sources: {links}</p>")
    return "".join(parts)


def render_rss(edition_date: str, selected: list[Selected], sources: dict[str, Source],
               prefs: Prefs, base_url: str) -> str:
    pub = format_datetime(datetime.combine(date.fromisoformat(edition_date), time(12, 0), tzinfo=timezone.utc))
    query = prefs.to_query()
    self_url = f"{base_url}/feed.xml" + (f"?{query}" if query else "")
    items = []
    for sel in selected:
        s = sel.story
        link = f"{base_url}/?date={edition_date}#story-{s.id}"
        title = s.headline if sel.lane == "main" else f"Underreported: {s.headline}"
        items.append(
            "<item>"
            f"<title>{xml_escape(title)}</title>"
            f"<link>{xml_escape(link)}</link>"
            f'<guid isPermaLink="false">boringnews-{edition_date}-{s.id}</guid>'
            f"<category>{xml_escape(TOPICS.get(s.topic, s.topic))}</category>"
            f"<pubDate>{pub}</pubDate>"
            f"<description>{xml_escape(_item_html(sel, sources, prefs))}</description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        "<title>Boring News</title>"
        f"<link>{xml_escape(base_url)}/</link>"
        f'<atom:link href="{xml_escape(self_url)}" rel="self" type="application/rss+xml"/>'
        "<description>The day's news, once a day, without the noise.</description>"
        "<language>en-us</language>"
        "<ttl>720</ttl>"
        f"<lastBuildDate>{pub}</lastBuildDate>"
        + "".join(items)
        + "</channel></rss>\n"
    )
