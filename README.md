# Boring News

https://boringnews.org

The day's news, once a day. Stories are chosen by a published rule (covered
across left, center and right), rewritten in plain wire-service language,
and linked back to every source. Readers can change what they see, and every
setting carries over to their RSS feed.

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
python -m boringnews.pipeline check-feeds          # which sources work, and which look stale
python -m boringnews.pipeline run                  # today's edition, UTC
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
| Congress.gov | record | API; only bills that passed a chamber, went to the President, were signed or vetoed | `CONGRESS_API_KEY` |
| GovInfo public laws | record | RSS | none |
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

## How it works

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
| `boringnews/web.py` | Local preview, FastAPI: `/`, `/feed.xml`, `/api/edition.json` |
| `boringnews/export_static.py` | Static site export (page, data, one feed per topic) |
| `web/core.js` | What readers' settings do: selection, scores, the settings list, RSS. Used by the page, the feed function and Python |
| `web/app.js` | The reader page |

## Reader settings (work on the page and the feed)

| Parameter | Values | Default |
| --- | --- | --- |
| `topics` | comma list of categories: government, states, economy, world, health-science, tech | all |
| `exclude` | comma list of source ids | none |
| `threshold` | broad (0.30), standard (0.40), strict (0.55) | standard |
| `official` | 1 or 0: include official items no outlet has covered yet | 1 |
| `statements` | 1 or 0: include official statements (press releases) | 1 |
| `spotlight` | 1: only the top 5 stories | 0 |
| `length` | full or headlines | full |

Example: `/feed.xml?topics=economy,government&threshold=strict&exclude=ny-post`

## Settings

Environment variables: `BN_DB`, `BN_SOURCES`, `BN_BASE_URL` (used in feed
links), `BN_MODEL` (default `claude-haiku-5-5`), `BN_LOOKBACK_HOURS`,
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

## Free and open

Boring News is free to read and free to copy: no ads, no accounts, no
tracking. Reader settings live in the browser and in the feed address. The
code is MIT-licensed; the rules that pick stories (`boringnews/rubric.py`),
the source list (`sources.yaml`) and the writing rules (`editorial/`) are
public, and every change to them is a public commit.

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
