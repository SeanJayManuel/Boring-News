# How articles are grouped into stories

This is the plain-language version of [`boringnews/cluster.py`](../boringnews/cluster.py). Any change to grouping must update this file in the same commit.

Different outlets write about the same event with different headlines. Before stories can be scored, articles about the same event have to be grouped together. Grouping matters: if two articles about one event end up apart, each looks like it had narrower coverage than it really did.

## Current method

1. **Compare meaning.** Each article's headline and the first 300 characters of its summary are turned into a sentence embedding by a small open model (`all-MiniLM-L6-v2`), which runs on the build machine and costs nothing per use. Similar meanings score high even when outlets use different words.
2. **Require a shared name.** Two articles can join only if they share a proper name that few of the day's articles use (at most 5% of them, or 12 if that's more). Embeddings rate any two stories from one news cycle as alike, and the name tells them apart. Names are learned from the day's text: words capitalised mid-sentence and rarely used in lower case.
3. **Join by average.** Groups form by average linkage: two groups join only if their articles are similar **on average** (at least 0.60). One close pair can't chain two stories together.
4. **Keep some things apart.** Articles more than 48 hours apart never join. Two documents from the same government source never join, even when their boilerplate ("Final rule: ...") looks alike. Live blogs never join anything, because they touch every story of the day. So a live blog's coverage doesn't count toward any story.

## If the model can't load

The edition still runs, grouped by words (TF-IDF, average linkage, at least 0.14), with no name check. This method is also used for sample data and tests. It makes more mistakes. Every edition file says which method ran, under `editorial.grouping`.

## Settings

| Setting | Default | Environment variable |
| --- | --- | --- |
| Similarity needed, embeddings | 0.60 | `BN_EMBEDDING_SIMILARITY` |
| Similarity needed, words | 0.14 | `BN_WORD_SIMILARITY` |
| Time window | 48 hours | `BN_CLUSTER_WINDOW_HOURS` |

**Both similarity settings are provisional.** They come from one unusual day just after the 2026 midterms, and they were chosen on the same day they were tested on. They need a normal news week (roadmap L6).

## How it was tested

232 real articles from one day were hand-labeled, with 78 hand-checked pairs. A wrong group is one that joins separate events.

| Method | Wrong groups that would be written | Clean groups from 2+ outlets |
| --- | --- | --- |
| Before: words, chains, 0.15 | 4 | 9 |
| Words, average, 0.14 (the fallback) | 2 | 13 |
| Embeddings with names, average, 0.60 | 0 | 16 |

## Known weaknesses

- It finds about as many of the true same-event pairs as the old method. Its gain is fewer wrong merges, so it won't raise the number of stories all three sides covered.
- A story whose articles share no rare name stays split. On a day when one name is everywhere, that name stops helping.
- No government record was in that test day's window alongside news coverage, so how often records join news stories under this method is untested. Check this first in the L6 week: a record that doesn't join loses the story its record score.
- The same articles should give the same groups, but tiny number differences between machines could flip a pair right at the threshold. The edition file is the record of what actually happened.

## Checking the result

Every edition file in [`archive/`](../archive/) records exactly which articles were grouped into each story, so anyone can audit the grouping for any day.
