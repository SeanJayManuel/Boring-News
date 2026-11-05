# Roadmap

The detailed plan behind the summary in the [README](../README.md). Each feature has a stable ID so it can be worked through one at a time: what it is, what already exists, what's missing, what it needs from a person, and how we'll know it's done.

Status as of 2026-11-04.

**Status:** ✅ built · 🟡 partly built · ⬜ not started
**Size:** S (under a day) · M (a few days) · L (a week or more)

## Where things stand

The product is built but has never run on real news.

- `archive/` holds no editions, and the nightly workflow has never run.
- The feed URLs in `sources.yaml` are unverified, and Claude writing has only been tested with stand-ins.
- The domain isn't registered, the site isn't deployed, and no repo secrets are set.
- Grouping and ranking were tuned on invented sample data.

So everything below is ordered around one question: **does this work on real news?** Phase 0 answers that. Until it does, later features would be built on untested assumptions.

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

The planned name is **The Standard Edition**, at standardedition.org. The code and site still say Boring News until the rename, which happens with L1.

## Open decisions

These block or shape work, and only the maintainer can make them.

| # | Decision | Affects |
| --- | --- | --- |
| D1 | **Nightly job:** add the secrets, or disable the workflow until launch? Without secrets it writes a fallback edition and commits it to `main`, then fails at the deploy | L1, L2 |
| D3 | **Should a story covered only by one side be written up?** Today many aren't (see T1). This is an editorial change, not a bug fix | T1, R1 |
| D4 | **Which rating services can we cite,** and do their terms allow it? | T2 |
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

### L2. Safe nightly job ⬜ S

- **Exists:** tests run before the build, so failing tests stop a deploy.
- **Gaps:** a run with missing secrets still commits an edition to `main`. Nothing stops a real edition being written by the fallback writer without anyone noticing.
- **Done when:** a missing key fails the run before anything is committed.

### L3. Tests on pull requests ⬜ S

- **Exists:** the full test suite, run only inside the nightly job.
- **Gaps:** pull requests aren't tested. Node 20, which the nightly job uses, has never been run against the current code.
- **Done when:** every pull request runs the tests on Python 3.12 and Node 20, with no way to publish from that workflow.

### L4. Verify every live source ⬜ S

- **Exists:** `python -m boringnews.pipeline check-feeds`, and tests for the failure paths.
- **Gaps:** no feed has been confirmed against the live internet. Each official source's `max_items` cap is a guess.
- **Done when:** every source reports healthy or is removed, with the reason in the commit.

### L5. First real edition, read by a person ⬜ M

- **Exists:** the writer, retries, linter and fact check, tested with stand-ins only.
- **Gaps:** the real Claude call has never run. The model's fact-check call hasn't either. Unknown: real cost per edition, how often the fallback writer is used, and how many bullets the fact check wrongly removes.
- **Needs a person:** read a full edition against its sources, and judge it. Decision D6.
- **Done when:** five editions in a row are good enough to publish unedited, and cost per edition is in the ledger.

### L6. Tune grouping and ranking on real news ⬜ M

- **Exists:** word-based grouping, with a similarity setting of 0.15 tuned on sample data. Edition files record every grouping.
- **Gaps:** real headlines vary far more than the samples. Merged and split stories are likely. Rubric thresholds are also uncalibrated: we don't know how many stories a real day produces.
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

- **Needs a person:** decision D3.
- **Done when:** the rule is decided and published, `docs/ranking.md` explains it, and tests pin it for each side. Any change to the score bumps the rubric version.

### T2. Cited ratings for every outlet ⬜ M

- **Exists:** `ratings` support in `sources.yaml`, the averaging rule in `docs/labeling.md`, and the site showing raters.
- **Gaps:** no outlet has a `ratings` entry. Every label is a hand-set starting assumption.
- **Needs a person:** decision D4, then research.
- **Done when:** every outlet has cited ratings, and disagreements between raters show on the site.

### T3. A more balanced source list ⬜ M

