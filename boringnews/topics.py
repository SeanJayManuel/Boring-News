"""Topic and region taxonomy, plus a keyword fallback when no model is used."""

from __future__ import annotations

TOPICS = {
    "politics": "Politics",
    "congress": "Congress",
    "defense": "Defense",
    "economy": "Economy",
    "world": "World",
    "science-health": "Science & health",
    "tech": "Tech",
    "regulation": "Regulation",
    "courts": "Courts",
    "local-state": "State & local",
}

REGIONS = {
    "us-national": "U.S. national",
    "us-state": "U.S. states",
    "world": "World",
}

_KEYWORDS = {
    "congress": ["h.r.", "s.res", "public law", "passed house", "passed senate", "cloture"],
    "defense": ["navy", "army", "air force", "marine corps", "pentagon", "department of war", "military", "contract award"],
    "courts": ["court", "judge", "ruling", "ruled", "opinion", "lawsuit", "appeal", "justices"],
    "regulation": ["rule", "regulation", "agency", "final rule", "comment period", "federal register"],
    "economy": ["inflation", "interest rate", "jobs", "unemployment", "gdp", "tariff", "central bank", "prices", "budget"],
    "science-health": ["study", "researchers", "trial", "vaccine", "disease", "climate", "nasa", "hospital", "health"],
    "tech": ["recall", "software", "ai ", "artificial intelligence", "chip", "app", "e-bike", "cyber", "data breach"],
    "politics": ["senate", "congress", "governor", "election", "campaign", "president", "ethics", "lawmakers", "vote"],
    "local-state": ["mayor", "city council", "county", "legislature", "state", "university", "school board"],
    "world": ["minister", "parliament", "un ", "united nations", "nato", "embassy", "foreign"],
}


def guess_topic(text: str) -> str:
    t = f" {text.lower()} "
    best, best_hits = "politics", 0
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
