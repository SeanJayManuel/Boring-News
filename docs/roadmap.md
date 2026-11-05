# Roadmap

The detailed plan behind the summary in the [README](../README.md). Each feature has a stable ID so it can be worked through one at a time: what it is, what already exists, what's missing, what it needs from a person, and how we'll know it's done.

Status as of 2026-11-05.

**Status:** ✅ built · 🟡 partly built · ⬜ not started
**Size:** S (under a day) · M (a few days) · L (a week or more)

## Where things stand

The product is built but has never been published.

- `archive/` holds no editions, and the nightly workflow has never run.
- Claude writing has only been tested with stand-ins. Feeds and grouping have had one local check on real news (see below).
- The domain isn't registered, the site isn't deployed, and no repo secrets are set.
- Grouping and ranking are still set from invented sample data.

So everything below is ordered around one question: **does this work on real news?** Phase 0 answers that. Until it does, later features would be built on untested assumptions.

## First check on real news (2026-11-05)

One local run on the live feeds, with no model and nothing published. It's a single day just after the midterms, and without a Congress key, so government records are undercounted. Local runs also stored feed times 8 hours late until a bug was fixed afterward, so the window was slightly off. A recount of the one-sided stories with a true 36-hour window matched.

| Measure | Result |
| --- | --- |
| Articles in the 36-hour window | 234 |
| Groups, at similarity 0.15 | 192 |
| Groups with 2 or more outlets | 15 |
| Stories that would be written | 14 before fixing reposted laws, 10 after |
| Stories in the main list at the standard threshold | 9 |
| Stories covered by left, center and right | **1** |

What this showed:

- **Three-sided coverage is rare, partly because of the list.** The WSJ feed moved, leaving The Hill and the BBC as the only working center outlets (L4, T3). The strict setting would show almost nothing.
- **Grouping publishes wrong merges (D4).** A test on 232 hand-labeled articles found 4 groups that would have published a wrong story, including the day's only three-sided story, which merged separate events. Better grouping mostly prevents those. It doesn't find many more matches, so it won't raise three-sided coverage by itself.
- **One-sided stories are being lost (T1).** All six one-lean stories were dropped at the current setting. Four of them had 2 or more rated outlets on one side.
- **Feeds are shallow.** One fetch reached back 1.6 hours for the NY Post and 4.2 for The Hill, against 131 for the Guardian. A once-a-day fetch can make a story look one-sided when it isn't, and it tilts against center and right.
- **Sports reached the edition.** Decided: no sports for now. `docs/ranking.md` has the rule, and each edition file lists what it left out.
- **Reposted laws looked new.** GovInfo reposted old laws with fresh dates, so 2021 laws appeared as today's records, and it was weeks behind on real ones. Fixed by F7.

With the Congress key added, the same check found no bills with a significant action in the window, so records didn't change the result that day. Congress was just past an election, so this needs a week in session to judge. A rerun later that day gave 8 stories rather than 10, because the feeds had moved on, so treat these counts as rough.

## Order of work

| Order | Phase | Why here |
| --- | --- | --- |
| 1 | **0. Launch** | Nothing else counts until a real edition exists |
| 2 | **Trust: labels and selection** | The labels and the rule that drops stories are what critics will test first |
| 3 | **2. Reader control** | The core of the thesis, and much of it is small now |
| 4 | **3. Federal records** | Extends a working system |
| 5 | **6. Open books** | Costs become real at launch, so the ledger comes early. Donations wait |
| 6 | **4. State and local** | The biggest job. Start once the national edition is reliable |
| 7 | **5. Open data** | Most useful once there's a history to download |
| Later | **Beyond the US** | Only once US coverage is solid |

Phase numbers match the README. Phase 0 and Trust are new here, and the README's Phase 1 (the national edition) is built, so it isn't repeated.

## Name

**Standard Edition**, planned at standardedition.org, which isn't registered yet. The site, feeds, docs and MCP server use the name. The GitHub repo, the Python package (`boringnews`) and `BN_` settings keep the old name for now.

## Open decisions

These block or shape work, and only the maintainer can make them.

