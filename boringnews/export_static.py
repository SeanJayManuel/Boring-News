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

from . import config, research
from .db import connect
from .edition import Edition, NoEdition
from .reader import feeds
from .render import load_corrections, render_page
from .sources import load_sources
from .topics import TOPICS


def export(edition: Edition, research_index: dict, out: Path, base_url: str, sample: bool = False,
           cname: str | None = None, static_feed: bool = False, archive_dir: Path | None = None,
           inline_research: bool = False) -> list[Path]:
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
        if (out / "archive" / f"{edition.date}.json").exists():
            data_url = f"{base_url}/archive/{edition.date}.json"
    # Research tab: the last 30 days, fetched by the page when the tab opens.
    (out / "research.json").write_text(json.dumps(research_index, ensure_ascii=False))
    written.append(out / "research.json")

    data = edition.page_data(base_url, sample=sample, data_url=data_url, corrections=load_corrections(),
                             research_url="research.json", research=research_index if inline_research else None)
    (out / "index.html").write_text(render_page(data))
    (out / "edition.json").write_text(json.dumps(data, ensure_ascii=False))
    written += [out / "index.html", out / "edition.json"]

    if cname:  # GitHub Pages custom domain
        (out / "CNAME").write_text(cname.strip() + "\n")
        written.append(out / "CNAME")

    paths = {out / "feeds" / f"{topic}.xml": f"topics={topic}" for topic in TOPICS}
    if static_feed:
        paths[out / "feed.xml"] = ""
    for path, xml in zip(paths, feeds(data, list(paths.values()))):
        path.write_text(xml)
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
    conn = connect(args.db)
    sources = load_sources(config.sources_path(args.sample))
    try:
        edition = Edition.load(conn, sources)
    except NoEdition as exc:
        raise SystemExit(str(exc))
    for p in export(edition, research.build(conn, sources), Path(args.out), args.base_url.rstrip("/"), args.sample,
                    args.cname, args.static_feed, Path(args.archive), args.inline_research):
        print("wrote", p)


if __name__ == "__main__":
    main()
