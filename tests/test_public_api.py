"""The public data: files under api/v1/ from a real export, and the unmodified
functions/mcp.js answering real requests against that exported folder."""

import base64
import json
import re
import shutil
import subprocess
import zipfile
from fnmatch import fnmatch
from pathlib import Path

import pytest

from boringnews import config
from boringnews.edition import FORMAT
from boringnews.export_static import main as export_main
from boringnews.pipeline import main as pipeline_main

NODE = shutil.which("node")
BASE = "https://example.org"
MCP = f"{BASE}/mcp"
DATES = ["2026-10-31", "2026-11-03", "2026-11-04"]
LATEST = DATES[-1]
MODERN = "2026-07-28"
LEGACY = "2025-11-25"
TOOLS = ["get_edition", "search_coverage", "search_records", "list_sources"]

# Runs the function file as Cloudflare would call it. `spa` makes the fake
# ASSETS answer missing files the way Pages does with no 404.html: 200 and the
# home page. Every console call is recorded, to prove queries aren't logged.
RUNNER = r"""
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { pathToFileURL } from "url";
const [fn, site, mode, input] = process.argv.slice(2);
const logged = [];
const assets = [];
const write = console.log;
for (const k of ["log", "info", "warn", "error", "debug"]) console[k] = (...a) => logged.push(a);
const mod = await import(pathToFileURL(fn).href);
const env = { ASSETS: { fetch: async (u) => {
  const file = join(site, new URL(u).pathname);
  assets.push(new URL(u).pathname);
  if (existsSync(file)) return new Response(readFileSync(file, "utf8"));
  if (mode === "spa") return new Response("<!doctype html><title>home</title>", { status: 200 });
  return new Response("", { status: 404 });
} } };
const out = [];
for (const r of JSON.parse(input)) {
  const res = await mod.onRequest({
    request: new Request(r.url, { method: r.method, headers: r.headers, body: r.body }), env });
  out.push({ status: res.status, headers: Object.fromEntries(res.headers), body: await res.text() });
}
write(JSON.stringify({ out, logged, assets }));
"""


def build(tmp: Path, dates: list[str], archive: bool = True, name: str = "site") -> Path:
    db, arch, out = tmp / f"{name}.db", tmp / f"{name}-arch", tmp / name
    for d in dates:
        pipeline_main(["run", "--fixtures", "--mock-llm", "--date", d, "--db", str(db), "--archive", str(arch)])
    export_main(["--out", str(out), "--db", str(db), "--sample", "--base-url", BASE,
                 "--archive", str(arch if archive else tmp / "none")])
    return out


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    return build(tmp_path_factory.mktemp("api"), DATES)


@pytest.fixture(scope="module")
def runner(tmp_path_factory):
    """The unmodified function and core.js, as .mjs and .js side by side."""
    tmp = tmp_path_factory.mktemp("fn")
    (tmp / "functions").mkdir()
    (tmp / "web").mkdir()
    fn = tmp / "functions" / "mcp.mjs"
    shutil.copy(config.ROOT / "functions" / "mcp.js", fn)
    shutil.copy(config.ROOT / "web" / "core.js", tmp / "web" / "core.js")
    script = tmp / "runner.mjs"
    script.write_text(RUNNER)
    return script, fn


def run(runner, folder: Path, requests: tuple, mode: str = "plain") -> dict:
    script, fn = runner
    done = subprocess.run([NODE, str(script), str(fn), str(folder), mode, json.dumps(requests)],
                          capture_output=True, text=True, check=True)
    assert done.stderr == ""
    result = json.loads(done.stdout)
    assert result["logged"] == []  # nothing about any request is written out
    return result


def send(runner, folder: Path, *requests: dict, mode: str = "plain") -> list[dict]:
    return run(runner, folder, requests, mode)["out"]


def raw(body, headers: dict | None = None, method: str = "POST") -> dict:
    return {"url": MCP, "method": method, "headers": headers or {}, "body": body}


def legacy(method: str, params=None, id=1, headers: dict | None = None) -> dict:
    msg = {"jsonrpc": "2.0", "method": method}
    if id is not None:
        msg["id"] = id
    if params is not None:
        msg["params"] = params
    return raw(json.dumps(msg), {"content-type": "application/json", **(headers or {})})


