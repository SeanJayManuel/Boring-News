// Runs the exported page in jsdom and reports what a reader would see.
//   node tests/page_smoke.cjs <index.html> <url>
// Scripts run for real, so this exercises web/app.js against the published
// payload. Output is JSON for tests/test_published_site.py.
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");

const [html, url] = [fs.readFileSync(process.argv[2], "utf8"), process.argv[3]];
const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push(String(e.detail || e)));
vc.on("error", (e) => errors.push(String(e)));

let scrolledTo = null;
const dom = new JSDOM(html, {
  url, runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc,
  beforeParse(window) {
    window.scrollTo = () => {};
    window.HTMLElement.prototype.scrollIntoView = function () { scrolledTo = this; };
  },
});
const { document } = dom.window;
const docs = [...document.querySelectorAll("#param-table code")].map((n) => n.textContent.split("=")[0]);
const anchors = [...document.querySelectorAll("[id^='story-']")].map((n) => n.id);
const threshold = document.getElementById("threshold-strict");
threshold.checked = true;
threshold.dispatchEvent(new dom.window.Event("change"));

console.log(JSON.stringify({
  errors,
  lede: document.getElementById("lede").textContent,
  spotlight: document.querySelectorAll("#spotlight article.story").length,
  anchors,
  duplicates: anchors.filter((id, i) => anchors.indexOf(id) !== i),
  scrolledTo: scrolledTo && scrolledTo.id,
  scrolledToHidden: !!(scrolledTo && scrolledTo.closest("[hidden]")),
  ticker: document.querySelectorAll("#ticker-track .tick").length,
  dataLink: !!document.querySelector("#data-line a"),
  feedUrl: document.getElementById("feed-url").value,
  docs,
  settings: dom.window.BoringCore.SETTINGS.map((x) => x.name),
}));
dom.window.close();
