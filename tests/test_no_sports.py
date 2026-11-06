"""No sports in the edition: the rule, run through the whole pipeline. URLs have the
shapes real feeds use (The Guardian, the New York Post, CBS); all the text is invented."""

import json

from boringnews import archive, config, rubric
from boringnews.db import Article, connect, load_edition
from boringnews.inputs import FixtureInputs
from boringnews.pipeline import run
from boringnews.sources import load_sources

SOURCES = load_sources(config.FIXTURE_SOURCES_PATH)
DATE = "2026-11-04"
LEFT, CENTER, RIGHT, COURT = "northside-tribune", "capital-wire", "heartland-post", "westmark-courts"
GUARDIAN = "https://www.theguardian.com/sport/2026/nov/04/"
POST = "https://nypost.com/2026/11/04/sports/"
CBS = "https://www.cbsnews.com/video/"
NEWS = "https://www.theguardian.com/us-news/2026/nov/04/"


def art(source_id, url, title, summary=""):
    return Article(source_id, url, title, summary or title, f"{DATE}T12:00:00+00:00")


def three_outlets(words, first=GUARDIAN, second=POST, third=CBS):
    """One event, reported by a left, a right and a center outlet."""
    title = " ".join(words)
    return [art(LEFT, f"{first}{words[0]}-one", title), art(RIGHT, f"{second}{words[0]}-two", title),
            art(CENTER, f"{third}{words[0]}-three", title)]


class Feeds(FixtureInputs):
    def __init__(self, articles):
        super().__init__(SOURCES)
        self.given = articles

    def articles(self, since=None):
        return self.given, []


class Spy:
    """A writer that keeps what it was sent, then fails, so the fallback writes the story."""
    model = "spy"
    checks_facts = False
    usage = None

    def __init__(self):
        self.sent = []

    def complete(self, system, messages):
        self.sent.append(json.dumps(messages))
        raise TimeoutError


def edition(tmp_path, articles, writer=None):
    run(Feeds(articles), writer, tmp_path / "t.db", DATE, tmp_path / "a")
    file = json.loads((tmp_path / "a" / f"{DATE}.json").read_text())
    return load_edition(connect(tmp_path / "t.db"), DATE), file


def written(stories):
    return {a.url for s in stories for a in s.articles}


def assert_kept(stories, file, arts):
    assert written(stories) == {a.url for a in arts}
    assert file["left_out"]["sports"]["groups"] == []


def test_a_group_mostly_from_sports_sections_is_not_written_and_is_on_the_record(tmp_path):
    sports = three_outlets(["quarterback", "zanetti", "shoulder", "recovery"])
    news = three_outlets(["harbor", "dredging", "contract", "awarded"], NEWS, NEWS, NEWS)
    spy = Spy()
    stories, file = edition(tmp_path, sports + news, spy)

    assert written(stories) == {a.url for a in news}
    assert spy.sent and not any("zanetti" in sent for sent in spy.sent)  # nothing was spent on it
    record = file["left_out"]["sports"]
    assert len(record["groups"]) == 1
    group = record["groups"][0]
    assert sorted(group["articles"]) == sorted(a.url for a in sports)
    assert sorted(group["from_sports_sections"]) == sorted(a.url for a in sports[:2])
    assert sorted(group["titles"]) == sorted(a.title for a in sports)
    assert group["score"]["total"] >= rubric.THRESHOLDS["broad"]
    assert sorted(a.url for a in sports) in [sorted(g) for g in file["clusters"]]  # the grouping stays public


def test_the_edition_file_publishes_the_rule_even_when_nothing_was_dropped(tmp_path):
    _, file = edition(tmp_path, three_outlets(["harbor", "dredging"], NEWS, NEWS, NEWS))
    record = file["left_out"]["sports"]
    assert record["groups"] == []
    assert record["rule"]["sections"] == list(rubric.SPORTS_SECTIONS)
    assert record["rule"]["keep_words"] == list(rubric.HARD_NEWS_WORDS)


