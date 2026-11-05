# Boring News

*Working name. A permanent name is being chosen.*

**All the news, from every side, with nothing hidden. Free forever.**

Boring News is a free, open-source daily news edition. It reads reporting from outlets across the political spectrum, alongside official records from government, and shows you exactly how it decides what to put in front of you. You can read the rules, change the rules, or throw them out and write your own.

---

## Why this exists

Most people think media bias is about how a story is written. The bigger bias is which stories get told at all.

Every feed you read, whether it's a newspaper front page, a cable lineup, or an app, is the output of choices you never see: which sources are included, which are left out, what gets promoted, what gets buried. Some of those choices are editorial. Many are commercial. Almost none are disclosed.

News aggregators were supposed to fix this. Instead most of them became another layer of hidden choices, funded by ads, subscriptions or investors, and tuned for attention.

Boring News takes the opposite position. A news feed is a set of decisions, and anyone reading it has a right to see those decisions, question them, and change them.

## What we believe

1. **Free, permanently.** No ads, no paywall, no premium tier, no accounts, no selling or renting user data. The whole thing is free to read and free to copy.

2. **Every decision is visible.** The code, the list of sources, how each source is labeled, how stories are grouped, how they're ranked, and how they're written are all public, and explained in plain language as well as in code.

3. **The reader owns the algorithm.** The default rules are a starting point, not a verdict. If you only want certain outlets, certain topics, or only government records, that's your call. We'll show you what you're filtering out; we won't stop you.

4. **Show the whole spread.** For every story, you can see which outlets across the spectrum covered it, and which didn't. A story that only one side is talking about is information in itself.

5. **Official records sit next to the reporting.** Laws, rules, court rulings and votes appear beside the coverage of them, so readers can check the source themselves.

6. **Local news matters as much as national.** What your school board and city council decide often affects you more than what happens in Washington. State and municipal news are on the roadmap as first-class coverage, not an afterthought.

7. **Boring on purpose.** Once a day. No outrage optimization, no infinite scroll, no engagement metrics deciding what you see. Plain language, clear sourcing, done.

8. **Open books.** Every dollar in and every dollar out is published in [`LEDGER.md`](LEDGER.md). If donations ever exist, they exist only to keep the servers running, and the ledger shows it.

9. **No tracking.** No third-party analytics, no ad pixels, no profiles. Your settings live in your browser and your feed address.

## What Boring News is not

- **Not a newsroom.** We don't do original reporting. Each story is a short, plain summary of what the outlets reported, held to a [published style guide](editorial/style_guide.md) and checked against its sources, with a link to every source. Full articles are never republished; traffic goes to the people who did the reporting.
- **Not a fact-checker.** We show where coverage comes from and how it's spread. Judging what's true is the reader's job, and we try to give them what they need to do it.
- **Not a business.** There's no growth target, no exit, and nothing to sell.

## How the decisions are made

Any change to sources, labels, grouping, ranking or writing rules is a public commit, and must update the matching document in the same commit.

| Decision | Plain-language explanation | Where it lives in code |
| --- | --- | --- |
| Which sources are read | [`docs/labeling.md`](docs/labeling.md) | [`sources.yaml`](sources.yaml) |
| How outlets are labeled left, center or right | [`docs/labeling.md`](docs/labeling.md) | [`boringnews/sources.py`](boringnews/sources.py) |
| How articles are grouped into stories | [`docs/clustering.md`](docs/clustering.md) | [`boringnews/cluster.py`](boringnews/cluster.py) |
| Which stories make the edition | [`docs/ranking.md`](docs/ranking.md) | [`boringnews/rubric.py`](boringnews/rubric.py) |
| How stories are written | [`editorial/style_guide.md`](editorial/style_guide.md) | [`boringnews/rewrite.py`](boringnews/rewrite.py) |
| What was wrong and fixed | [`corrections.yaml`](corrections.yaml) | |

Every edition is also saved in full to [`archive/`](archive/): every article read, how they were grouped, every score, the fact-check log, and the version of the rules used that day.

## For journalists, students and researchers

Boring News is meant to be useful to anyone covering a beat, including student papers, community newsletters and freelancers without a wire subscription.

- **Now:** a Research tab to look up which outlets covered a claim and search 30 days of government records; RSS for any combination of settings; full edition files in `archive/`; and a free [public API and MCP server](docs/api.md), with no accounts or keys (ready, but not deployed yet).
- **Planned:** per-state and per-city feeds including council and board agendas.

