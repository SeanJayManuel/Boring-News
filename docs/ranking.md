# How stories are chosen

This is the plain-language version of [`boringnews/rubric.py`](../boringnews/rubric.py). If the two ever disagree, the code is what ran, and the mismatch is a bug to report. Any change to the rubric must update this file in the same commit and bump `VERSION` in the code.

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

## What readers can change

Readers can choose the threshold, choose topics, drop any source, hide official items, and set their own weights for the four parts. Dropping a source re-scores every story without it. The page and the RSS feed apply exactly the same rules (`web/core.js`, with the score and lane also in `boringnews/rubric.py` for the pipeline, and tests check they match).

A reader's weights (`weights=60,20,10,10`, in the order breadth, coverage, diversity, record) count as shares of their total, so a score still runs from 0 to 1 and the thresholds stay the same. They apply only to that reader's page and feed. The published rule above still decides what gets written, so weights re-rank stories that were written, and can't bring back one it dropped.

Every story a reader's settings hide is listed with the reason (`select` in `web/core.js`): outside their categories, all its sources off, below their threshold, or a government item they turned off.

## Every story explains itself

Each story on the site carries a one-line reason, for example: "6 outlets across left, center and right. Backed by a government record. Score 0.87." The full score breakdown for every story is saved in that day's file in [`archive/`](../archive/).

## History

- **v0.4** (2026-11-04): coverage counts weighted outlets, so each side counts equally.
- **v0.3** (2026-11-04): only official records earn the record part; statements are listed but add nothing.
- **v0.2** (2026-11-04): added the record part; thresholds recalibrated.
- **v0.1** (2026-11-04): breadth 50%, coverage 35%, diversity 15%.
