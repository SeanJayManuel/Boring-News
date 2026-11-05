import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pytest

from boringnews import config, ingest, rubric
from boringnews.cluster import cluster
from boringnews.db import connect, load_edition, editions
from boringnews.edition import Edition
from boringnews.ingest import load_fixtures
from boringnews.pipeline import main as pipeline_main
from boringnews.reader import feeds
from boringnews.rewrite import fallback, lint, load_banned
from boringnews.sources import Source, load_sources

from .core import select

SOURCES = load_sources(config.FIXTURE_SOURCES_PATH)
BANNED = load_banned(config.BANNED_WORDS_PATH)


def src(*ids):
    return [SOURCES[i] for i in ids]


# ---------------------------------------------------------------- rubric

def test_cross_spectrum_scores_higher_than_one_sided():
    wide = rubric.score(src("northside-tribune", "capital-wire", "heartland-post"))
    narrow = rubric.score(src("heartland-post", "liberty-daily", "prairie-gazette"))
    assert wide.breadth == 1.0 and narrow.breadth == pytest.approx(1 / 3, abs=1e-3)
    assert wide.total > narrow.total


def test_one_sided_story_is_symmetric_left_and_right():
    left = rubric.score(src("northside-tribune", "metro-ledger", "bay-chronicle"))
    right = rubric.score(src("heartland-post", "liberty-daily", "prairie-gazette"))
    assert left.total == right.total


def test_thresholds_and_lanes():
    one_sided = rubric.score(src("heartland-post", "liberty-daily", "prairie-gazette"))
    assert rubric.lane(one_sided, "broad") == "main"
    assert rubric.lane(one_sided, "standard") is None
    primary = rubric.score(src("rules-register"))
    assert rubric.lane(primary, "strict", official=True) == "official"
    assert rubric.lane(primary, "strict", official=False) is None


def test_single_outlet_never_makes_main_lane():
    sc = rubric.score(src("capital-wire"))
    assert rubric.lane(sc, "broad") is None


def test_duplicate_outlet_counts_once():
    assert rubric.score(src("capital-wire", "capital-wire")).outlets == 1


# ---------------------------------------------------------------- clustering

def test_fixture_clusters_match_events():
    arts = load_fixtures(config.FIXTURE_ARTICLES_PATH)
    official = frozenset(sid for sid, s in SOURCES.items() if s.type == "primary")
    sizes = sorted((len(c) for c in cluster(arts, config.CLUSTER_SIMILARITY, separate=official)), reverse=True)
    assert sizes == [7, 4, 4, 4, 4, 3, 3, 3, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1]


# ---------------------------------------------------------------- linter and fallback writer

def test_linter_flags_loaded_words_outside_quotes():
    assert "ram through" in lint("Lawmakers ram through water bill", BANNED)
    assert lint('The mayor called it "a historic day"', BANNED) == []
    assert lint("Legislature passes water bill", BANNED) == []
    assert lint("Wire services report", BANNED) == []  # "wire" is not "war on"


def test_fallback_prefers_clean_wire_headline():
    arts = [a for a in load_fixtures(config.FIXTURE_ARTICLES_PATH) if "water" in a.url]
    draft = fallback(arts, SOURCES, BANNED)
    assert draft.headline == "Westmark legislature passes water rights bill"
    assert all(not lint(b, BANNED) for b in draft.bullets)


# ---------------------------------------------------------------- end to end

@pytest.fixture()
def edition_db(tmp_path):
    db = tmp_path / "t.db"
    assert pipeline_main(["run", "--fixtures", "--mock-llm", "--date", "2026-11-04", "--db", str(db)]) == 0
    conn = connect(db)
    yield conn
    conn.close()


def test_pipeline_is_idempotent(tmp_path):
    db = tmp_path / "t.db"
    for _ in range(2):
        pipeline_main(["run", "--fixtures", "--mock-llm", "--date", "2026-11-04", "--db", str(db)])
    conn = connect(db)
    assert editions(conn) == ["2026-11-04"]
    assert len(load_edition(conn, "2026-11-04")) == 17


def page_data(conn) -> dict:
    return Edition.load(conn, SOURCES).page_data("https://example.org", sample=True)


def test_prefs_filter_and_rescore(edition_db):
    data = page_data(edition_db)
    default = select(data)["items"]
    assert [s["lane"] for s in default].count("main") == 11
    assert [s["lane"] for s in default].count("official") == 4

    assert len(select(data, "threshold=broad")["items"]) == 17

    # Dropping every right-leaning outlet re-scores the water story but keeps it.
    no_right = select(data, "exclude=heartland-post,liberty-daily,prairie-gazette")["items"]
    water = [s for s in no_right if "water" in s["headline"].lower()][0]
    assert "right" not in water["leans"]

    only_states = select(data, "topics=states")["items"]
    assert {s["topic"] for s in only_states} == {"states"} and len(only_states) == 7