- **Exists:** 11 outlets: 4 left, 3 center, 3 right, 1 unrated.
- **Gaps:** left and right outlets are all national. The BBC is the only international outlet with a lean, and no outlet is typed regional or wire, partly because Reuters and AP don't offer public feeds. So the diversity part of the score can't reach its maximum on any story that only left and right outlets cover.
- **Done when:** each side has a mix of outlet types, and each addition follows the process in `docs/labeling.md`.

### T4. A public way to challenge decisions ⬜ S

- **Exists:** the contributing rules in the README.
- **Gaps:** no issue templates for proposing a source, challenging a label or reporting a wrong story. No written review schedule beyond "quarterly".
- **Done when:** the templates exist and are linked from the site. This is the first practical step on the open question about becoming a gatekeeper.

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

- **Exists:** each story's outlets and leans, in the page data. The Outlets tab already shows what each outlet skipped.
- **Gaps:** depends on T1, because many of these stories are never written. There's no definition yet of "heavily" and "barely". There's also no history view, though Research holds 30 days.
- **Done when:** the rule is published, the view is on the site, and it has its own feed.

### R2. Adjustable rubric weights ⬜ M

- **Exists:** `web/core.js` already re-scores in the browser and feed function, and `SETTINGS` makes a new setting cheap.
- **Gaps:** readers can only re-rank stories that were written, so a reader's weights can't bring back a story the default rule dropped. The address needs a compact form for four numbers. The chart and "your setting needs" text assume the default weights.
- **Done when:** four weights work on the page and in the feed, with the limit explained plainly.

### R3. Feed recipes ⬜ S to M

- **Exists:** every setting already lives in the address, so any setup is a shareable link.
- **Gaps:** no name, description or share button. Decide whether recipes are just links, or files in the repo that people can propose.
- **Done when:** a reader can save and share a named setup, with no accounts.

### R4. Show what's filtered out ⬜ S

- **Exists:** a count of stories left out by a reader's settings.
- **Gaps:** the belief says "we'll show you what you're filtering out", but readers only get a number, with no way to see the stories.
- **Done when:** each hidden story can be seen, with the reason it was hidden.

### R5. Developing stories ⬜ S to M

- **Exists:** threads and "Day 2" labels. The thread id is in the research index.
- **Gaps:** no way to read a story's earlier days.
- **Done when:** a developing story links to its earlier days.

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
- **Gaps:** the README promises votes beside the coverage, but individual roll-call votes aren't read.
- **Done when:** a story about a vote links to the vote record itself.

### F5. Presenting official framing ⬜ M

- **Gaps:** the open question of how to show an agency's own framing of a record. Today a record counts as neutral once it's labeled a record.
- **Done when:** a written policy exists in `docs/`, applied in the style guide.

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

### D1. Downloads ⬜ S

- **Exists:** edition files, published at `/archive/`. A 30-day `research.json`.
- **Gaps:** no index of editions, a documented format, or bulk or CSV download.
- **Done when:** the format is documented and the whole archive can be downloaded.

### D2. Public API ⬜ M

- **Exists:** static JSON files, which may already be enough.
- **Gaps:** decide what a free, stable API needs beyond static files, and what format promises we're willing to keep.
- **Done when:** a versioned, documented interface exists. This must stay cheap on the free hosting tier.

### D3. Research beyond 30 days ⬜ M

- **Exists:** coverage lookup and records search over the last 30 days, in the browser.
- **Gaps:** the index grows with every day, and all of it is downloaded to the page. Longer history needs a different approach. Word matching also misses paraphrased claims.
- **Done when:** a reader can search the whole archive at a sensible download size.

### D4. Better grouping ⬜ M

- **Exists:** word-based grouping.
- **Gaps:** `docs/clustering.md` plans sentence embeddings, which match on meaning. Only worth doing if L6 shows word matching isn't good enough.
- **Done when:** real editions measurably improve, on the week of checks from L6.

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
