"""The path readers actually get: an edition is built, exported to a folder,
and served by the real page script and the real Cloudflare function."""

import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from boringnews import config, ledger
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


def open_page(site: Path, url: str, research: str = "ok", saved: str | None = None) -> dict:
    args = [NODE, str(config.ROOT / "tests" / "page_smoke.cjs"), str(site / "index.html"), url, research]
    out = subprocess.run(args + ([] if saved is None else [saved]), capture_output=True, text=True, check=True)
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
    assert set(data["rubric"]) == {"version", "weights", "thresholds", "coverage_cap", "min_outlets", "spotlight",
                                   "blindspot_outlets"}


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
    assert page["lede"].startswith("Five stories today.") and page["spotlight"] == 5
    assert page["ticker"] == 14 and page["dataLink"]
    assert page["feedUrl"] == f"{BASE}/feed.xml?threshold=strict"


def test_category_names_are_title_case():
    words = [w for name in TOPICS.values() for w in name.split() if w != "&"]
    assert words and all(w[0].isupper() for w in words)


def test_sample_note_sits_in_a_landmark(site):
    html = (site / "index.html").read_text()
    assert html.index('<header class="masthead">') < html.index('id="sample-note"') < html.index("</header>")


@jsdom
def test_headings_and_names_read_in_order(site):
    page = open_page(site, f"{BASE}/")
    assert page["leadHeading"] == "H2" and page["themePressed"] is None
    assert page["themeColor"] and page["allSummary"].count(" backed by a government record.") == 1
    assert all(link.startswith("#topic-") for link in page["topicLinks"]) and page["topicLinks"]
    assert all(" " in name for name in page["topicNames"])
    assert all("\u25b2" not in name and "\u25bc" not in name and name.endswith("(FRED)") for name in page["tickNames"])


@jsdom
def test_a_topic_link_opens_its_place_in_all_stories(site):
    topic = open_page(site, f"{BASE}/")["topicLinks"][0]
    page = open_page(site, f"{BASE}/{topic}")
    assert page["errors"] == [] and page["scrolledTo"] == topic[1:] and not page["scrolledToHidden"]


@jsdom
def test_a_research_search_can_be_shared(site):
    page = open_page(site, f"{BASE}/#research?lookup=water&q=river&uncovered=1")
    assert page["errors"] == [] and page["researchLookup"] == "water"
    assert page["researchQuery"] == "river" and page["researchUncovered"] is True
    assert page["address"].endswith("#research?lookup=water&q=river&uncovered=1")
    assert page["recCount"].endswith(" edition.") or page["recCount"].endswith(" editions.")


@jsdom
def test_reset_can_be_undone(site):
    page = open_page(site, f"{BASE}/?weights=10,20,30,40")
    assert page["undoOffered"] and page["undoGone"]
    assert page["reset"]["sliders"] != page["undone"]["sliders"] and "weights=" in page["undone"]["feedUrl"]


@jsdom
def test_all_sliders_at_zero_stay_in_place(site):
    page = open_page(site, f"{BASE}/")
    assert page["sliderKept"] and page["allZero"]["sliders"] == [40, 25, 10, 25]


@jsdom
def test_a_settings_link_offers_the_way_back(site):
    replacing = open_page(site, f"{BASE}/?threshold=broad", saved="threshold=strict")
    assert any(n.startswith("This link replaced the settings") for n in replacing["notices"])
    same = open_page(site, f"{BASE}/?threshold=strict", saved="threshold=strict")
    fresh = open_page(site, f"{BASE}/?threshold=broad")
    assert not any("replaced" in n for n in same["notices"] + fresh["notices"])


@jsdom
def test_feed_links_open_the_visible_story(site):
    top = open_page(site, f"{BASE}/")["anchors"]
    assert top
    page = open_page(site, f"{BASE}/#{top[0]}")
    assert page["errors"] == [] and page["duplicates"] == []
    assert page["storyTitle"] and page["storyScore"] and page["storyTitle"] in page["title"]
    assert page["sideColumns"] == ["Left", "Center", "Right"]


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
    assert seen["sublede"] == "" and "weights" not in seen["showing"]
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


