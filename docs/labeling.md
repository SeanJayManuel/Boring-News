# How sources are chosen and labeled

This is the plain-language version of [`sources.yaml`](../sources.yaml) and [`boringnews/sources.py`](../boringnews/sources.py). Any change to how sources are labeled or weighted must update this file in the same commit.

## What every source records

Each source in `sources.yaml` lists:

- **Name and feed address**
- **Type:** `wire`, `national`, `regional`, `international`, or `primary` (an official government source)
- **Lean:** `left`, `center`, `right`, or `unrated`
- **Role** (official sources only): `record` or `statement`. See [ranking](ranking.md).

## Where lean labels come from

We don't invent lean labels. A source can list ratings from several published media-rating services:

```yaml
- id: example
  ratings: {ServiceA: lean left, ServiceB: center}
```

Each rating is turned into a number (left −2, lean left −1, center 0, lean right +1, right +2) and averaged:

| Average | Label |
| --- | --- |
| −0.5 or lower | left |
| between −0.5 and 0.5 | center |
| 0.5 or higher | right |

The raters and their individual labels are shown on the site next to the outlet, so readers can see where the label came from and where raters disagree.

Some sources still carry a single hand-set `lean` taken from public ratings. Those are starting assumptions and should be replaced with cited `ratings` over time. Labels are reviewed quarterly.

**Unrated** outlets count toward a story's coverage but not its breadth.

## Balance weighting

The source list will rarely have the same number of outlets on each side. So that no side counts more just because it has more outlets listed, rated outlets are weighted so each side adds up to the same total.

Example: with 4 left, 3 center and 3 right outlets, each left outlet counts 0.83 and each center or right outlet counts 1.11. The site shows each outlet's weight as "Counts as".

## Adding or removing a source

Use the [source form](https://github.com/SeanJayManuel/Boring-News/issues/new/choose) to propose a change, or open a pull request that edits `sources.yaml` and explains in the description:

1. Why the source should be included (or removed)
2. Where its lean label comes from, with links to the ratings
3. That `python -m boringnews.pipeline check-feeds` reports its feed as healthy

## Known gaps

- Reuters and AP do not offer public RSS feeds.
- The Supreme Court does not publish an RSS feed.
- State and local sources are not on the list yet. See the roadmap in the [README](../README.md).