def test_an_edition_file_with_a_dropped_group_still_restores(tmp_path):
    arts = three_outlets(["quarterback", "zanetti"]) + three_outlets(["harbor", "dredging"], NEWS, NEWS, NEWS)
    stories, file = edition(tmp_path, arts)
    assert file["format"] == 2 and file["left_out"]["sports"]["groups"]
    assert archive.restore(tmp_path / "a", tmp_path / "r.db") == 1
    assert written(load_edition(connect(tmp_path / "r.db"), DATE)) == written(stories)


def test_an_even_split_is_kept(tmp_path):
    arts = [art(LEFT, f"{POST}zanetti-signing", "Zanetti signing announced by the club"),
            art(RIGHT, f"{NEWS}zanetti-signing", "Zanetti signing announced by the club today")]
    assert_kept(*edition(tmp_path, arts), arts)


def test_one_prolific_sports_desk_does_not_outvote_two_outlets(tmp_path):
    arts = [art(LEFT, f"{POST}zanetti-{n}", f"Zanetti signing announced by the club, part {n}") for n in range(4)]
    arts += [art(RIGHT, f"{NEWS}zanetti", "Zanetti signing announced by the club, a report"),
             art(CENTER, f"{CBS}zanetti", "Zanetti signing announced by the club, a video")]
    assert_kept(*edition(tmp_path, arts), arts)


def test_an_outlet_with_a_news_desk_piece_too_does_not_count_as_sports(tmp_path):
    arts = three_outlets(["quarterback", "zanetti", "shoulder"])
    arts.append(art(RIGHT, f"{NEWS}quarterback-zanetti", "quarterback zanetti shoulder news desk report"))
    assert_kept(*edition(tmp_path, arts), arts)


def test_a_group_with_an_official_source_is_never_dropped(tmp_path):
    arts = three_outlets(["quarterback", "zanetti", "shoulder"], GUARDIAN, POST, POST)
    arts.append(art(COURT, "https://courts.example.gov/opinions/9988", "quarterback zanetti shoulder opinion filed"))
    assert_kept(*edition(tmp_path, arts), arts)


def test_an_official_item_on_its_own_is_never_dropped(tmp_path):
    item = art(COURT, "https://courts.example.gov/sports/9988", "Opinion on the state athletic commission")
    assert_kept(*edition(tmp_path, [item]), [item])


def test_real_news_filed_on_a_sports_desk_is_kept(tmp_path):
    headlines = ["Stadium bond vote set for county residents",
                 "New sports betting law takes effect in Westmark",
                 "Veteran pitcher charged with fraud in Westmark",
                 "Antitrust ruling against the basketball league stands"]
    for n, headline in enumerate(headlines):
        arts = three_outlets(headline.split(), GUARDIAN, POST, POST)
        assert_kept(*edition(tmp_path / str(n), arts), arts)


def test_those_words_keep_a_story_only_as_words_of_their_own(tmp_path):
    # "Lawson" isn't "law", "Bonds" isn't "bond vote", "Senators" isn't "Senate".
    arts = three_outlets("Lawson traded as Senators chase Bonds record".split())
    stories, _ = edition(tmp_path, arts)
    assert stories == []


def test_one_title_with_a_keep_word_keeps_the_group(tmp_path):
    arts = three_outlets(["zanetti", "quarterback", "shoulder", "injury"])
    arts[2] = art(CENTER, f"{CBS}zanetti", "zanetti quarterback shoulder injury lawsuit filed")
    assert_kept(*edition(tmp_path, arts), arts)


def test_only_a_whole_section_of_the_path_counts(tmp_path):
    arts = [art(LEFT, "https://news.test/us-news/sports-betting-rises", "Harbor dredging plan advances in the state"),
            art(RIGHT, "https://news.test/transport/sports/", "Harbor dredging plan advances in the state today"),
            art(CENTER, "https://news.test/sportswashing?section=sports", "Harbor dredging plan advances in the state now")]
    # One of three is in a /sports/ section; the slug, a longer word and the query don't count.
    assert_kept(*edition(tmp_path, arts), arts)


def test_the_rule_reads_the_section_in_any_case_and_on_any_site(tmp_path):
    arts = three_outlets(["quarterback", "zanetti"], "https://a.test/SPORT/", "https://b.test/news/football/", CBS)
    stories, file = edition(tmp_path, arts)
    assert stories == [] and len(file["left_out"]["sports"]["groups"]) == 1
