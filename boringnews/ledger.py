"""LEDGER.md, read for the site's Ledger page.

The file stays the one record, so the page can never disagree with it. Totals
are added up from the rows here, not copied from the file's own table.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config

MONEY_RE = re.compile(r"[\d,]+\.\d\d")


def amount(text: str) -> float:
    found = MONEY_RE.search(text)
    return float(found.group().replace(",", "")) if found else 0.0


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = sections.setdefault(line[3:].strip(), [])
        elif current is not None:
            current.append(line)
    return sections


def _table(lines: list[str]) -> list[dict[str, str]]:
    """A Markdown table's filled-in rows, keyed by column name."""
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines if line.startswith("|")]
    if len(rows) < 2:
        return []
    return [dict(zip(rows[0], row)) for row in rows[2:] if any(row)]


def load(path: Path | None = None) -> dict:
    sections = _sections(Path(path or config.LEDGER_PATH).read_text())
    money_in = _table(sections.get("Money in", []))
    money_out = _table(sections.get("Money out", []))
    return {
        "money_in": money_in,
        "money_out": money_out,
        "running_costs": _table(sections.get("Running costs", [])),
        "rules": [re.sub(r"^\d+\.\s*", "", line) for line in sections.get("Rules", []) if re.match(r"\d+\.", line)],
        "received": round(sum(amount(r["Amount"]) for r in money_in), 2),
        "spent": round(sum(amount(r["Amount"]) for r in money_out), 2),
    }
