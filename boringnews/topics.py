"""Categories. Six of them, one per story, each with a plain description that
the site shows to readers and the model is given when it picks one.

(Stories also keep an internal `region` guess, which is not shown or filtered on.)
"""

from __future__ import annotations

TOPICS = {
    "government": "Politics & government",
    "states": "States & cities",
    "economy": "Economy & business",
    "world": "World",
    "health-science": "Health & science",
    "tech": "Technology",
}

TOPIC_DESCRIPTIONS = {
    "government": "Congress, the White House, federal courts, federal agencies and the military.",
    "states": "Governors, state legislatures, state courts, cities and schools.",
    "economy": "Jobs, prices, interest rates, trade and companies.",
    "world": "Other countries and international affairs.",
    "health-science": "Medicine, public health, research and the environment.",
    "tech": "Tech companies, product recalls, data breaches and the internet.",
}

# Older category names map to the current ones, so old editions still read correctly.
LEGACY = {
    "politics": "government", "congress": "government", "courts": "government",
    "regulation": "government", "defense": "government",
    "local-state": "states", "science-health": "health-science",
}

_KEYWORDS = {
    "government": ["congress", "senate", "house passed", "h.r.", "president", "white house", "federal",
                   "supreme court", "final rule", "federal register", "pentagon", "military", "department of war",
                   "navy", "army", "election", "campaign"],
    "states": ["governor", "legislature", "state ", "mayor", "city council", "county", "school board",
               "university", "district court"],
    "economy": ["inflation", "interest rate", "jobs", "unemployment", "gdp", "tariff", "central bank",
                "prices", "earnings", "payrolls", "trade agreement"],
    "world": ["minister", "parliament", "united nations", "nato", "embassy", "foreign"],
    "health-science": ["study", "researchers", "trial", "vaccine", "disease", "climate", "hospital", "health",
                       "measles"],
    "tech": ["recall", "software", "artificial intelligence", "chip", "app", "e-bike", "cyber", "data breach",
             "hackers"],
}


def normalize(topic: str | None) -> str | None:
    if topic in TOPICS:
        return topic
    return LEGACY.get(topic or "")


def guess_topic(text: str) -> str:
    t = f" {text.lower()} "
    best, best_hits = "government", 0
    for topic, words in _KEYWORDS.items():
        hits = sum(t.count(w) for w in words)
        if hits > best_hits:
            best, best_hits = topic, hits
    return best


def guess_region(text: str, source_types: set[str]) -> str:
    t = text.lower()
    if source_types and source_types <= {"international"}:
        return "world"
    if any(w in t for w in ("governor", "legislature", "mayor", "state ", "county", "city ")):
        return "us-state"
    if any(w in t for w in ("minister", "parliament", "central bank", "prime minister")):
        return "world"
    return "us-national"