| # | Decision | Affects |
| --- | --- | --- |
| D1 | **When to turn the nightly job back on.** It's disabled on GitHub until launch | L1, L2 |
| D3 | **Should a story covered only by one side be written up?** Today many aren't (see T1). This is an editorial change, not a bug fix | T1, R1 |
| D4 | **Which rating services can we cite,** and do their terms allow it? | T2 |
| D9 | **Which center and right outlets to add,** and whether WSJ's new feed is allowed. See T3 | T3 |
| D5 | **What does Boring News do on a day the pipeline fails?** Show yesterday's edition with a notice, or nothing? | L8 |
| D6 | **Monthly spending limit** for the Claude API, and who pays | L5, B1 |
| D7 | **How much AI writing is disclosed** on each story, beyond the "written by" field in edition files | T5 |

---

## Phase 0: Launch

Goal: a real edition, published every day, that the maintainer would be happy for a stranger to read.

### L1. Accounts, hosting and secrets ⬜ S

- **Exists:** the nightly workflow and Cloudflare deploy step.
- **Gaps:** no domain, Cloudflare project or repo secrets. The workflow expects `ANTHROPIC_API_KEY`, `CONGRESS_API_KEY`, `FRED_API_KEY`, `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
- **Needs a person:** register the domain, create the accounts, add the secrets. Decision D1.
- **Done when:** the workflow deploys a page to the domain.

### L2. Safe nightly job ✅ S

- **Built:** tests run before the build, so failing tests stop a deploy. `pipeline run --require-writer`, used by the nightly job, stops before writing anything when a required key is missing, and stops before storing when every story fell back, which catches a bad key or an outage.
- **Limit:** with no secrets set, the nightly job fails every day until launch. A partial outage, where only some stories fall back, still publishes; those stories show their writer in the edition file.

### L3. Tests on pull requests 🟡 S

- **Exists:** `.github/workflows/tests.yml`, on Python 3.12 and Node 20, with read-only permissions and no secrets.
- **Gaps:** it hasn't run yet, so the code still hasn't been tested on Node 20.
- **Done when:** it has passed on a real pull request.

### L4. Verify every live source 🟡 S

- **Exists:** `python -m boringnews.pipeline check-feeds`, and tests for the failure paths. Checked live on 2026-11-05: 14 of 16 sources work.
- **Gaps:**
  - `wsj-world` answers, but its newest item is from January 2025, because the feed moved (T3).
  - `war-department-releases` returns 403 Access Denied to our requests. It may behave differently from GitHub, which is unknown.
  - Each official source's `max_items` cap is a guess.
- **Done when:** every source reports healthy or is removed, with the reason in the commit.

### L5. First real edition, read by a person ⬜ M

- **Exists:** the writer, retries, linter and fact check, tested with stand-ins only.
- **Gaps:** the real Claude call has never run. The model's fact-check call hasn't either. Unknown: real cost per edition (each edition file now records its token totals in `editorial.usage`), whether 2,000 tokens is always enough, how often the fallback writer is used, and how many bullets the fact check wrongly removes.
- **Needs a person:** read a full edition against its sources, and judge it. Decision D6.
- **Done when:** five editions in a row are good enough to publish unedited, and cost per edition is in the ledger.

### L6. Tune grouping and ranking on real news 🟡 M

- **Exists:** word-based grouping, with a similarity setting of 0.15 tuned on sample data. Edition files record every grouping.
- **Gaps:** one day has been measured (see above), and it needs a normal news week. Rubric thresholds are uncalibrated: on that day only about 10 stories would be written, and only 1 reached all three sides. This doesn't need a model, so it can run locally.
- **Done when:** a week of real editions is hand-checked for wrongly merged or split stories, the settings are updated, and `docs/clustering.md` and `docs/ranking.md` record the result.

### L7. Market ticker permissions ⬜ S

- **Exists:** the ticker, which is hidden if FRED can't be reached.
- **Gaps:** FRED's S&P 500 and Dow series are copyrighted and say reproduction needs the owner's permission.
- **Needs a person:** check the terms, then keep, replace or remove those series.
- **Done when:** every series on the ticker has been checked.

### L8. Failure handling and alerts ⬜ S

- **Exists:** source and ticker problems are printed in the workflow log.
- **Gaps:** nobody is told when a run fails or half the sources go quiet. The page has no way of saying an edition is old. Decision D5.
- **Done when:** a failed or thin run sends the maintainer an alert, and the page says when it's showing an old edition.

### L9. Launch legal check ⬜ S

- **Exists:** summaries only, with links out, and a rule against republishing full articles.
- **Gaps:** each outlet's feed terms haven't been read. The README licenses docs under CC BY-SA 4.0, but the repo has no file saying so. The site has no contact address for corrections or takedown requests.
- **Needs a person:** review the terms, and take legal advice if in doubt.
- **Done when:** each outlet's terms have been checked, and the site has a contact route.

### L10. Launch page basics ⬜ S

- **Exists:** the reader page, RSS, and a local demo.
- **Gaps:** no social preview tags or favicon. No outside reader has tried it, and accessibility hasn't been audited.
- **Done when:** a link previews properly when shared, and the page passes a keyboard and screen-reader check.

---

## Trust: labels and selection

Goal: when someone asks "why is this outlet labeled that?" or "why wasn't this story here?", there's a good, public answer.

### T1. One-sided stories survive to be written ⬜ S to M

The most important gap in the product. The thesis says a story only one side covers is "information in itself", but the pipeline only writes up stories that pass the broad threshold (0.30). With the current source list:

| One-sided story | Score | Written? |
| --- | --- | --- |
| 2 left outlets | 0.27 | No |
| 3 left outlets | 0.30 (0.297) | No |
| 2 right outlets | 0.29 | No |
| 3 right outlets | 0.32 | Yes |
| 2 center outlets | 0.29 to 0.32 | Depends on the pair |

Two things cause this:
- Every left outlet on the list is `national`, so left stories score low on diversity.
- Left outlets count 0.83 each and right outlets 1.11, because the list has four left and three right. That balances each side's total, but it means three left outlets count for less than three right outlets.

So today a three-outlet story on the left is dropped and the same story on the right is kept.

- **Options tested (2026-11-05):**
  - **A, separate blind-spot lane (recommended):** write any story with 2+ rated outlets on one side and keep it out of the main list. Adds 4 stories that day, under a cent a day, and treats all sides alike because it counts outlets, not weights. Needs a third lane in `rubric.py` and `core.js`, and a new rubric version.
  - **B, lower the broad threshold:** 0.28 still drops every left pair. 0.26 is even but by a thin margin, and it changes what "broad" means for everyone.
  - **C, drop weights from the write-up test:** adds nothing that day.
  - **D, balance the list:** adds nothing by itself, and adding outlets can unwrite stories through reweighting.
- **Conditions for A:** word labels as a fact about our list ("Among the outlets we read, only right outlets ran this"), withhold them if any side's feeds failed that day, and fetch more than once a day. Decide what happens if a reader's weights lift one into the main list.
- **Needs a person:** decision D3.
- **Done when:** the rule is decided and published, `docs/ranking.md` explains it, and tests pin it for each side. Any change to the score bumps the rubric version.

### T2. Cited ratings for every outlet ⬜ M

- **Exists:** `ratings` support in `sources.yaml`, the averaging rule in `docs/labeling.md`, and the site showing raters.
- **Gaps:** no outlet has a `ratings` entry. Every label is a hand-set starting assumption.
- **Needs a person:** decision D4, then research.
- **Done when:** every outlet has cited ratings, and disagreements between raters show on the site.

### T3. A more balanced source list ⬜ M

- **Exists:** 11 outlets: 4 left, 3 center, 3 right, 1 unrated.
- **Shortlist (2026-11-05):** UPI (center wire, a new type), NewsNation (center, both raters agree; check whether its owner also owns The Hill), The Oregonian (center regional). Straight Arrow News is the alternative on coverage gain. All have working feeds. AllSides ratings came from search summaries and need checking before citing, and feed terms aren't confirmed.
- **Balance:** adding only center outlets widens the gap between sides, to left 1.08, center 0.72 and right 1.44 with those three, so pair them with right outlets. The only non-national right option found is The Center Square, rated by AllSides only.
- **WSJ:** the feed moved to `feeds.content.dowjones.io` and works, but Dow Jones's terms may limit RSS to personal use. That needs a yes or no before using it.
- **Ratings:** Ad Fontes labels aren't in `RATING_SCALE`, and its "Middle" spans -5.30 to +5.50, so T2 needs a mapping rule first.
- **Gaps:** two working center outlets. Left and right outlets are all national. The BBC is the only international outlet with a lean, and no outlet is typed regional or wire, partly because Reuters and AP don't offer public feeds. So the diversity part of the score can't reach its maximum on any story that only left and right outlets cover.
- **Done when:** each side has a mix of outlet types, and each addition follows the process in `docs/labeling.md`.

### T4. A public way to challenge decisions 🟡 S

- **Exists:** issue forms for proposing a source, challenging a label, reporting a wrong story and suggesting a rubric change, linked from How it works.
- **Gaps:** the `source`, `label`, `correction` and `rubric` labels need creating on GitHub. Filing an issue needs a GitHub account. No written review schedule beyond "quarterly".
- **Done when:** the labels exist and there's a written review schedule, and readers without a GitHub account have a way in. This is the first practical step on the open question about becoming a gatekeeper.

### T5. Checkable summaries ⬜ M

- **Exists:** the number check, the model check, a log of removed bullets, and original headlines shown under each story.
- **Gaps:** a reader can't see which source supports which bullet. Nothing shows what was left out. Decision D7.
- **Done when:** each bullet can be traced to its source. This addresses the open question "summaries are choices too".

### T6. Grouping audit view ⬜ M

- **Exists:** grouping recorded in each edition file.
- **Gaps:** it's only readable as raw JSON. Readers can't see stories that didn't make it, or which articles went unused.
- **Done when:** the site can show everything read that day and what happened to it.

---

## Phase 2: Reader control

Goal: "the reader owns the algorithm" is true in practice, not just for four switches.

### R1. Blind-spot view ⬜ M

Stories covered heavily by one side and barely by the other.

- **Exists:** each story's outlets and leans, in the page data. The Outlets tab shows what each outlet skipped. Today has an "Only one side covered" list, and every story's scale stripes a side that ran nothing, but that only covers stories that were written.
- **Gaps:** depends on T1, because many of these stories are never written. There's no definition yet of "heavily" and "barely". There's also no history view, though Research holds 30 days.
- **Done when:** the rule is published, the view is on the site, and it has its own feed.

### R2. Adjustable rubric weights ✅ M

- **Built:** `weights=60,20,10,10` (breadth, coverage, diversity, record), counted as shares of their total, with sliders on Your feed. It works on the page and in feeds.
- **Limit:** weights only re-rank stories that were written, so they can't bring back a story the default rule dropped. The page says so. T1 would widen what readers can reach.

### R3. Feed recipes ✅ S to M

- **Built:** a recipe is a named settings link (`recipe=`), with a copy control and four built-in examples. No accounts, and nothing leaves the browser. Whoever made a link chose its name, and the page says so.
- **Limit:** there's no saved list; saving means bookmarking the link. Opening a recipe replaces the reader's saved settings in that browser, as any settings link does.

### R4. Show what's filtered out ✅ S

- **Built:** Today and All stories list every story a reader's settings hide, grouped by reason.
- **Limit:** this only covers stories that were written. Seeing everything that was read is T6.

### R5. Developing stories ✅ S to M

- **Built:** Day 2+ stories have an "Earlier days of this story" button, which loads the research index on click.
- **Limit:** it reaches back 30 days, older editions have no page of their own, and RSS items don't link to earlier days.

---

## Phase 3: Federal records

Goal: the claim that records sit next to the reporting holds for all three branches.

### F1. Federal court opinions ⬜ M

- **Exists:** GovInfo as a source type. The README notes it publishes about 250 feeds.
- **Gaps:** which courts to include, given the volume. Courts publish many routine opinions, so `max_items` won't be enough: this needs a rule for what matters.
- **Done when:** opinions appear without flooding the edition, and the selection rule is public.

### F2. Agency reports (GAO and others) ⬜ S to M

- **Gaps:** choosing sources and their record or statement role. Decide whether an audit report is a record.
- **Done when:** the chosen sources run, with roles explained.

### F3. Supreme Court opinions ⬜ M

- **Gaps:** there's no public RSS feed, so this needs another route, and any scraper will be fragile.
- **Done when:** opinions appear on the day they're issued, with a failure alert if the route breaks.

### F4. Roll-call votes ⬜ M

- **Exists:** Congress.gov bills that passed a chamber, went to the President, were signed or vetoed.
- **Gaps:** the README promises votes beside the coverage, but individual roll-call votes aren't read. The Congress.gov API has `/house-vote`, in beta, covering legislation-linked votes in the 118th and 119th Congresses. It has no Senate equivalent, so Senate votes need another source, and showing only one chamber isn't a neutral default.
- **Needs a person:** `CONGRESS_API_KEY`.
- **Done when:** a story about a vote in either chamber links to the vote record itself.

### F5. Presenting official framing ⬜ M

- **Gaps:** the open question of how to show an agency's own framing of a record. Today a record counts as neutral once it's labeled a record.
- **Done when:** a written policy exists in `docs/`, applied in the style guide.

### More from the Congress.gov API

We read only `/bill` today. The [API](https://github.com/LibraryOfCongress/api.congress.gov/) has about 20 areas, allows 5,000 requests an hour, and is free. Everything below needs `CONGRESS_API_KEY`, the same key the bills source needs. Each new source needs the same care as public laws: count real events, not routine record updates.

### F6. Bill summaries from the Congressional Research Service ✅ S to M

- **Built:** a bill the edition keeps now carries its newest summary, labeled with the bill version it describes, so the writer and the fact check have real source material.
- **Limit:** a summary may describe an older version of the bill. A bill with no summary, or a failed call, stays a record with its title and latest action. Not yet tried with a real model.

### F7. Laws from Congress.gov ✅ S

- **Built:** the GovInfo laws source is gone. Congress.gov gives real dates and showed laws GovInfo's feed hadn't posted, and the bills source already catches each signing on its real date.
- **Limit:** an action only counts if Congress.gov shows it within the edition's window. If it posts an action late, that action is missed. Check this over a week in session.

### F8. Nominations ⬜ S to M

- **Gaps:** `/nomination` covers cabinet and judicial nominations. Needs a rule for which actions count, since most nominations are routine.
- **Done when:** significant nominations appear as records, with the rule public.

### F9. Treaties ⬜ S

- **Gaps:** `/treaty` covers treaties sent to the Senate. They're rare, and they stay active across Congresses, so only real events should count, such as a treaty being sent or ratified. Its update date alone isn't an event.
- **Done when:** treaties appear as records on those events only.

### F10. Hearings and committee activity ⬜ M

- **Gaps:** `/hearing`, `/committee-meeting` and `/committee-report` show what's coming up. That could fill the "Next" line with a scheduled date. Needs a rule for matching them to stories.
- **Done when:** a story can cite a scheduled hearing or report as its next step.

### F11. Research reports ⬜ S to M

- **Gaps:** `/crsreport` has nonpartisan background reports, which suit the Research tab more than the edition.
- **Done when:** Research can show relevant reports beside coverage.

---

## Phase 4: State and local

Goal: one place, done properly. The pilot is San Mateo County, California, and nearby cities.

This is the phase with the most unknowns. It should start with a small research spike, S1, before any build.

### S1. Pilot research ⬜ M

- **Gaps:** an inventory of what actually exists: which cities and boards publish agendas, in what format, how reliably, and which local outlets have feeds.
- **Done when:** there's a written list of sources, formats and gaps, and a decision on which cities are in the pilot.

### S2. The place model ⬜ M

- **Exists:** a `states` topic. A `region` field is still stored and guessed, but nothing reads it, and the region setting was removed.
- **Gaps:** there's no concept of where a story belongs or where a reader lives. A reader's place must stay in the browser and feed address, with no accounts. The spotlight, Today page and feeds all assume one national edition.
- **Done when:** a reader can pick a place, and the page and feed follow it.

### S3. State legislature ⬜ M

- **Gaps:** an adapter for California bills and votes, and a rule for which bills matter.
- **Done when:** California bills that pass a chamber appear as records.

### S4. City and board agendas ⬜ L

- **Gaps:** usually PDFs on inconsistent vendor sites, with no feed. Needs document parsing, and a decision on how summaries of agendas meet the fact-check rules.
- **Done when:** the pilot's councils and school boards appear reliably.

### S5. Ranking without a national spectrum ⬜ L

- **Gaps:** the score rewards coverage across left, center and right, and local stories may have one outlet or none. Most local outlets have no published lean rating. Under today's rule, nearly every local story would fail. This needs its own published rule, likely built around records.
- **Done when:** local stories have a rule that's as public and explainable as the national one.

### S6. A guide to add your own city ⬜ M

- **Done when:** someone outside the project adds a city by following it, with a pull request.

### S7. Expansion ⬜ L

- **Gaps:** cost and maintenance grow with every source. Needs per-place failure reporting, and likely volunteer maintainers.
- **Done when:** a second state runs with no new core code.

---

## Phase 5: Open data

Goal: journalists and researchers can use the data without asking.

### D1. Downloads ✅ S

- **Built:** `api/v1/` has an index of editions, one file per edition, and monthly zip downloads. See [`api.md`](api.md).
- **Limit:** no CSV. Not yet deployed.

### D2. Public API and MCP server 🟡 M

- **Built:** a versioned static JSON API, and a read-only remote MCP server (`functions/mcp.js`) with `get_edition`, `search_coverage`, `search_records` and `list_sources`. No accounts or keys. Documented in [`api.md`](api.md).
- **Gaps:** no real MCP client has connected, and nothing has run on Cloudflare. There's no rate limit, which the MCP spec requires and which needs a Cloudflare rule on the live domain. The free plan's 100,000 daily requests are shared with `/feed.xml`, so heavy MCP use could stop custom feeds.
- **Done when:** a real client works against a deployed preview, and a rate limit is in place.

### D3. Research beyond 30 days ⬜ M

- **Exists:** coverage lookup and records search over the last 30 days, in the browser.
- **Gaps:** the index grows with every day, and all of it is downloaded to the page. Longer history needs a different approach. Word matching also misses paraphrased claims. The MCP function's first search on a fresh copy costs far more than the free plan's 10 ms CPU limit, because it parses and tokenizes the whole index, so it needs a smaller or pre-tokenized index.
- **Done when:** a reader can search the whole archive at a sensible download size.

### D4. Better grouping ⬜ M

- **Exists:** word-based grouping.
- **Tested (2026-11-05):** sentence embeddings with a shared-name check and average linkage, at 0.60, gave no wrong multi-outlet groups and 16 clean ones, against 4 that would publish wrongly and 9 clean today. Embeddings alone are worse, merging by topic. They find about the same number of matches as word matching, so the gain is fewer wrong stories.
- **Cost:** about 110 MB of packages, a 90 MB model to cache in CI, and seconds to run. If that's too much, average linkage on word matching at 0.14 needs no new dependency and separates the Johnson and Jeffries stories, but it leaves wrong multi-outlet groups.
- **Gaps:** 0.60 was picked on one unusual day, so test it on a normal week first. It also won't link stories with no shared name, and same-official-source rules were barely exercised.
- **Done when:** real editions measurably improve, on the week of checks from L6. A wrong merge publishes a false story, so this should come before launch.

---

## Phase 6: Open books

### B1. A true ledger ⬜ S

- **Exists:** `LEDGER.md`, with $0 and empty running costs.
- **Gaps:** real costs appear from L1 and L5 onward. The ledger's rule is to record every transaction within a week.
- **Done when:** the domain, API and hosting costs are listed, and updated as a routine.

### B2. Donations ⬜ M

- **Exists:** the rules in `LEDGER.md`.
- **Gaps:** a payment route with no tracking, and legal and tax questions about taking donations. Depends on real, recurring costs.
- **Needs a person:** the legal and tax decisions.
- **Done when:** a donation appears in the ledger within a week, by a written routine.

---

## Later: Beyond the US

Starts only once US coverage is solid. Each country gets its own spectrum, sources and government feeds rather than inheriting American labels. The work in S5, on ranking without a national spectrum, should inform this.
