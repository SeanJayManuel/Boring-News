# Boring News

https://boringnews.org

The day's news, once a day. Stories are chosen by a published rule (covered
across left, center and right), rewritten in plain wire-service language,
and linked back to every source. Readers can change what they see, and every
setting carries over to their RSS feed.

## Quick start (demo data, no API key)

```bash
python -m venv .venv && source .venv/bin/activate
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
   `CLOUDFLARE_ACCOUNT_ID`.

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
          web page + /feed.xml ◄── prefs (URL query) ◄── store ◄── rewrite (Claude + linter)
```

| File | What it does |
| --- | --- |
| `sources.yaml` | Outlets, each with a lean (left / center / right / unrated) and a type |
| `editorial/style_guide.md` | The writing rules, sent to the model as its instructions |
| `editorial/banned_words.txt` | Loaded words the linter rejects outside quotes |
| `boringnews/rubric.py` | Selection rule: breadth, coverage, diversity, thresholds |
| `boringnews/cluster.py` | Groups articles about the same event |
| `boringnews/rewrite.py` | Claude writer, linter, retry, and no-model fallback |
| `boringnews/prefs.py` | Reader settings from the query string; filtering and re-scoring |
| `boringnews/feeds.py` | RSS 2.0 output |
| `boringnews/web.py` | FastAPI app: `/`, `/feed.xml`, `/api/edition.json` |
| `boringnews/export_static.py` | Static site export (page, default feed, one feed per topic) |
| `web/` | The reader page; `app.js` mirrors the rubric so settings apply instantly |

## Reader settings (work on the page and the feed)

| Parameter | Values | Default |
| --- | --- | --- |
| `topics` | comma list: politics, congress, defense, economy, world, science-health, tech, regulation, courts, local-state | all |
| `regions` | comma list: us-national, us-state, world | all |
| `exclude` | comma list of source ids | none |
| `threshold` | broad (0.30), standard (0.40), strict (0.55) | standard |
| `official` | 1 or 0: include official items no outlet has covered yet | 1 |
| `statements` | 1 or 0: include official statements (press releases) | 1 |
| `spotlight` | 1: only the top 5 stories | 0 |
| `length` | full or headlines | full |

Example: `/feed.xml?topics=economy,courts&threshold=strict&exclude=ny-post`

## Settings

Environment variables: `BN_DB`, `BN_SOURCES`, `BN_BASE_URL` (used in feed
links), `BN_MODEL` (default `claude-haiku-5-5`), `BN_LOOKBACK_HOURS`,
`BN_CLUSTER_SIMILARITY` (default 0.15, tuned on the sample data; re-tune on
real feeds), `BN_SAMPLE=1` (serve the sample source list).

## Free and open

Boring News is free to read and free to copy: no ads, no accounts, no
tracking. Reader settings live in the browser and in the feed address. The
code is MIT-licensed; the rules that pick stories (`boringnews/rubric.py`),
the source list (`sources.yaml`) and the writing rules (`editorial/`) are
public, and every change to them is a public commit.

## Tests

```bash
pytest -q
```

## Notes

- Only titles and short summaries from feeds are stored; pages show original
  summaries and link out. Never republish full articles.
- Lean labels are starting assumptions. Publish them and revisit quarterly.
- Reuters and AP do not offer public RSS feeds.