def modern(method: str, params: dict | None = None, version: str = MODERN, headers: dict | None = None) -> dict:
    meta = {"io.modelcontextprotocol/protocolVersion": version, "io.modelcontextprotocol/clientCapabilities": {}}
    body = {"jsonrpc": "2.0", "id": 7, "method": method, "params": {**(params or {}), "_meta": meta}}
    sent = {"content-type": "application/json", "mcp-protocol-version": version, "mcp-method": method}
    if method == "tools/call":
        sent["mcp-name"] = params["name"]
    return raw(json.dumps(body), {**sent, **(headers or {})})


def one(runner, folder: Path, request: dict, mode: str = "plain") -> dict:
    return send(runner, folder, request, mode=mode)[0]


def body(response: dict) -> dict:
    return json.loads(response["body"])


def tool(runner, folder: Path, name: str, arguments: dict | None = None, mode: str = "plain") -> dict:
    """A tool call over the modern path. Returns the result, parsed."""
    res = one(runner, folder, modern("tools/call", {"name": name, "arguments": arguments or {}}), mode)
    assert res["status"] == 200
    result = body(res)["result"]
    assert result["resultType"] == "complete"
    data = json.loads(result["content"][0]["text"])
    assert result["content"][0]["type"] == "text" and result["structuredContent"] == data
    return {"data": data, "isError": result.get("isError", False)}


def refused(runner, folder: Path, name: str, arguments) -> str:
    out = tool(runner, folder, name, arguments)
    assert out["isError"] is True
    return out["data"]["error"]


# ---------- static files


def test_index_lists_every_edition_and_every_file(site):
    index = json.loads((site / "api/v1/index.json").read_text())
    assert index["api_version"] == 1 and index["edition_format"] == FORMAT and index["sample"] is True
    assert index["latest"] == LATEST
    assert [e["date"] for e in index["editions"]] == DATES[::-1]
    for e in index["editions"]:
        assert e["url"] == f"{BASE}/{e['path']}" and (site / e["path"]).is_file()
    for key in ("latest_edition", "sources", "research"):
        assert index["files"][key]["url"] == f"{BASE}/{index['files'][key]['path']}"
        assert (site / index["files"][key]["path"]).is_file()
    assert index["corrections"] == []


def test_edition_files_are_published_unchanged(site):
    for d in DATES:
        assert (site / f"api/v1/editions/{d}.json").read_bytes() == (site / f"archive/{d}.json").read_bytes()
    assert (site / "api/v1/latest.json").read_bytes() == (site / f"archive/{LATEST}.json").read_bytes()
    story = json.loads((site / "api/v1/latest.json").read_text())["stories"][0]
    assert story["score"]["total"] > 0 and story["articles"]


def test_sources_and_research_files(site):
    sources = json.loads((site / "api/v1/sources.json").read_text())
    assert sources["api_version"] == 1 and sources["sample"] is True
    assert sources["rubric"]["weights"] and len(sources["sources"]) == 14
    assert set(next(iter(sources["sources"].values()))) == {"name", "lean", "type", "role", "weight", "ratings"}

    research = json.loads((site / "api/v1/research.json").read_text())
    page = json.loads((site / "research.json").read_text())
    assert research["api_version"] == 1 and research["sample"] is True
    assert {k: research[k] for k in page} == page  # same index as the page, with a version on top


def test_bulk_files_hold_every_edition_by_month(site, tmp_path):
    index = json.loads((site / "api/v1/index.json").read_text())
    assert [b["month"] for b in index["bulk"]] == ["2026-11", "2026-10"]
    names = []
    for b in index["bulk"]:
        assert b["url"] == f"{BASE}/{b['path']}" and b["bytes"] == (site / b["path"]).stat().st_size
        with zipfile.ZipFile(site / b["path"]) as z:
            assert z.testzip() is None
            names += z.namelist()
            for n in z.namelist():
                assert z.read(n) == (site / "archive" / n).read_bytes()
    assert sorted(names) == [f"{d}.json" for d in DATES]


def test_bulk_files_are_byte_for_byte_repeatable(site, tmp_path):
    """The same editions give the same bytes, so a nightly deploy re-uploads only this month."""
    export_main(["--out", str(tmp_path / "again"), "--db", str(site.parent / "site.db"), "--sample", "--base-url", BASE,
                 "--archive", str(site.parent / "site-arch")])
    for f in (site / "api/v1/bulk").iterdir():
        assert f.read_bytes() == (tmp_path / "again/api/v1/bulk" / f.name).read_bytes()