## Roadmap

United States first. International coverage starts only once US coverage is solid. The feature-by-feature plan, with what's missing for each, is in [`docs/roadmap.md`](docs/roadmap.md).

**Phase 1: National edition** (built)
- [x] Read outlet RSS feeds across left, center and right
- [x] Group articles into stories
- [x] Published selection rubric, with balanced weighting so no side counts more
- [x] Plain-language summaries, banned-word linter and fact check
- [x] Website and RSS output, nightly build
- [x] Full daily edition files and corrections log

**Phase 2: Reader control** (mostly built)
- [x] Choose topics, exclude sources, set the threshold, on the page and in the feed
- [x] Adjust the rubric weights themselves, not just the threshold
- [x] Save and share settings as a "feed recipe"
- [x] See every story your settings hide, and why
- [ ] Blind-spot view: stories covered heavily by one side and barely by the other

**Phase 3: Federal records** (partly built)
- [x] Congress, public laws, Federal Register rules, presidential documents
- [x] Records vs. statements, so press releases can't lift a story
- [ ] Federal court opinions and agency reports (GAO and others)
- [ ] Supreme Court opinions (no public RSS; needs another route)

**Phase 4: State and local**
- [ ] One state and a few cities first, done properly (California: San Mateo County and nearby cities)
- [ ] State legislature bills and votes
- [ ] City council and school board agendas and minutes
- [ ] A guide for anyone to add their own city's sources
- [ ] Expand state by state until US coverage is solid

**Phase 5: Open data**
- [x] Public API, MCP server and data downloads for journalists and researchers (built, not deployed)

**Phase 6: Open books**
- [x] Public ledger from day one
- [ ] Donation page, with every donation shown in the ledger

**Later: Beyond the US**
- Only once US coverage is solid. Each country gets its own spectrum, sources and government feeds rather than inheriting American labels.

## The money

| | |
| --- | --- |
| Revenue | $0 |
| Expenses | See [`LEDGER.md`](LEDGER.md) |
| Ads | Never |
| Investors | Never |

If donations are ever accepted, every one will appear in the ledger (amounts, with names only if the donor opts in), alongside every expense. Donations will never buy influence over sources, labels, ranking or writing.

## Open questions

These are real, unsolved, and we'd like help:

- **Who decides what "left," "center" and "right" mean?** Every rating system has critics. How do we label outlets in a way people on all sides find fair, and show disagreement honestly?
- **Government sources aren't neutral either.** Records and statements are already separated, but how should an agency's own framing of a record be presented?
- **Summaries are choices too.** A neutral summary still decides what to include. How do we make that process as checkable as the ranking?
- **How do we avoid becoming the gatekeeper we're replacing?** Every inclusion decision is a choice. The answer is probably making those decisions public and contestable, but the process needs work.

## Contributing

