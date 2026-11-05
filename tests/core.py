"""Run web/core.js from a test."""

import json
import shutil
import subprocess

from boringnews import config


def run_core(data: dict, queries=(), scores=(), index=None, threads=()) -> dict:
    out = subprocess.run([shutil.which("node"), str(config.ROOT / "tests" / "core_runner.cjs")],
                         input=json.dumps({"data": data, "queries": list(queries), "scores": list(scores),
                                           "index": index, "threads": list(threads)}),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def select(data: dict, query: str = "") -> dict:
    return run_core(data, queries=[query])["selections"][0]
