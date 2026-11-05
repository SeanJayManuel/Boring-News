# How articles are grouped into stories

This is the plain-language version of [`boringnews/cluster.py`](../boringnews/cluster.py). Any change to grouping must update this file in the same commit.

Different outlets write about the same event with different headlines. Before stories can be scored, articles about the same event have to be grouped together. Grouping matters: if two articles about one event end up apart, each looks like it had narrower coverage than it really did.

## Current method

1. **Compare text.** Each article's headline and summary are turned into a word-frequency profile (TF-IDF, ignoring common words like "the"). Headlines count twice, because they carry the event.
2. **Find close pairs.** Two articles are a match when their profiles are similar enough (cosine similarity of at least 0.15) **and** they were published within 48 hours of each other.
3. **Join matches.** Any chain of matches becomes one story: if A matches B and B matches C, all three are one story.
4. **Keep official documents apart.** Two documents from the same government source are never joined to each other, even when their boilerplate ("Final rule: ...") looks alike. They are different events.

This method is cheap, makes no paid API calls, and gives the same result every time it runs on the same articles.

## Settings

| Setting | Default | Environment variable |
| --- | --- | --- |
| Similarity needed to match | 0.15 | `BN_CLUSTER_SIMILARITY` |
| Time window | 48 hours | |

The 0.15 threshold was tuned on sample data and needs re-tuning on real feeds.

## Known weaknesses

- Word overlap misses stories described in very different language, which can split one event in two.
- Chains can occasionally join two related but separate events.

Planned: replacing word frequency with sentence embeddings, which match on meaning rather than shared words.

## Checking the result

Every edition file in [`archive/`](../archive/) records exactly which articles were grouped into each story, so anyone can audit the grouping for any day.
