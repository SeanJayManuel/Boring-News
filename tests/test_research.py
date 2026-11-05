"""The Research tab's tools in web/core.js, over the real index."""

import json
import shutil
import subprocess

from boringnews import config, research
from boringnews.db import connect
from boringnews.pipeline import main as pipeline_main
from boringnews.sources import load_sources

NODE = shutil.which("node")

RESEARCH_RUNNER = r"""
require(process.argv[2]);
const idx = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
const R = globalThis.BoringCore.research;
const q = (s) => R.lookup(idx, s).matches.map(m => m.story.headline);
console.log(JSON.stringify({
  claim: q("Judge blocked the voter ID rule"),
  numbers: q("Westmark unemployment 4.1%"),
  nothing: q("aliens landed in Westmark"),
  exact: R.lookup(idx, "https://example.com/liberty-daily/water-bill-farms").how,
  slug: q("https://news.example.org/2026/11/brightline-ebike-recall-battery"),
  uncovered: R.searchRecords(idx, {uncovered: true}).length,
  statements: R.searchRecords(idx, {role: "statement"}).map(r => r.source_id),
  words: R.searchRecords(idx, {q: "voter"}).map(r => r.source_id),
}));
"""


def test_research_tools(tmp_path):
    db = tmp_path / "t.db"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", "2026-11-04", "--db", str(db)])
    index = research.build(connect(db), load_sources(config.FIXTURE_SOURCES_PATH))
    assert len(index["stories"]) == 17 and len(index["records"]) == 7
    assert sum(1 for r in index["records"] if r["outlets"] == 0) == 4

    idx_path = tmp_path / "research.json"
    idx_path.write_text(json.dumps(index))
    runner = tmp_path / "r.js"
    runner.write_text(RESEARCH_RUNNER)
    out = json.loads(subprocess.run([NODE, str(runner), str(config.ROOT / "web" / "core.js"), str(idx_path)],
                                    capture_output=True, text=True, check=True).stdout)
    assert out["claim"][0] == "Judge blocks Westmark voter ID rule until trial"
    assert out["numbers"][0].startswith("Westmark adds 14,200 jobs")
    assert out["nothing"] == []                       # no coverage is reported as none, never as false
    assert out["exact"] == "link"
    assert out["slug"][0].startswith("Brightline recalls")
    assert out["uncovered"] == 4
    assert out["statements"] == ["westmark-defense"]
    assert out["words"] == ["westmark-courts"]