def test_opening_sentence_names_a_side_the_reader_left_out(site):
    left = "bay-chronicle,metro-ledger,northside-tribune"
    lede = open_page(site, f"{BASE}/?exclude={left}")["lede"]
    assert lede.endswith(" stories today. No left outlet you kept ran these.")


@jsdom
def test_a_link_to_a_story_outside_todays_edition(two_days):
    data = json.loads((two_days / "research.json").read_text())
    old = next(s for s in data["stories"] if s["date"] == "2026-11-03")
    page = open_page(two_days, f"{BASE}/#story-{old['id']}")
    assert page["errors"] == [] and page["storyTitle"] == old["headline"]
    assert page["storyNote"] == "From the edition of Tuesday, November 3, 2026."


@jsdom
def test_a_link_to_a_story_we_no_longer_have(site):
    page = open_page(site, f"{BASE}/#story-999999")
    assert page["errors"] == [] and page["storyTitle"] == "This story isn't available"


@jsdom
def test_every_page_has_a_footer_and_a_link_preview(site):
    page = open_page(site, f"{BASE}/")
    assert page["footLinks"] == 6 and page["socialImage"] == f"{BASE}/brand/social.png"
    assert (site / "brand" / "social.png").exists() and (site / "brand" / "favicon.png").exists()


@jsdom
def test_page_says_when_it_could_not_read_a_feed(tmp_path, site):
    html = (site / "index.html").read_text()
    copy = tmp_path / "site"
    shutil.copytree(site, copy)
    source = next(iter(json.loads((site / "edition.json").read_text())["sources"]))
    (copy / "index.html").write_text(html.replace('"feeds_down": []', f'"feeds_down": ["{source}"]'))
    assert "couldn't read" in open_page(copy, f"{BASE}/")["notices"][0]


@jsdom
def test_about_page_shows_a_contact_address_only_when_there_is_one(tmp_path, site):
    assert open_page(site, f"{BASE}/")["contactEmail"] is None
    copy = tmp_path / "site"
    shutil.copytree(site, copy)
    html = (site / "index.html").read_text()
    (copy / "index.html").write_text(html.replace('"contact_email": ""', '"contact_email": "desk@example.org"'))
    assert "desk@example.org" in open_page(copy, f"{BASE}/")["contactEmail"]


def with_data(site, tmp_path, **changes):
    """A copy of the site whose page data has `changes` applied."""
    raw = (site / "edition.json").read_text()
    copy = tmp_path / "site"
    shutil.copytree(site, copy)
    html = (site / "index.html").read_text()
    assert raw.replace("</", "<\\/") in html
    new = json.dumps({**json.loads(raw), **changes}, ensure_ascii=False).replace("</", "<\\/")
    (copy / "index.html").write_text(html.replace(raw.replace("</", "<\\/"), new))
    return copy


@jsdom
def test_page_says_when_the_edition_is_old(tmp_path, site):
    page = open_page(with_data(site, tmp_path, edition="2026-10-01", sample=False), f"{BASE}/")
    assert page["errors"] == [] and "A newer one hasn't been published yet." in page["notices"][0]


@jsdom
def test_page_with_no_stories_says_so(tmp_path, site):
    page = open_page(with_data(site, tmp_path, stories=[]), f"{BASE}/")
    assert page["errors"] == [] and page["lede"] == "No stories in this edition."


@jsdom
def test_every_top_story_has_a_summary_and_a_picture_of_its_coverage(site):
    page = open_page(site, f"{BASE}/")
    assert page["errors"] == [] and page["summaries"] == 5 and page["plates"] >= 5
    assert page["leadRings"] == 3 and page["gapCircles"]


@jsdom
def test_story_page_shows_each_side_reposts_and_a_way_to_report_a_mistake(site):
    data = json.loads((site / "edition.json").read_text())
    storm = next(s for s in data["stories"] if "Port Avery" in s["headline"])
    page = open_page(site, f"{BASE}/#story-{storm['id']}")
    assert page["errors"] == [] and "What each side reported" in page["storyHeads"]
    assert page["sideSaid"] == [" ".join(storm["sides"][side]) for side in ("left", "center", "right")]
    assert any("same report as Capital Wire" in who for who in page["storySides"])
    lines = " ".join(page["storyLines"])
    assert "first outlet we read" in lines and "1 outlet repeated another's report, so this rests on 4 separate reports." in lines
    assert "template=wrong-story.yml" in page["wrongLink"] and "story=" in page["wrongLink"]
    assert "More on this topic" in page["storyHeads"] and page["relatedLinks"]


