"""The page and the feed function use web/core.js; the pipeline and server use
Python. These tests check both give the same stories, in the same order, with
the same scores, and that the Cloudflare function serves a valid custom feed."""

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from boringnews import config
from boringnews.db import connect, load_edition
from boringnews.feeds import render_rss
from boringnews.pipeline import main as pipeline_main
from boringnews.prefs import Prefs, apply
from boringnews.render import page_data
from boringnews.sources import load_sources

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

QUERIES = [
    "",
    "threshold=broad",
    "threshold=strict",
    "topics=economy,government",
    "exclude=heartland-post,liberty-daily,prairie-gazette",
    "statements=0",
    "official=0&threshold=broad",
    "spotlight=1",
    "topics=world&length=headlines",
]

RUNNER = r"""
const fs = require("fs");
require(process.argv[2]);
const D = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const C = globalThis.BoringCore.create(D);
const out = {};
for (const q of JSON.parse(process.argv[4])) {
  const p = C.fromQuery("?" + q);
  const res = C.select(p);
  const items = p.spotlight ? C.spotlight(res.shown) : res.shown;
  out[q] = { items: items.map(x => [x.story.id, x.lane, x.score.total, x.why]), query: C.toQuery(p),
             rss: C.rss(p, "https://example.org") };
}
console.log(JSON.stringify(out));
"""

FUNCTION_RUNNER = r"""
import { readFileSync } from "fs";
import { pathToFileURL } from "url";
await import(pathToFileURL(process.argv[2]).href);           // web/core.js sets globalThis.BoringCore
const mod = await import(pathToFileURL(process.argv[3]).href); // the function, minus its import line
const edition = readFileSync(process.argv[4], "utf8");
const env = { ASSETS: { fetch: async () => new Response(edition, { headers: { "content-type": "application/json" } }) } };
const res = await mod.onRequest({ request: new Request("https://boringnews.org/feed.xml?topics=government&threshold=strict"), env });
console.log(JSON.stringify({ status: res.status, type: res.headers.get("content-type"), body: await res.text() }));
"""


@pytest.fixture(scope="module")
def edition(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("parity")
    db = tmp / "t.db"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", "2026-11-04", "--db", str(db)])
    conn = connect(db)
    stories = load_edition(conn, "2026-11-04")
    sources = load_sources(config.FIXTURE_SOURCES_PATH)
    data = page_data("2026-11-04", ["2026-11-04"], stories, sources, "https://example.org", sample=True)
    path = tmp / "edition.json"
    path.write_text(json.dumps(data))
    return tmp, path, stories, sources


def test_js_core_matches_python(edition):
    tmp, path, stories, sources = edition
    runner = tmp / "runner.js"
    runner.write_text(RUNNER)
    out = subprocess.run([NODE, str(runner), str(config.ROOT / "web" / "core.js"), str(path), json.dumps(QUERIES)],
                         capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    for q in QUERIES:
        prefs = Prefs.from_query(dict(x.split("=") for x in q.split("&")) if q else {})
        py = [[x.story.id, x.lane, x.score.total, x.why] for x in apply(stories, sources, prefs)]
        assert js[q]["items"] == py, q
        assert js[q]["query"] == prefs.to_query(), q
        # Same feed items, same titles, same order.
        py_rss = ET.fromstring(render_rss("2026-11-04", apply(stories, sources, prefs), sources, prefs, "https://example.org"))
        js_rss = ET.fromstring(js[q]["rss"])
        assert [i.findtext("title") for i in js_rss.iter("item")] == [i.findtext("title") for i in py_rss.iter("item")], q
        assert [i.findtext("guid") for i in js_rss.iter("item")] == [i.findtext("guid") for i in py_rss.iter("item")], q


def test_pages_function_serves_custom_feed(edition):
    tmp, path, stories, sources = edition
    src = (config.ROOT / "functions" / "feed.xml.js").read_text()
    fn = tmp / "feed_fn.mjs"
    fn.write_text("\n".join(l for l in src.splitlines() if not l.startswith("import ")))
    runner = tmp / "fn_runner.mjs"
    runner.write_text(FUNCTION_RUNNER)
    out = subprocess.run([NODE, str(runner), str(config.ROOT / "web" / "core.js"), str(fn), str(path)],
                         capture_output=True, text=True, check=True)
    res = json.loads(out.stdout)
    assert res["status"] == 200 and res["type"].startswith("application/rss+xml")
    items = ET.fromstring(res["body"]).findall("./channel/item")
    expected = apply(stories, sources, Prefs(topics=["government"], threshold="strict"))
    assert [i.findtext("guid") for i in items] == [f"boringnews-2026-11-04-{x.story.id}" for x in expected]
