"""Export the latest edition as a static site.

    python -m boringnews.export_static --out site

Writes index.html (settings work in the browser), edition.json (the data),
and one ready-made feed per topic under feeds/.

Custom feed addresses (/feed.xml?topics=...) are built on request by the
Cloudflare Pages function in functions/feed.xml.js, which reads edition.json.
Pass --static-feed to also write a fixed feed.xml for hosts without functions
(GitHub Pages, any plain file host); that file ignores feed settings.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from . import config
from . import research
from .db import connect, editions, load_edition, load_extra
from .feeds import render_rss
from .prefs import Prefs, apply
from .render import page_data, render_page
from .sources import load_sources
from .topics import TOPICS


def export(out: Path, db_path: Path, sample: bool, base_url: str, cname: str | None = None,
           static_feed: bool = False, archive_dir: Path | None = None,
           inline_research: bool = False) -> list[Path]:
    conn = connect(db_path)
    dates = editions(conn)
    if not dates:
        raise SystemExit("No editions yet. Run: python -m boringnews.pipeline run")
    stories = load_edition(conn, dates[0])
    sources = load_sources(config.FIXTURE_SOURCES_PATH if sample else config.SOURCES_PATH)

    out.mkdir(parents=True, exist_ok=True)
    (out / "feeds").mkdir(exist_ok=True)
    written = []

    # Publish the edition files so anyone can download and re-check them.
    data_url = None
    if archive_dir and Path(archive_dir).is_dir():
        (out / "archive").mkdir(exist_ok=True)
        for f in sorted(Path(archive_dir).glob("*.json")):
            shutil.copy(f, out / "archive" / f.name)
            written.append(out / "archive" / f.name)
        if (out / "archive" / f"{dates[0]}.json").exists():
            data_url = f"{base_url}/archive/{dates[0]}.json"
    # Research tab: the last 30 days, fetched by the page when the tab opens.
    index = research.build(conn, sources)
    (out / "research.json").write_text(json.dumps(index, ensure_ascii=False))
    written.append(out / "research.json")

    data = page_data(dates[0], dates, stories, sources, base_url, sample=sample, data_url=data_url,
                     markets=load_extra(conn, dates[0], "markets", []),
                     research_url="research.json", research=index if inline_research else None)
    (out / "index.html").write_text(render_page(data))
    (out / "edition.json").write_text(json.dumps(data, ensure_ascii=False))
    written += [out / "index.html", out / "edition.json"]

    if static_feed:
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
    ap.add_argument("--archive", default=str(config.ARCHIVE_DIR), help="folder of edition files to publish")
    ap.add_argument("--inline-research", action="store_true",
                    help="embed the research index in the page (for a single-file preview)")
    ap.add_argument("--static-feed", action="store_true", help="also write a fixed feed.xml (hosts without functions)")
    args = ap.parse_args(argv)
    for p in export(Path(args.out), Path(args.db), args.sample, args.base_url.rstrip("/"), args.cname, args.static_feed,
                    Path(args.archive), args.inline_research):
        print("wrote", p)


if __name__ == "__main__":
    main()