def header_rules(site: Path) -> dict[str, dict[str, str]]:
    rules, path = {}, None
    for line in (site / "_headers").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("/"):
            path = line.strip()
            rules[path] = {}
        else:
            k, v = line.strip().split(": ", 1)
            rules[path][k] = v
    return rules


def test_headers_open_the_api_to_browsers(site):
    rules = header_rules(site)
    assert rules["/api/*"]["Access-Control-Allow-Origin"] == "*"
    # Cloudflare joins a repeated header with commas, so each file must match
    # exactly one Cache-Control rule or its cache header turns to nonsense.
    for f in (site / "api").rglob("*"):
        if f.is_file():
            url = "/" + f.relative_to(site).as_posix()
            matches = [p for p, h in rules.items() if "Cache-Control" in h and fnmatch(url, p)]
            assert len(matches) == 1, url


def test_missing_paths_are_a_real_404(site):
    """Without a top-level 404.html, Pages answers any missing path with 200 and the home page."""
    assert (site / "404.html").is_file()


def test_export_without_an_archive_says_so(tmp_path):
    site = build(tmp_path, [LATEST], archive=False)
    index = json.loads((site / "api/v1/index.json").read_text())
    assert index["editions"] == [] and index["latest"] is None and index["bulk"] == []
    assert "latest_edition" not in index["files"]
    assert not (site / "api/v1/latest.json").exists()
    assert (site / "api/v1/sources.json").is_file() and (site / "api/v1/research.json").is_file()


def test_export_keeps_only_dated_edition_files(tmp_path):
    db, arch = tmp_path / "t.db", tmp_path / "arch"
    pipeline_main(["run", "--fixtures", "--mock-llm", "--date", LATEST, "--db", str(db), "--archive", str(arch)])
    (arch / "notes.json").write_text("{}")
    export_main(["--out", str(tmp_path / "s"), "--db", str(db), "--sample", "--archive", str(arch)])
    index = json.loads((tmp_path / "s/api/v1/index.json").read_text())
    assert [e["date"] for e in index["editions"]] == [LATEST]


def test_docs_are_published_and_linked_from_the_research_tab(site):
    docs = (site / "api/docs.md").read_text()
    assert docs == (config.ROOT / "docs/api.md").read_text()
    for name in [*TOOLS, "api/v1/index.json", "api/v1/latest.json", "api/v1/sources.json", "api/v1/research.json",
                 "api/v1/editions/", "api/v1/bulk/", "AGPL-3.0", "CC BY-SA 4.0", "30 days", "https://example.org/mcp"]:
        assert name in docs, name
    page = (config.ROOT / "web/index.html").read_text()
    section = page[page.index('id="view-research"'):page.index("<!-- How it works -->")]
    assert re.search(r'<a [^>]*href="api/docs\.md"', section)


# ---------- MCP: the older handshake


@pytest.mark.parametrize("asked, answered", [(LEGACY, LEGACY), ("2025-06-18", "2025-06-18"), ("2025-03-26", "2025-03-26"),
                                             ("1999-01-01", LEGACY), (MODERN, LEGACY)])
def test_initialize_settles_on_a_version_it_serves(site, runner, asked, answered):
    res = one(runner, site, legacy("initialize", {"protocolVersion": asked, "capabilities": {},
                                                  "clientInfo": {"name": "t", "version": "1"}}))
    assert res["status"] == 200 and res["headers"]["content-type"].startswith("application/json")
    assert "mcp-session-id" not in res["headers"]  # stateless
    result = body(res)["result"]
    assert result["protocolVersion"] == answered and result["capabilities"] == {"tools": {}}
    assert result["serverInfo"]["name"] == "boring-news"
    assert "never" in result["instructions"].lower()