def test_prefs_query_round_trip(edition_db):
    data = page_data(edition_db)
    q = "topics=economy,government&exclude=npr&threshold=strict&official=0&spotlight=1"
    assert select(data, q)["query"] == q
    assert select(data)["query"] == ""


def test_bad_settings_fall_back_to_defaults(edition_db):
    data = page_data(edition_db)
    for q in ("threshold=constructor", "threshold=nonsense", "topics=constructor", "length=tiny"):
        assert select(data, q)["query"] == "", q
        assert len(select(data, q)["items"]) == 15, q


def test_rss_is_valid_xml(edition_db):
    root = ET.fromstring(feeds(page_data(edition_db), [""])[0])
    items = root.findall("./channel/item")
    assert len(items) == 15
    assert items[-1].find("title").text.startswith("Government ")


def test_feeds_fail_loudly_without_node(monkeypatch):
    monkeypatch.setattr("boringnews.reader.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="needs node"):
        feeds({}, [""])


def test_web_routes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import boringnews.web as web

    db = tmp_path / "t.db"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", "2026-11-04", "--db", str(db)])
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(web, "SAMPLE", True)
    client = TestClient(web.app)

    page = client.get("/")
    assert page.status_code == 200 and "Standard Edition" in page.text and "__DATA__" not in page.text
    feed = client.get("/feed.xml?topics=states&threshold=strict")
    assert feed.status_code == 200
    assert len(ET.fromstring(feed.content).findall("./channel/item")) == 7
    assert client.get("/feed.xml?date=1999-01-01").status_code == 404
    assert "/mcp" in client.get("/api/docs.md").text


# ---------------------------------------------------------------- official sources

from datetime import datetime, timezone

from boringnews.ingest import congress_items, federal_register_items
from boringnews.pipeline import cap_official
from boringnews.db import Article

SINCE = datetime(2026, 11, 3, tzinfo=timezone.utc)


def test_congress_keeps_only_meaningful_actions():
    data = {"bills": [
        {"congress": 119, "type": "HR", "number": "1234", "title": "Example Act",
         "latestAction": {"actionDate": "2026-11-03", "text": "Passed House by recorded vote, 220-210."}},
        {"congress": 119, "type": "S", "number": "99", "title": "Another Act",
         "latestAction": {"actionDate": "2026-11-03", "text": "Read twice and referred to the Committee on Finance."}},
        {"congress": 119, "type": "SJRES", "number": "7", "title": "Joint resolution",
         "latestAction": {"actionDate": "2026-11-04", "text": "Became Public Law No: 119-88."}},
        {"congress": 119, "type": "HR", "number": "5", "title": "Old Act",
         "latestAction": {"actionDate": "2026-10-01", "text": "Became Public Law No: 119-70."}},
    ]}
    items = congress_items(data, "congress", SINCE)
    assert [a.title for a in items] == ["H.R. 1234: Example Act", "S.J.Res. 7: Joint resolution"]
    assert items[0].url == "https://www.congress.gov/bill/119th-congress/house-bill/1234"
    assert items[1].url == "https://www.congress.gov/bill/119th-congress/senate-joint-resolution/7"


def test_federal_register_parsing():
    data = {"results": [{"title": "Safety Standard for Widgets", "abstract": "This rule sets a standard.",
                         "html_url": "https://www.federalregister.gov/d/2026-1", "publication_date": "2026-11-04",
                         "type": "Rule", "agencies": [{"name": "Consumer Product Safety Commission"}]}]}
    [a] = federal_register_items(data, "federal-register-rules")
    assert a.summary.startswith("Rule from Consumer Product Safety Commission.")
    assert a.published_at == "2026-11-04T12:00:00+00:00"


def test_official_items_are_capped_per_source():
    from boringnews.sources import Source
    srcs = {"gov": Source("gov", "Gov", "", "unrated", "primary", max_items=2),
            "paper": Source("paper", "Paper", "", "center", "national")}
    def art(i, sid="gov"):
        return Article(sid, f"https://x/{sid}/{i}", f"t{i}", "", f"2026-11-04T0{i}:00:00+00:00")
    clusters = [[art(i)] for i in range(5)] + [[art(9, "paper"), art(8)]]
    kept = cap_official(clusters, srcs)
    solo = [g for g in kept if len(g) == 1]
    assert len(solo) == 2 and {g[0].title for g in solo} == {"t4", "t3"}  # newest two
    assert any(len(g) == 2 for g in kept)  # covered by news: never capped


def test_source_topic_hint_used_by_fallback():
    arts = [a for a in load_fixtures(config.FIXTURE_ARTICLES_PATH) if "armory" in a.url]
    assert fallback(arts, SOURCES, BANNED).topic == "government"


# ---------------------------------------------------------------- v0.2: official record + spotlight

def test_official_record_raises_score():
    news = src("capital-wire", "northside-tribune", "liberty-daily")
    assert rubric.score(news + src("westmark-courts")).total == pytest.approx(rubric.score(news).total + 0.25, abs=1e-3)


def test_spotlight_is_top_five_covered_stories(edition_db):
    top = select(page_data(edition_db), "spotlight=1")["items"]
    assert len(top) == rubric.SPOTLIGHT and all(x["lane"] == "main" for x in top)
    assert [x["total"] for x in top] == sorted((x["total"] for x in top), reverse=True)
    # The two stories backed by an official record lead the day.
    assert {x["topic"] for x in top[:2]} == {"economy", "states"}


def test_official_documents_from_one_source_stay_separate():
    arts = [a for a in load_fixtures(config.FIXTURE_ARTICLES_PATH) if a.source_id == "rules-register"]
    assert len(cluster(arts, config.CLUSTER_SIMILARITY, separate=frozenset({"rules-register"}))) == 2


# ---------------------------------------------------------------- v0.3: records vs statements

def test_statements_never_add_to_score():
    news = src("capital-wire", "northside-tribune", "liberty-daily")
    with_statement = rubric.score(news + src("westmark-defense"))
    assert with_statement.total == rubric.score(news).total
    assert with_statement.has_statement and not with_statement.has_record


def test_records_add_to_score():
    sc = rubric.score(src("westmark-labor"))
    assert sc.has_record and sc.record == 1.0 and sc.total == 0.25


def test_statements_can_be_turned_off(edition_db):
    data = page_data(edition_db)
    on, off = select(data)["items"], select(data, "statements=0")
    assert any(x["hasStatement"] for x in on)
    assert not any(x["hasStatement"] for x in off["items"])
    assert len(on) - len(off["items"]) == 1  # the armory contract press release
    assert off["query"] == "statements=0"


def test_official_sources_default_to_statement(tmp_path):
    from boringnews.sources import load_sources
    p = tmp_path / "s.yaml"
    p.write_text("sources:\n  - {id: agency, name: Agency, url: x, type: primary}\n")
    assert load_sources(p)["agency"].role == "statement"


# ---------------------------------------------------------------- Congress.gov

SIGNED = {"type": "HR", "number": "12", "congress": 119, "title": "A Test Act",
          "latestAction": {"actionDate": "2026-11-04", "text": "Signed by President."}}
BILL_SINCE = datetime(2026, 11, 3, tzinfo=timezone.utc)


def congress_api(monkeypatch, pages, summaries=None):
    calls = []

    def fake(url, params):
        calls.append((url, params))
        if url.endswith("/summaries"):
            if isinstance(summaries, Exception):
                raise summaries
            return {"summaries": summaries or []}
        return {"bills": pages[params["offset"] // 250]}

    monkeypatch.setenv("CONGRESS_API_KEY", "x")
    monkeypatch.setattr(ingest, "_get_json", fake)
    return calls


def fetch(pages=None):
    src = Source(id="congress", name="Congress.gov", url="x", lean="unrated", type="primary", fetcher="congress")
    return ingest.fetch_congress(src, BILL_SINCE)


def test_every_page_of_bills_is_read(monkeypatch):
    noise = {**SIGNED, "latestAction": {"actionDate": "2026-11-04", "text": "Referred to committee."}}
    calls = congress_api(monkeypatch, [[noise] * 250, [noise] * 250, [SIGNED]])
    assert len(fetch()) == 1
    assert [p["offset"] for u, p in calls if not u.endswith("/summaries")] == [0, 250, 500]


def test_a_bill_carries_its_latest_nonpartisan_summary(monkeypatch):
    congress_api(monkeypatch, [[SIGNED]], [
        {"actionDesc": "Introduced in House", "updateDate": "2026-01-01T00:00:00Z", "text": "<p>Old text.</p>"},
        {"actionDesc": "Passed House", "updateDate": "2026-06-01T00:00:00Z", "text": "<p>This bill does a thing.</p>"},
    ])
    summary = fetch()[0].summary
    assert summary == ("Latest action on 2026-11-04: Signed by President. "
                       "Congressional Research Service summary (Passed House): This bill does a thing.")


def test_a_bill_without_a_summary_is_still_a_record(monkeypatch):
    congress_api(monkeypatch, [[SIGNED]])
    assert fetch()[0].summary == "Latest action on 2026-11-04: Signed by President."


def test_a_failed_summary_call_keeps_the_bill(monkeypatch):
    congress_api(monkeypatch, [[SIGNED]], OSError("no route"))
    assert fetch()[0].summary == "Latest action on 2026-11-04: Signed by President."


def test_only_kept_bills_cost_a_summary_call(monkeypatch):
    noise = {**SIGNED, "number": "13", "latestAction": {"actionDate": "2026-11-04", "text": "Referred to committee."}}
    calls = congress_api(monkeypatch, [[noise, SIGNED]])
    fetch()
    assert [u for u, _ in calls if u.endswith("/summaries")] == [ingest.CONGRESS_API + "/119/hr/12/summaries"]


def test_public_laws_come_from_congress_gov_not_a_second_source():
    assert "public-laws" not in load_sources(config.SOURCES_PATH)