Anyone can propose a new source, challenge a label, or suggest a rubric change by [opening an issue](https://github.com/SeanJayManuel/Boring-News/issues/new/choose) or pull request. Changes to sources, labels, ranking or writing rules need a written reason in the pull request, and the matching document in `docs/` or `editorial/` updated in the same change, so anyone can see why the edition works the way it does.

## License

Code: [AGPL-3.0](LICENSE). Anyone can use, copy or change Boring News, but anyone who runs a modified version publicly has to publish their changes too. That keeps it open.

Docs, source lists and editorial rules: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

---

# Running it

## Quick start (demo data, no API key)

Needs Python 3.10 or newer, and Node.js for the RSS feeds and the tests.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Build a demo edition from invented sample articles
python -m boringnews.pipeline run --fixtures --mock-llm --date 2026-11-04

# Serve it
BN_SAMPLE=1 uvicorn boringnews.web:app --reload
# open http://localhost:8000 and http://localhost:8000/feed.xml
```

`--mock-llm` uses canned example rewrites in `fixtures/rewrites.json` so you
can see the target style. Leave it off to see the no-model fallback writer.

## Real feeds

```bash
export CONGRESS_API_KEY=...                        # free: https://api.congress.gov/sign-up/
export FRED_API_KEY=...                            # free: https://fred.stlouisfed.org/docs/api/api_key.html
export ANTHROPIC_API_KEY=...                       # optional; without it, the fallback writer is used
# Or use any OpenAI-compatible server (Ollama, llama.cpp) instead of a paid key:
# export BN_WRITER_URL=http://localhost:11434 BN_WRITER_MODEL=llama3.2
python -m boringnews.pipeline check-feeds          # which sources work, and which look stale
python -m boringnews.pipeline run                  # today's edition, UTC
# Add --require-writer to stop rather than publish fallback stories (the nightly job does)
uvicorn boringnews.web:app
```

## Official sources

These come straight from the government, in two roles:

- **Records** have legal or statistical standing: laws, rules, court rulings,
  votes, official statistics. When news outlets cover the same event, a record
  adds the `record` part of the score (25%), so stories on the record rank higher.
- **Statements** are an institution describing its own work, like a press
  release. They are listed and labeled "Official statement" but never add to
  the score, so no administration's messaging can lift a story. Readers can
  hide them with `statements=0`.

Every official source must say `role: record` to earn the boost; anything
without a role is treated as a statement.

| Source | Role | How | Key |
| --- | --- | --- | --- |
| Congress.gov | record | API; only bills that passed a chamber, went to the President, were signed or vetoed, with the Congressional Research Service summary when there is one. New laws arrive here, on the day they're signed | `CONGRESS_API_KEY` |
| Federal Register significant rules | record | API | none |
| Federal Register presidential documents | record | API (executive orders as legally published) | none |
| White House presidential actions | statement | RSS | none |
| Department of War news releases | statement | RSS (check-feeds flags it if it goes stale) | none |

Each has a `max_items` cap in `sources.yaml` so busy days don't flood the
edition. GovInfo publishes about 250 more official feeds (Congressional
Record, GAO reports, federal court opinions); any of them can be added as a
`type: primary` source. The Supreme Court does not publish an RSS feed.

## Hosting (boringnews.org)

The site is static files plus one Cloudflare Pages function,
`functions/feed.xml.js`, which builds each custom feed on request from
`edition.json` using the same rubric code as the page (`web/core.js`).
GitHub Pages can't run functions, so custom feed addresses would silently
return the default feed there.

One-time setup:

1. Create a free Cloudflare account and a Pages project named `boring-news`
   (Workers & Pages → Create → Pages → Direct upload; the workflow uploads to it).
2. Add `boringnews.org` as a custom domain on that project. If the domain is
   registered elsewhere, point its nameservers to Cloudflare first.
3. In the GitHub repo, add these secrets: `ANTHROPIC_API_KEY`, `CONGRESS_API_KEY`,
   `CLOUDFLARE_API_TOKEN` (a token with "Cloudflare Pages: Edit") and
   `CLOUDFLARE_ACCOUNT_ID`, plus `FRED_API_KEY` for the market ticker.

The nightly workflow then builds the edition, exports the site and deploys it.
To host somewhere without functions, export with `--static-feed` to get a
fixed default `feed.xml`.

Run `pipeline run` once a day (cron, or the GitHub Actions workflow in
`.github/workflows/nightly.yml`). Re-running for the same date replaces that
edition.

## Pipeline

```
sources.yaml ──► ingest (RSS) ──► SQLite ──► cluster (TF-IDF) ──► score (rubric)
                                                                     │
          web page + /feed.xml ◄── web/core.js (URL query) ◄── edition ◄── rewrite (Claude + linter)
```

| File | What it does |
| --- | --- |
| `sources.yaml` | Outlets, each with a lean (left / center / right / unrated) and a type |
| `editorial/style_guide.md` | The writing rules, sent to the model as its instructions |
| `editorial/banned_words.txt` | Loaded words the linter rejects outside quotes |
| `boringnews/rubric.py` | Selection rule: breadth, coverage, diversity, thresholds |
| `boringnews/cluster.py` | Groups articles about the same event |
| `boringnews/rewrite.py` | Writers, the parsing, retry and lint rules for their text, fact check, no-model fallback |
| `boringnews/inputs.py` | Where articles and market closes come from: live or the sample data |
| `boringnews/edition.py` | One edition and all its forms: database, edition file, page data |
| `boringnews/reader.py` | Asks `web/core.js` for RSS feeds, through node |
| `boringnews/research.py` | The 30-day index behind the Research tab |
| `boringnews/web.py` | Local preview, FastAPI: `/`, `/feed.xml`, `/api/edition.json` |
| `boringnews/export_static.py` | Static site export (page, data, one feed per topic) |
| `web/core.js` | What readers' settings do: selection, scores, the settings list, RSS, plus the research tools. Used by the page, the feed function and Python |
| `web/app.js` | The reader page |

## Reader settings (work on the page and the feed)

| Parameter | Values | Default |
| --- | --- | --- |
| `topics` | comma list of categories: government, states, economy, world, health-science, tech | all |
| `exclude` | comma list of source ids | none |
| `threshold` | broad (0.30), standard (0.40), strict (0.55) | standard |
| `weights` | four whole numbers, 0 to 100, for breadth, coverage, diversity and record, each counted as its share. Re-ranks written stories only | the published rule |
| `official` | 1 or 0: include official items no outlet has covered yet | 1 |
| `statements` | 1 or 0: include official statements (press releases) | 1 |
| `spotlight` | 1: only the top 5 stories | 0 |
| `length` | full or headlines | full |
| `recipe` | a name for this setup, up to 60 characters | none |

Example: `/feed.xml?topics=economy,government&threshold=strict&exclude=ny-post`

## Settings

Environment variables: `BN_DB`, `BN_SOURCES`, `BN_BASE_URL` (used in feed
links), `BN_MODEL` (default `claude-haiku-5-5`), `BN_WRITER_URL` and
`BN_WRITER_MODEL` (write with any OpenAI-compatible server, such as Ollama or
llama.cpp, instead of Claude; the URL is the server's base address and the model
name is published with each story), `BN_LOOKBACK_HOURS`,
`BN_CLUSTER_SIMILARITY` (default 0.15, tuned on the sample data; re-tune on
real feeds), `BN_CLUSTER_WINDOW_HOURS`, `BN_THREAD_SIMILARITY`, `BN_ARCHIVE`,
`BN_REPO_URL`, `BN_SAMPLE=1` (serve the sample source list).

## Market ticker

The strip at the top of the page shows the previous trading day's closes
(stock indexes, Treasury yields, oil and the US dollar) from FRED, the St. Louis
Fed's data service. Edit `markets.yaml` to change the list. It updates once a
day with the edition; if FRED can't be reached the ticker is hidden and the
edition still publishes.

Before launch, check each series' notes on FRED: the S&P 500 and Dow series
are copyrighted by S&P Dow Jones Indices and FRED says reproducing them needs
the owner's permission. Remove any series you can't use.

## Research tools

The Research tab has two free tools for reporters and anyone checking a claim.
Both run in the browser over `research.json`, the last 30 days of editions,
which the export writes next to the page.

- **Look up coverage:** paste a claim, headline or link. It shows which outlets
  covered the matching story (grouped left, center, right), which didn't, and
  any government record behind it, with a copyable citation. It describes
  coverage only; it never says whether a claim is true.
- **Search government records:** every bill, rule, ruling and statement read
  in the last 30 days, filtered by source, kind, and whether any outlet
  covered it.

## Transparency features

- **Balanced coverage.** Outlets are weighted so each side of the spectrum
  counts equally toward coverage, however many outlets of each lean are on
  the list (`weight` in `sources.py`, shown as "Counts as" on the site).
- **Rating inputs.** A source can list ratings from several services instead
  of a single `lean`:
  ```yaml
  - id: example
    ratings: {ServiceA: lean left, ServiceB: center}   # left, lean left, center, lean right, right
  ```
  Its lean becomes their average, and the raters are shown on the site. Fill
  these in from each service's current published rating.
- **Fact check.** Every bullet is checked against its sources before
  publishing: numbers must appear in the sources, and with an API key a second
  model call confirms each bullet. Removed bullets are logged with the reason
  and shown under the story.
- **Edition files.** Each run writes `archive/YYYY-MM-DD.json`: every article
  read, how they were grouped, every score, the fact-check log, the rubric
  version and hashes of the editorial files. These files are the project's
  storage (committed nightly, published at `/archive/`), and
  `python -m boringnews.archive restore` rebuilds the database from them.
- **Developing stories.** A story that continues from the previous edition
  keeps its thread and shows "Day 2", "Day 3" (`boringnews/threads.py`).
- **Corrections.** `corrections.yaml` is published under How it works.

## Tests

```bash
npm install     # test-only: jsdom runs the reader page
pytest -q
```

The site itself has no npm dependencies.

## Notes

- Only titles and short summaries from feeds are stored; pages show original
  summaries and link out. Never republish full articles.
- Lean labels are starting assumptions. Publish them and revisit quarterly.
- Reuters and AP do not offer public RSS feeds.