@jsdom
def test_a_side_alone_is_not_summarized(tmp_path, site):
    data = json.loads((site / "edition.json").read_text())
    storm = next(s for s in data["stories"] if "Port Avery" in s["headline"])
    left = next(sid for sid, src in data["sources"].items() if src["lean"] == "right")
    keep = [a["source_id"] for a in storm["articles"] if data["sources"][a["source_id"]]["lean"] == "center"]
    off = ",".join(sid for sid in {a["source_id"] for a in storm["articles"]} if sid not in keep)
    page = open_page(site, f"{BASE}/?exclude={off}#story-{storm['id']}")
    assert page["errors"] == [] and page["sideSaid"] == [] and "Who covered it" in page["storyHeads"]


@jsdom
def test_ledger_is_on_the_site_and_adds_up_from_its_rows(site):
    page = open_page(site, f"{BASE}/#ledger")
    book = ledger.load()
    assert page["errors"] == [] and page["ledgerLede"].endswith(" received.")
    assert f"${book['spent']:.2f} spent so far" in page["ledgerLede"]
    assert page["ledgerRows"] == len(book["money_out"]) and page["ledgerRules"] == len(book["rules"])
    assert "No donations are accepted yet" in page["ledgerIn"]
    assert page["title"] == "Public ledger | The Standard Edition" and page["tabCount"] == 7


def test_ledger_file_totals_match_its_rows():
    text = config.LEDGER_PATH.read_text()
    book = ledger.load()
    assert f"| Total spent | ${book['spent']:.2f} |" in text and f"| Total received | ${book['received']:.2f} |" in text


@jsdom
def test_a_market_value_that_lags_shows_its_own_date(tmp_path, site):
    markets = json.loads((site / "edition.json").read_text())["markets"]
    markets[-1]["date"] = "2026-10-30"
    page = open_page(with_data(site, tmp_path, markets=markets), f"{BASE}/")
    assert page["errors"] == [] and page["tickDates"] == ["Oct 30"]
    assert page["tickerLabel"].endswith("Last close, Nov 3")


@jsdom
def test_market_values_on_one_day_show_no_extra_dates(site):
    assert open_page(site, f"{BASE}/")["tickDates"] == []


def test_every_tab_opens_a_view():
    page = (config.ROOT / "web" / "index.html").read_text()
    views = re.findall(r'<a href="#[\w-]+" data-view="([\w-]+)"', page)
    assert "about" in views
    app = (config.ROOT / "web" / "app.js").read_text()
    for view in views:
        assert f'id="view-{view}"' in page and f'"{view}"' in app


def test_function_serves_custom_weights_and_a_named_feed(site, tmp_path):
    plain, weighted, same = serve(site, tmp_path, f"{BASE}/feed.xml", f"{BASE}/feed.xml?weights=0,0,0,100&recipe=Records",
                                  f"{BASE}/feed.xml?weights=40,25,10,25")
    assert same["body"] == plain["body"]
    root = ET.fromstring(weighted["body"]).find("channel")
    assert root.findtext("title") == "The Standard Edition (reader recipe: Records)"
    assert [i.findtext("title") for i in root.findall("item")] != \
        [i.findtext("title") for i in ET.fromstring(plain["body"]).findall("./channel/item")]


@jsdom
def test_front_page_shows_what_each_side_ran_and_what_one_side_missed(site):
    page = open_page(site, f"{BASE}/")
    assert page["errors"] == [] and page["oneSide"] and page["gapSides"]
    assert page["leadLink"].startswith("#story-")
    assert all(link.startswith("#story-") and link[1:] in page["anchors"] for link in page["oneSide"])


def test_page_is_a_real_document_that_fits_a_phone(site):
    html = (site / "index.html").read_text()
    assert html.lower().startswith("<!doctype html>")
    assert 'name="viewport"' in html.split("<style>")[0]
