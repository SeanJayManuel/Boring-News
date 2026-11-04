"""Export the latest edition as a static site (no server needed).

    python -m boringnews.export_static --out site

Writes index.html (customization works in the browser), feed.xml (default
settings) and one feed per topic under feeds/. Fully custom feed URLs need
the server (boringnews.web) or a small serverless function.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .db import connect, editions, load_edition
from .feeds import render_rss
from .prefs import Prefs, apply
from .render import page_data, render_page
from .sources import load_sources
from .topics import TOPICS


def export(out: Path, db_path: Path, sample: bool, base_url: str, cname: str | None = None) -> list[Path]:
    conn = connect(db_path)
    dates = editions(conn)
    if not dates:
        raise SystemExit("No editions yet. Run: python -m boringnews.pipeline run")
    stories = load_edition(conn, dates[0])
    sources = load_sources(config.FIXTURE_SOURCES_PATH if sample else config.SOURCES_PATH)

    out.mkdir(parents=True, exist_ok=True)
    (out / "feeds").mkdir(exist_ok=True)
    written = []

    page = render_page(page_data(dates[0], dates, stories, sources, base_url, sample=sample))
    (out / "index.html").write_text(page)
    written.append(out / "index.html")

    default = Prefs()
    (out / "feed.xml").write_text(render_rss(dates[0], apply(stories, sources, default), sources, default, base_url))
    written.append(out / "feed.xml")
    if cname:  # GitHub Pages custom domain
        (out / "CNAME").write_text(cname.strip() + "\n")
        written.append(out / "CNAME")
    for topic in TOPICS:
        p = Prefs(topics=[topic])
        path = out / "feeds" / f"{topic}.xml"
        path.write_text(render_rss(dates[0], apply(stories, sources, p), sources, p, base_url))
        written.append(path)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(prog="boringnews.export_static")
    ap.add_argument("--out", default="site")
    ap.add_argument("--db", default=str(config.DB_PATH))
    ap.add_argument("--sample", action="store_true", help="label the page as sample data")
    ap.add_argument("--base-url", default=config.BASE_URL)
    ap.add_argument("--cname", help="custom domain for GitHub Pages, e.g. boringnews.org")
    args = ap.parse_args(argv)
    for p in export(Path(args.out), Path(args.db), args.sample, args.base_url.rstrip("/"), args.cname):
        print("wrote", p)


if __name__ == "__main__":
    main()
