"""The path readers actually get: an edition is built, exported to a folder,
and served by the real page script and the real Cloudflare function."""

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from boringnews import config
from boringnews.export_static import main as export_main
from boringnews.pipeline import main as pipeline_main
from boringnews.topics import TOPICS

NODE = shutil.which("node")
BASE = "https://example.org"
DATE = "2026-11-04"

FUNCTION_RUNNER = r"""
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { pathToFileURL } from "url";
const [fn, site, ...urls] = process.argv.slice(2);
const mod = await import(pathToFileURL(fn).href);
const env = { ASSETS: { fetch: async (u) => {
  const file = join(site, new URL(u).pathname);
  return existsSync(file) ? new Response(readFileSync(file, "utf8")) : new Response("", { status: 404 });
} } };
const out = [];
for (const url of urls) {
  const res = await mod.onRequest({ request: new Request(url), env });
  out.push({ status: res.status, type: res.headers.get("content-type"), body: await res.text() });
}
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("published")
    db, arch, out = tmp / "t.db", tmp / "archive", tmp / "site"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", DATE, "--db", str(db), "--archive", str(arch)])
    export_main(["--out", str(out), "--db", str(db), "--sample", "--archive", str(arch), "--base-url", BASE])
    return out


def edition(site: Path) -> dict:
    return json.loads((site / "edition.json").read_text())


def serve(site: Path, tmp_path: Path, *urls: str) -> list[dict]:
    """Run the unmodified function file, import line included. The .mjs copy
    beside web/core.js is how both node 20 and 22 load it as a module."""
    (tmp_path / "functions").mkdir()
    (tmp_path / "web").mkdir()
    fn = tmp_path / "functions" / "feed.xml.mjs"
    shutil.copy(config.ROOT / "functions" / "feed.xml.js", fn)
    shutil.copy(config.ROOT / "web" / "core.js", tmp_path / "web" / "core.js")
    runner = tmp_path / "runner.mjs"
    runner.write_text(FUNCTION_RUNNER)
    out = subprocess.run([NODE, str(runner), str(fn), str(site), *urls], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def open_page(site: Path, url: str) -> dict:
    out = subprocess.run([NODE, str(config.ROOT / "tests" / "page_smoke.cjs"), str(site / "index.html"), url],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_export_writes_the_whole_site(site):
    names = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    assert {"index.html", "edition.json", "research.json", f"archive/{DATE}.json"} <= names
    assert {f"feeds/{t}.xml" for t in TOPICS} <= names
    assert "feed.xml" not in names  # only with --static-feed


def test_edition_json_carries_what_the_page_needs(site):
    data = edition(site)
    assert data["edition"] == DATE and data["sample"] is True and data["base_url"] == BASE
    assert data["data_url"] == f"{BASE}/archive/{DATE}.json"
    assert data["research_url"] == "research.json" and data["research"] is None
    assert len(data["markets"]) == 7 and len(data["stories"]) == 17
    assert all(s["id"] for s in data["stories"])
    assert json.loads((site / "archive" / f"{DATE}.json").read_text())["stories"][0]["id"] == data["stories"][0]["id"]
    assert set(data["rubric"]) == {"version", "weights", "thresholds", "coverage_cap", "min_outlets", "spotlight"}


def test_static_feed_is_opt_in(site, tmp_path):
    db = tmp_path / "t.db"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", DATE, "--db", str(db)])
    export_main(["--out", str(tmp_path / "s"), "--db", str(db), "--sample", "--static-feed", "--archive", str(tmp_path / "none")])
    ET.parse(tmp_path / "s" / "feed.xml")


def test_inline_research_embeds_the_index(site, tmp_path):
    db = tmp_path / "t.db"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", DATE, "--db", str(db)])
    export_main(["--out", str(tmp_path / "s"), "--db", str(db), "--sample", "--inline-research", "--archive", str(tmp_path / "none")])
    assert len(edition(tmp_path / "s")["research"]["stories"]) == 17


def test_export_needs_an_edition(tmp_path):
    with pytest.raises(SystemExit, match="No editions yet"):
        export_main(["--out", str(tmp_path / "s"), "--db", str(tmp_path / "empty.db")])


def test_topic_feeds_only_hold_their_topic(site):
    data = edition(site)
    ids = {s["id"]: s["topic"] for s in data["stories"]}
    seen = 0
    for topic, label in TOPICS.items():
        for item in ET.parse(site / "feeds" / f"{topic}.xml").getroot().iter("item"):
            seen += 1
            assert item.findtext("category") == label
            assert ids[int(item.findtext("guid").rsplit("-", 1)[1])] == topic
    assert seen


def test_function_serves_custom_feeds_from_the_export(site, tmp_path):
    default, custom = serve(site, tmp_path, f"{BASE}/feed.xml", f"{BASE}/feed.xml?topics=government&threshold=strict")
    assert default["status"] == 200 and default["type"].startswith("application/rss+xml")
    all_items = ET.fromstring(default["body"]).findall("./channel/item")
    some_items = ET.fromstring(custom["body"]).findall("./channel/item")
    assert 0 < len(some_items) < len(all_items)
    assert all(i.findtext("category") == TOPICS["government"] for i in some_items)


def test_old_topic_names_keep_their_feed_narrow(site, tmp_path):
    full, old, new, mixed = serve(site, tmp_path, f"{BASE}/feed.xml", f"{BASE}/feed.xml?topics=courts",
                                  f"{BASE}/feed.xml?topics=government", f"{BASE}/feed.xml?topics=courts,congress,economy")
    assert old["body"] == new["body"]
    assert old["body"] != full["body"]
    labels = {i.findtext("category") for i in ET.fromstring(mixed["body"]).findall("./channel/item")}
    assert labels == {TOPICS["government"], TOPICS["economy"]}


def test_function_reports_a_missing_edition(tmp_path):
    assert serve(tmp_path / "nothing", tmp_path, f"{BASE}/feed.xml")[0]["status"] == 503


jsdom = pytest.mark.skipif(not (config.ROOT / "node_modules" / "jsdom").exists(), reason="needs `npm install`")


@jsdom
def test_page_renders_the_edition(site):
    page = open_page(site, f"{BASE}/")
    assert page["errors"] == []
    assert page["lede"] == "Five stories today." and page["spotlight"] == 5
    assert page["ticker"] == 14 and page["dataLink"]  # the ticker repeats so it can scroll
    assert page["feedUrl"] == f"{BASE}/feed.xml?threshold=strict"


@jsdom
def test_feed_links_open_the_visible_story(site):
    top = open_page(site, f"{BASE}/")["anchors"]
    assert top
    page = open_page(site, f"{BASE}/#{top[0]}")
    assert page["errors"] == [] and page["duplicates"] == []
    assert page["scrolledTo"] == top[0] and not page["scrolledToHidden"]


@jsdom
def test_page_keeps_an_old_topic_filter(site):
    page = open_page(site, f"{BASE}/?topics=courts")
    assert page["errors"] == [] and "topics=government" in page["feedUrl"]


@jsdom
def test_every_setting_is_documented(site):
    page = open_page(site, f"{BASE}/")
    assert page["docs"] == page["settings"]
    readme = (config.ROOT / "README.md").read_text()
    assert all(f"| `{name}` |" in readme for name in page["settings"])
