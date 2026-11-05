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
def two_days(tmp_path_factory):
    """Two editions, so some of the second day's stories are on Day 2."""
    tmp = tmp_path_factory.mktemp("published")
    db, arch, out = tmp / "t.db", tmp / "archive", tmp / "site"
    for date in ("2026-11-03", DATE):
        pipeline_main(["run", "--fixtures", "--mock-llm", "--date", date, "--db", str(db), "--archive", str(arch)])
    export_main(["--out", str(out), "--db", str(db), "--sample", "--archive", str(arch), "--base-url", BASE])
    return out


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


def open_page(site: Path, url: str, research: str = "ok") -> dict:
    out = subprocess.run([NODE, str(config.ROOT / "tests" / "page_smoke.cjs"), str(site / "index.html"), url, research],
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


def test_how_it_works_links_the_challenge_forms(site):
    page = (site / "index.html").read_text()
    assert f'href="{config.REPO_URL}/issues/new/choose"' in page and "__REPO_URL__" not in page


@jsdom
def test_every_setting_is_documented(site):
    page = open_page(site, f"{BASE}/")
    assert page["docs"] == page["settings"]
    readme = (config.ROOT / "README.md").read_text()
    assert all(f"| `{name}` |" in readme for name in page["settings"])


@jsdom
def test_a_reader_can_see_each_story_left_out_and_why(site):
    page = open_page(site, f"{BASE}/?topics=economy")
    assert page["errors"] == []
    seen = page["loaded"]
    total = len(edition(site)["stories"])
    assert 0 < len(seen["leftOut"]) < total
    assert seen["leftOutSummary"] == f"See the {len(seen['leftOut'])} stories left out, and why"
    assert seen["leftOutAllSummary"] == seen["leftOutSummary"]
    assert f"{len(seen['leftOut'])} stories left out by your settings" in seen["showing"]
    assert seen["leftOutGroups"][0].startswith("Outside your categories (")
    assert all(row["headline"] and row["why"] and row["bullets"] and row["sources"] for row in seen["leftOut"])
    assert all("isn't one you chose" in row["why"] for row in seen["leftOut"])
    assert page["anchoredLeftOut"] == 0 and page["duplicates"] == []


@jsdom
def test_left_out_stories_follow_headlines_only(site):
    seen = open_page(site, f"{BASE}/?topics=economy&length=headlines")["loaded"]
    assert seen["leftOut"] and not any(row["bullets"] for row in seen["leftOut"])


@jsdom
def test_nothing_is_listed_when_nothing_is_left_out(site):
    assert open_page(site, f"{BASE}/?threshold=broad")["loaded"]["leftOutSummary"] is None


@jsdom
def test_custom_weights_change_what_the_page_says(site):
    seen = open_page(site, f"{BASE}/?weights=0,0,0,100")["loaded"]
    assert seen["sublede"].startswith("Ranked by your own weights: ") and "record 100%" in seen["sublede"]
    assert "your own weights" in seen["showing"]
    assert seen["scoreLine"].startswith("Score 1.00 with your weights: ")
    assert "government record 1.00" in seen["scoreLine"] and seen["scoreLine"].endswith("Your setting needs 0.40.")
    assert seen["chartLabel"].startswith("Score 1.00 with your weights: ") and seen["chartWidths"] == [100]
    assert "your own weights" in seen["chartNote"] and "published rule" in seen["weightsYours"]
    assert "published weights" in seen["thresholdHint"]
    assert seen["sliders"] == [0, 0, 0, 100] and seen["shares"] == ["0%", "0%", "0%", "100%"]
    assert seen["feedUrl"] == f"{BASE}/feed.xml?weights=0,0,0,100"


@jsdom
def test_default_weights_say_nothing_new(site):
    seen = open_page(site, f"{BASE}/")["loaded"]
    assert seen["sublede"].startswith("Ranked by how widely") and "weights" not in seen["showing"]
    assert seen["scoreLine"].startswith("Score ") and "with your weights" not in seen["scoreLine"]
    assert "weights" not in seen["chartLabel"] and seen["chartNote"] == "" and seen["weightsYours"] is None
    assert "weights" not in seen["thresholdHint"] and seen["sliders"] == [40, 25, 10, 25]
    assert seen["feedUrl"] == f"{BASE}/feed.xml" and seen["recipeLink"] == f"{BASE}/" and seen["recipeNote"] is None


@jsdom
def test_sliders_change_the_address_and_reset_clears_them(site):
    page = open_page(site, f"{BASE}/")
    assert page["errors"] == []
    assert page["slid"]["feedUrl"] == f"{BASE}/feed.xml?threshold=strict&weights=40,25,10,100"
    assert page["slid"]["shares"] == ["23%", "14%", "6%", "57%"]
    assert page["reset"]["feedUrl"] == f"{BASE}/feed.xml" and page["reset"]["sliders"] == [40, 25, 10, 25]
    assert page["allZero"]["feedUrl"] == f"{BASE}/feed.xml"
    assert page["allZero"]["sliders"] == [40, 25, 10, 25]  # nothing to rank by, so the published rule stands


@jsdom
def test_the_page_says_what_weights_cannot_do(site):
    html = (site / "index.html").read_text()
    assert "Weights only re-rank stories that were written" in html and "no weight can bring it back" in html


@jsdom
def test_a_recipe_is_a_named_link(site):
    page = open_page(site, f"{BASE}/")
    named = page["named"]
    assert named["recipeLink"] == f"{BASE}/?threshold=strict&weights=40,25,10,100&recipe=My%20mix"
    assert named["feedUrl"].endswith("&recipe=My%20mix")
    assert "My mix" in named["recipeNote"] and "not Standard Edition" in named["recipeNote"]
    assert page["savedQuery"].endswith("recipe=My%20mix")                     # kept in this browser
    assert page["copyStatus"]                                                 # jsdom has no clipboard, so it selects
    assert page["reset"]["recipeName"] == "" and page["reset"]["recipeNote"] is None
    assert page["fetchedOnLoad"] == 0


@jsdom
def test_opening_a_recipe_link_restores_it(site):
    seen = open_page(site, f"{BASE}/?weights=20,20,10,50&recipe=Paper%20trail")["loaded"]
    assert seen["recipeName"] == "Paper trail" and "Paper trail" in seen["recipeNote"]
    assert seen["sliders"] == [20, 20, 10, 50]


@jsdom
def test_a_recipe_name_is_text_not_markup(site):
    page = open_page(site, f"{BASE}/?recipe=%3Cimg%20src%3Dx%3E")
    assert page["errors"] == [] and "<img src=x>" in page["loaded"]["recipeNote"]


@jsdom
def test_built_in_recipes_are_listed_and_open(site):
    links = open_page(site, f"{BASE}/")["recipes"]
    assert len(links) >= 3 and all(a.startswith("?") and "recipe=" in a and a.endswith("#today") for a in links)
    page = open_page(site, f"{BASE}/{links[1]}")
    assert page["errors"] == [] and page["loaded"]["recipeNote"]


@jsdom
def test_a_developing_story_opens_its_earlier_days(two_days):
    page = open_page(two_days, f"{BASE}/?threshold=broad")
    assert page["errors"] == []
    assert page["earlierButtons"] and page["fetchedOnLoad"] == 0 and page["earlier"]["fetched"] == 1
    days = page["earlier"]["days"]
    assert len(days) == 1 and days[0]["when"] == "Nov 3, 2026, day 1"
    assert days[0]["headline"] and days[0]["bullets"] and days[0]["sources"]
    assert page["earlier"]["message"] is None and page["earlier"]["open"]


@jsdom
def test_a_first_day_story_has_no_earlier_days(site):
    assert open_page(site, f"{BASE}/?threshold=broad")["earlierButtons"] == 0


@jsdom
def test_headlines_only_keeps_the_earlier_days_link(two_days):
    page = open_page(two_days, f"{BASE}/?length=headlines&threshold=broad")
    assert page["earlierButtons"] and len(page["earlier"]["days"]) == 1


@jsdom
@pytest.mark.parametrize("research", ["missing", "down"])
def test_earlier_days_say_so_when_the_index_is_unavailable(two_days, research):
    page = open_page(two_days, f"{BASE}/?threshold=broad", research)
    assert page["errors"] == []
    assert page["earlier"]["days"] == [] and "aren't available" in page["earlier"]["message"]


def test_function_serves_custom_weights_and_a_named_feed(site, tmp_path):
    plain, weighted, same = serve(site, tmp_path, f"{BASE}/feed.xml", f"{BASE}/feed.xml?weights=0,0,0,100&recipe=Records",
                                  f"{BASE}/feed.xml?weights=40,25,10,25")
    assert same["body"] == plain["body"]
    root = ET.fromstring(weighted["body"]).find("channel")
    assert root.findtext("title") == "Standard Edition (reader recipe: Records)"
    assert [i.findtext("title") for i in root.findall("item")] != \
        [i.findtext("title") for i in ET.fromstring(plain["body"]).findall("./channel/item")]
