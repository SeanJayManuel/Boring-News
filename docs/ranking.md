# How stories are chosen

This is the plain-language version of [`boringnews/rubric.py`](../boringnews/rubric.py). If the two ever disagree, the code is what ran, and the mismatch is a bug to report. Any change to the rubric must update this file in the same commit, and any change to the score must bump `VERSION` in the code.

Current rubric: **v0.4**

## The score

Each story gets a score from 0 to 1, made of four parts:

| Part | Weight | What it measures |
| --- | --- | --- |
| Breadth | 40% | How much of the spectrum covered it: left, center, right. One side is 1/3, two sides 2/3, all three 1. |
| Coverage | 25% | How many outlets covered it, on a log scale that tops out at 10 outlets. Each outlet counts by its balance weight (see [labeling](labeling.md)), so a side with more outlets on the list can't inflate this. |
| Diversity | 10% | How many kinds of outlet covered it (wire, national, regional, international), out of 3. |
| Record | 25% | 1 if an official **record** documents it: a law, a rule, a court ruling, a vote, official statistics. Otherwise 0. |

Breadth carries the most weight on purpose. A story that left, center and right all covered is, by this project's definition, news that matters across the country, not news that matters to one audience.

## Records vs. statements

Official sources are split into two roles:

- **Records** have legal or statistical standing. They add the record part of the score.
- **Statements** are an institution describing its own work, like a press release. They are shown and labeled "Official statement", but add nothing to the score.

This means no administration, of any party, can lift a story by issuing press releases about it. An official source counts as a record only if it is explicitly marked `role: record` in [`sources.yaml`](../sources.yaml).

## What makes the edition

A story is in the main edition when **both** are true:

1. Its score is at or above the threshold, and
2. At least **two** outlets covered it.

| Threshold | Score needed |
| --- | --- |
| broad | 0.30 |
| standard (default) | 0.40 |
| strict | 0.55 |

Official records and statements that no outlet has covered yet are listed separately under their topic, because they matter whether or not anyone wrote about them. Readers can hide them.

The five highest-scoring stories are the day's spotlight.

## Only one side covered

A story that doesn't reach the threshold, but that at least 2 rated outlets ran, all on one side, is a **blind spot**. It's written up and listed under "Only one side covered". It never enters the spotlight, and it stays out of the main list.

- **It counts outlets.** Weights and the score play no part, so the same rule holds for left, center and right. Before this rule, a three-outlet story on the left was dropped while the same story on the right was kept, because of how outlet weights and types add up.
- **Scores and the main list don't change.** A story already above the threshold stays there.
- **It's a fact about our list.** The page says "Among the outlets we read, only right outlets ran this", not that the other side ignored the story. If a reader turned off a source, it says "Among the outlets you kept".
- **We don't claim what we couldn't check.** If a feed on a side the story lacks failed that day, the page says so and makes no claim, and that side of the coverage scale stays blank instead of striped. Each edition file lists the failed feeds under `feeds_down`.

What this still gets wrong: a feed can work and still reach back only a little way. In one test the New York Post's feed covered 1.6 hours and The Guardian's 131. With one fetch a day, a story can look one-sided because a feed had already moved on. Fixing that means fetching more often (roadmap T1). A one-sided story also depends on grouping: if two outlets' articles aren't grouped, neither counts.

## No sports, for now

Sports are left out of the edition, whatever their score. The score doesn't change: the rule runs after it, before a story is written, so nothing is spent on a story that's left out.

A group of articles is left out only when all three of these are true:

1. **More than half of its outlets filed it in a sports section.** A section is a whole part of the link's path: `sport`, `sports`, or `football` (The Guardian's soccer section). Words in the rest of the link don't count, so `/us-news/sports-betting-rises` isn't in a sports section. An outlet counts only if all its articles in the group are in one, and one outlet with many articles still counts once.
2. **No official source is in the group.** A law, rule or court record is never left out by this rule, and neither is an official item on its own.
3. **No headline in the group uses a hard-news word.** The words are `HARD_NEWS_WORDS` in [`rubric.py`](../boringnews/rubric.py): law, lawsuit, antitrust, ruling, charged, arrested, senate, governor, voters, bond vote and the like. They can only keep a story, never remove one.

We read links and not the words in a story because words catch real news. On the first real day checked, a story on US sanctions against Rwanda's army named the NBA, and a story on an Arizona House race named the NFL. Neither is a sports story, and neither is filed as one.

**Borderline cases stay in.** A tie stays in: one outlet's sports section and one outlet's news section is not "most". So does a stadium bond vote, a sports betting law, an athlete charged with a crime, or an antitrust ruling against a league, when a headline says so.

What this rule still gets wrong:

- **Some sports stays in.** A story filed outside a sports section doesn't count as sports, so a story two outlets cover, one of them on a general page, stays in. The New York Times filed a Golden State Valkyries parade under `/us/`, and CBS files Lions video under `/video/`. A headline with a hard-news word also keeps a story, even if it's only "Hall of Fame voters".
- **Some real news can be left out.** If most outlets file it in sports sections, no official source is in the group, and no headline uses one of the words, it's left out. There's no official source for court rulings yet.

Nothing is hidden. Each edition file in [`archive/`](../archive/) lists every group this rule left out under `left_out`, with its titles, links and score, and the rule in force that day. So a wrong call can be found and reported. The articles also stay in the file's `articles` and `clusters`.

## What readers can change

Readers can choose the threshold, choose topics, drop any source, hide official items, hide one-sided stories, and set their own weights for the four parts. Dropping a source re-scores every story without it. The page and the RSS feed apply exactly the same rules (`web/core.js`, with the score and lane also in `boringnews/rubric.py` for the pipeline, and tests check they match).

A reader's weights (`weights=60,20,10,10`, in the order breadth, coverage, diversity, record) count as shares of their total, so a score still runs from 0 to 1 and the thresholds stay the same. They apply only to that reader's page and feed. The published rule above still decides what gets written, so weights re-rank stories that were written, and can't bring back one it dropped.

Every story a reader's settings hide is listed with the reason (`select` in `web/core.js`): outside their categories, all its sources off, below their threshold, a one-sided story or a government item they turned off.

## Every story explains itself

Each story on the site carries a one-line reason, for example: "6 outlets across left, center and right. Backed by a government record. Score 0.87." The full score breakdown for every story is saved in that day's file in [`archive/`](../archive/).

## History

- **2026-11-04**: no sports, for now. This decides what is written and not how anything scores, so the rubric stays at v0.4.
- **v0.5** (2026-11-05): added the blind-spot lane. Scores and the main list didn't change.
- **v0.4** (2026-11-04): coverage counts weighted outlets, so each side counts equally.
- **v0.3** (2026-11-04): only official records earn the record part; statements are listed but add nothing.
- **v0.2** (2026-11-04): added the record part; thresholds recalibrated.
- **v0.1** (2026-11-04): breadth 50%, coverage 35%, diversity 15%.
