# Glossary

**Edition**: one day's stories, sources and market closes (`boringnews/edition.py`). It has three forms: the database row set, the edition file and the page data.

**Edition file**: `archive/YYYY-MM-DD.json`, the public record of a run and the project's storage. The database can be rebuilt from these files.

**Page data**: `edition.json` and the JSON embedded in the page. What `web/core.js` and `web/app.js` read.

**Reader settings**: the query parameters that shape a page or feed. Declared once in `SETTINGS` in `web/core.js`.

**Score** and **lane**: how widely a story was covered, from its sources, and whether that puts it in the main list, the official list or neither. The only rules kept in both Python (`rubric.py`, for the pipeline) and JS (`core.js`, for readers who change settings); `tests/test_parity.py` keeps them equal.

**Writer**: turns a prompt into text (`ClaudeWriter`, `MockWriter`). It knows nothing about stories; parsing, retries and linting apply to every writer.

**Inputs**: where a run gets articles and market closes (`LiveInputs`, `FixtureInputs`).

**Record / statement**: a government item with legal or statistical standing, which adds to the score, versus an institution describing its own work, which doesn't.