def test_old_client_full_conversation(site, runner):
    init, note, ping, listed, called = send(
        runner, site,
        legacy("initialize", {"protocolVersion": LEGACY, "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}),
        legacy("notifications/initialized", id=None, headers={"mcp-protocol-version": LEGACY}),
        legacy("ping", {}, headers={"mcp-protocol-version": LEGACY}),
        legacy("tools/list", {}, headers={"mcp-protocol-version": LEGACY}),
        legacy("tools/call", {"name": "list_sources", "arguments": {}}, headers={"mcp-protocol-version": LEGACY}))
    assert init["status"] == 200
    assert note["status"] == 202 and note["body"] == ""
    assert body(ping) == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert [t["name"] for t in body(listed)["result"]["tools"]] == TOOLS
    assert len(json.loads(body(called)["result"]["content"][0]["text"])["sources"]) == 14


def test_old_client_without_a_version_header_still_works(site, runner):
    assert body(one(runner, site, legacy("tools/list")))["result"]["tools"]


def test_old_client_unknown_method_is_a_json_rpc_error(site, runner):
    res = one(runner, site, legacy("resources/list"))
    assert res["status"] == 200 and body(res)["error"]["code"] == -32601


def test_old_client_bad_version_header(site, runner):
    res = one(runner, site, legacy("tools/list", headers={"mcp-protocol-version": "2020-01-01"}))
    assert res["status"] == 400 and body(res)["error"]["code"] == -32022


# ---------- MCP: the current revision


def test_discover(site, runner):
    res = one(runner, site, modern("server/discover"))
    assert res["status"] == 200
    result = body(res)["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"][0] == MODERN and LEGACY in result["supportedVersions"]
    assert result["capabilities"] == {"tools": {}}
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "boring-news"
    assert result["cacheScope"] == "public" and result["ttlMs"] > 0
    assert "never" in result["instructions"].lower()


def test_tools_list_describes_the_tools_and_the_rule(site, runner):
    result = body(one(runner, site, modern("tools/list")))["result"]
    assert result["resultType"] == "complete" and result["cacheScope"] == "public" and result["ttlMs"] > 0
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "boring-news"
    tools = {t["name"]: t for t in result["tools"]}
    assert [t["name"] for t in result["tools"]] == TOOLS  # same order every time
    for t in tools.values():
        assert t["inputSchema"]["type"] == "object" and t["inputSchema"]["additionalProperties"] is False
        assert t["annotations"]["readOnlyHint"] is True
        assert "never judge" in t["description"]  # the project's rule, in what the model reads
    for name in ("search_coverage", "search_records"):
        assert "30 days" in tools[name]["description"]


def test_unsupported_version_lists_what_is_supported(site, runner):
    res = one(runner, site, modern("tools/list", version="1900-01-01"))
    assert res["status"] == 400
    err = body(res)["error"]
    assert err["code"] == -32022 and body(res)["id"] == 7
    assert err["data"]["requested"] == "1900-01-01" and MODERN in err["data"]["supported"]


def test_missing_client_capabilities_is_malformed(site, runner):
    req = modern("tools/list")
    msg = json.loads(req["body"])
    del msg["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"]
    res = one(runner, site, {**req, "body": json.dumps(msg)})
    assert res["status"] == 400 and body(res)["error"]["code"] == -32602


@pytest.mark.parametrize("change", [
    {"mcp-protocol-version": None},
    {"mcp-protocol-version": LEGACY},
    {"mcp-method": None},
    {"mcp-method": "server/discover"},
    {"mcp-name": None},
    {"mcp-name": "search_records"},
    {"mcp-name": "=?base64?not base64?="},
])
def test_headers_must_match_the_body(site, runner, change):
    req = modern("tools/call", {"name": "list_sources", "arguments": {}})
    headers = {k: v for k, v in {**req["headers"], **change}.items() if v is not None}
    res = one(runner, site, {**req, "headers": headers})
    assert res["status"] == 400
    assert body(res)["error"]["code"] == -32020 and body(res)["id"] == 7


def test_mcp_name_may_be_base64(site, runner):
    encoded = "=?base64?" + base64.b64encode(b"list_sources").decode() + "?="
    res = one(runner, site, modern("tools/call", {"name": "list_sources", "arguments": {}}, headers={"mcp-name": encoded}))
    assert res["status"] == 200 and "result" in body(res)


@pytest.mark.parametrize("method", ["ping", "resources/list", "subscriptions/listen", "nonsense"])
def test_unknown_method_is_404_on_the_current_revision(site, runner, method):
    res = one(runner, site, modern(method))
    assert res["status"] == 404 and body(res)["error"]["code"] == -32601


# ---------- MCP: HTTP


@pytest.mark.parametrize("method", ["GET", "DELETE", "PUT", "PATCH", "HEAD"])
def test_only_post(site, runner, method):
    res = one(runner, site, raw(None, method=method))
    assert res["status"] == 405 and "POST" in res["headers"]["allow"]
    assert res["headers"]["access-control-allow-origin"] == "*"


def test_preflight_lets_a_browser_page_call_it(site, runner):
    res = one(runner, site, raw(None, {"origin": "https://student.example", "access-control-request-method": "POST",
                                       "access-control-request-headers": "content-type,mcp-protocol-version"}, "OPTIONS"))
    assert res["status"] == 204 and res["body"] == ""
    h = res["headers"]
    assert h["access-control-allow-origin"] == "*" and "POST" in h["access-control-allow-methods"]
    allowed = h["access-control-allow-headers"].lower()
    for name in ("content-type", "accept", "mcp-protocol-version", "mcp-method", "mcp-name"):
        assert name in allowed


def test_every_answer_can_be_read_by_a_browser_and_is_never_cached(site, runner):
    """_headers doesn't reach function responses on Cloudflare, so the function must set these."""
    for req in (modern("tools/list"), legacy("initialize", {"protocolVersion": LEGACY, "capabilities": {}}),
                legacy("notifications/initialized", id=None), raw("not json")):
        h = one(runner, site, req)["headers"]
        assert h["access-control-allow-origin"] == "*" and h["cache-control"] == "no-store"


def test_any_origin_is_accepted(site, runner):
    """A public read-only server with nothing private: there's no origin to protect against."""
    res = one(runner, site, legacy("ping", headers={"origin": "https://student.example"}))
    assert res["status"] == 200


@pytest.mark.parametrize("payload, code", [
    ("not json", -32700),
    ("", -32700),
    ("[]", -32600),
    ('[{"jsonrpc":"2.0","id":1,"method":"ping"}]', -32600),
    ('"ping"', -32600),
    ("null", -32600),
    ('{"id":1,"method":"ping"}', -32600),
    ('{"jsonrpc":"1.0","id":1,"method":"ping"}', -32600),
    ('{"jsonrpc":"2.0","id":null,"method":"ping"}', -32600),
    ('{"jsonrpc":"2.0","id":{},"method":"ping"}', -32600),
    ('{"jsonrpc":"2.0","id":1,"method":7}', -32600),
    ('{"jsonrpc":"2.0","id":1}', -32600),
    ('{"jsonrpc":"2.0","id":1,"result":{}}', -32600),
])
def test_malformed_messages(site, runner, payload, code):
    res = one(runner, site, raw(payload))
    assert res["status"] == 400 and body(res)["error"]["code"] == code


def test_an_id_that_can_be_read_comes_back_on_an_error(site, runner):
    res = one(runner, site, raw('{"jsonrpc":"1.0","id":9,"method":"ping"}'))
    assert body(res)["id"] == 9


def test_oversized_body(site, runner):
    res = one(runner, site, raw(" " * 70_000))
    assert res["status"] == 413 and body(res)["error"]["code"] == -32600


@pytest.mark.parametrize("params", [[1, 2], "x"])
def test_params_must_be_an_object(site, runner, params):
    res = one(runner, site, legacy("tools/list", params))
    assert body(res)["error"]["code"] == -32602


@pytest.mark.parametrize("params", [{"protocolVersion": 7, "capabilities": {}}, {}])
def test_initialize_needs_a_version(site, runner, params):
    assert body(one(runner, site, legacy("initialize", params)))["error"]["code"] == -32602


@pytest.mark.parametrize("params", [
    {"name": "delete_everything", "arguments": {}},
    {"name": "__proto__", "arguments": {}},
    {"name": "constructor", "arguments": {}},
    {"name": 7},
    {},
    {"name": "get_edition", "arguments": [1]},
    {"name": "get_edition", "arguments": "x"},
])
def test_bad_tool_calls_are_protocol_errors(site, runner, params):
    res = one(runner, site, legacy("tools/call", params))
    assert res["status"] == 200 and body(res)["error"]["code"] == -32602


def test_arguments_may_be_left_out(site, runner):
    res = one(runner, site, legacy("tools/call", {"name": "get_edition"}))
    assert json.loads(body(res)["result"]["content"][0]["text"])["edition"] == LATEST


# ---------- tools


def test_get_edition_defaults_to_the_latest(site, runner):
    data = tool(runner, site, "get_edition")["data"]
    file = json.loads((site / f"archive/{LATEST}.json").read_text())
    assert data["edition"] == LATEST and data["total"] == 17 and data["returned"] == 17
    assert data["url"] == f"{BASE}/api/v1/editions/{LATEST}.json"
    totals = [s["score"]["total"] for s in data["stories"]]
    assert totals == sorted(totals, reverse=True)
    story = data["stories"][0]
    want = next(s for s in file["stories"] if s["id"] == story["id"])
    assert story["headline"] == want["headline"] and story["score"] == want["score"]
    assert [a["url"] for a in story["articles"]] == want["articles"]
    first = story["articles"][0]
    assert first["outlet"] == file["sources"][first["source_id"]]["name"]
    assert first["title"] and first["lean"]
    assert "checks" not in story and "summary" not in first  # those stay in the full file
    assert "judge" in data["note"]


def test_get_edition_by_date_and_limit(site, runner):
    data = tool(runner, site, "get_edition", {"date": LATEST, "limit": 3})["data"]
    assert data["edition"] == LATEST and data["returned"] == 3 == len(data["stories"]) and data["total"] == 17
    quiet = tool(runner, site, "get_edition", {"date": DATES[0]})  # a day with no stories is still an edition
    assert quiet["isError"] is False and quiet["data"]["edition"] == DATES[0] and quiet["data"]["stories"] == []


def test_get_edition_skips_an_article_the_file_does_not_hold(site, runner, tmp_path):
    copy = tmp_path / "site"
    shutil.copytree(site, copy)
    latest = copy / "api/v1/latest.json"
    data = json.loads(latest.read_text())
    data["stories"][0]["articles"].append("https://example.com/not-in-this-file")
    latest.write_text(json.dumps(data))
    stories = {s["id"]: s for s in tool(runner, copy, "get_edition")["data"]["stories"]}
    assert all(a["url"] != "https://example.com/not-in-this-file" for s in stories.values() for a in s["articles"])


@pytest.mark.parametrize("mode", ["plain", "spa"])
def test_get_edition_for_a_date_we_never_published(site, runner, mode):
    """`spa` is Pages' fallback: a 200 with the home page rather than a 404."""
    out = tool(runner, site, "get_edition", {"date": "2001-01-01"}, mode=mode)
    assert out["isError"] is True and "2001-01-01" in out["data"]["error"]


@pytest.mark.parametrize("arguments, word", [
    ({"date": "../../etc/passwd"}, "date"),
    ({"date": "2026-11-04/../../x"}, "date"),
    ({"date": "2026-11-4"}, "date"),
    ({"date": "2026-11-04\n"}, "date"),
    ({"date": 20261104}, "date"),
    ({"date": ["2026-11-04"]}, "date"),
    ({"limit": 0}, "limit"),
    ({"limit": 101}, "limit"),
    ({"limit": 1.5}, "limit"),
    ({"limit": "5"}, "limit"),
    ({"extra": 1}, "extra"),
])
def test_get_edition_refuses_bad_input(site, runner, arguments, word):
    assert word in refused(runner, site, "get_edition", arguments)


def test_search_coverage_finds_who_covered_a_claim(site, runner):
    data = tool(runner, site, "search_coverage", {"query": "Judge blocked the voter ID rule"})["data"]
    assert data["how"] == "words" and data["last_days"] == 30
    top = data["matches"][0]
    assert top["headline"] == "Judge blocks Westmark voter ID rule until trial" and top["date"] == LATEST
    assert top["strength"] > 0 and top["score"]["outlets"] > 0 and top["why"]
    assert top["covered_by"] and {"source_id", "outlet", "lean", "type", "title", "url"} <= set(top["covered_by"][0])
    covered = {c["source_id"] for c in top["covered_by"]}
    sources = json.loads((site / "api/v1/sources.json").read_text())["sources"]
    assert top["did_not_run"] == sorted(s["name"] for k, s in sources.items()
                                        if s["type"] != "primary" and s["lean"] != "unrated" and k not in covered)
    assert "true" in data["note"].lower()


def test_search_coverage_by_link(site, runner):
    data = tool(runner, site, "search_coverage", {"query": "https://example.com/liberty-daily/water-bill-farms"})["data"]
    assert data["how"] == "link" and data["matches"][0]["strength"] == 1


def test_no_coverage_is_never_called_false(site, runner):
    data = tool(runner, site, "search_coverage", {"query": "aliens landed in Westmark"})
    assert data["isError"] is False and data["data"]["matches"] == []
    assert "doesn't mean it's false" in data["data"]["note"]


def test_search_coverage_limit(site, runner):
    many = tool(runner, site, "search_coverage", {"query": "Westmark", "limit": 2})["data"]
    assert len(many["matches"]) <= 2


@pytest.mark.parametrize("arguments, word", [
    ({}, "query"),
    ({"query": 7}, "query"),
    ({"query": ""}, "query"),
    ({"query": "x" * 501}, "query"),
    ({"query": ["a"]}, "query"),
    ({"query": {"toString": "x"}}, "query"),
    ({"query": "water", "limit": 21}, "limit"),
    ({"query": "water", "limit": -1}, "limit"),
    ({"query": "water", "min": 0}, "min"),
])
def test_search_coverage_refuses_bad_input(site, runner, arguments, word):
    assert word in refused(runner, site, "search_coverage", arguments)


def test_search_records_filters(site, runner):
    everything = tool(runner, site, "search_records")["data"]
    index = json.loads((site / "api/v1/research.json").read_text())
    assert everything["total"] == len(index["records"]) == everything["returned"]
    assert everything["last_days"] == 30 and "judge" in everything["note"]

    words = tool(runner, site, "search_records", {"q": "voter"})["data"]
    assert words["records"] and all(r["source_id"] == "westmark-courts" for r in words["records"])
    assert all(r["outlets"] == 0 for r in tool(runner, site, "search_records", {"uncovered": True})["data"]["records"])
    assert {r["role"] for r in tool(runner, site, "search_records", {"role": "statement"})["data"]["records"]} == {"statement"}
    only = tool(runner, site, "search_records", {"source": "westmark-defense"})["data"]["records"]
    assert only and {r["source_id"] for r in only} == {"westmark-defense"}
    assert {r["date"] for r in tool(runner, site, "search_records", {"from": DATES[1], "to": DATES[1]})["data"]["records"]} <= {DATES[1]}
    assert tool(runner, site, "search_records", {"from": "2030-01-01"})["data"]["records"] == []
    capped = tool(runner, site, "search_records", {"limit": 1})["data"]
    assert capped["returned"] == 1 and capped["total"] == everything["total"]


@pytest.mark.parametrize("arguments, word", [
    ({"q": 7}, "q"),
    ({"q": "x" * 501}, "q"),
    ({"source": "../secret"}, "source"),
    ({"source": 7}, "source"),
    ({"role": "opinion"}, "role"),
    ({"uncovered": "yes"}, "uncovered"),
    ({"from": "yesterday"}, "from"),
    ({"to": 2026}, "to"),
    ({"limit": 51}, "limit"),
    ({"limit": 0}, "limit"),
    ({"__proto__": 1}, "__proto__"),
])
def test_search_records_refuses_bad_input(site, runner, arguments, word):
    assert word in refused(runner, site, "search_records", arguments)


def test_list_sources(site, runner):
    data = tool(runner, site, "list_sources")["data"]
    published = json.loads((site / "api/v1/sources.json").read_text())
    assert data["sources"] == published["sources"] and data["rubric"] == published["rubric"]
    assert "judge" in data["note"]


def test_list_sources_takes_no_arguments(site, runner):
    assert "extra" in refused(runner, site, "list_sources", {"extra": 1})


def test_searches_read_the_big_file_once_per_isolate(site, runner):
    """Free-plan CPU is 10 ms a request, and parsing the index can use all of it."""
    search = modern("tools/call", {"name": "search_records", "arguments": {"q": "voter"}})
    result = run(runner, site, (search, search, search))
    assert result["assets"].count("/api/v1/research.json") == 1
    assert all("result" in body(r) for r in result["out"])


# ---------- MCP before anything is published


@pytest.mark.parametrize("mode", ["plain", "spa"])
@pytest.mark.parametrize("name, arguments", [("get_edition", {}), ("search_coverage", {"query": "water"}),
                                             ("search_records", {}), ("list_sources", {})])
def test_tools_explain_a_missing_site(runner, tmp_path, mode, name, arguments):
    out = tool(runner, tmp_path, name, arguments, mode=mode)
    assert out["isError"] is True and "published" in out["data"]["error"]


def test_a_broken_data_file_is_a_tool_error(site, runner, tmp_path):
    copy = tmp_path / "site"
    shutil.copytree(site, copy)
    (copy / "api/v1/research.json").write_text("{ broken")
    assert tool(runner, copy, "search_records")["isError"] is True


def test_handshake_works_with_nothing_published(runner, tmp_path):
    assert one(runner, tmp_path, modern("server/discover"))["status"] == 200
    assert body(one(runner, tmp_path, modern("tools/list")))["result"]["tools"]
