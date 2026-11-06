// Runs the exported page in jsdom and reports what a reader would see.
//   node tests/page_smoke.cjs <index.html> <url> [ok|missing|down]
// Scripts run for real, so this exercises web/app.js against the published
// payload. The last argument says how research.json answers: from the file
// beside the page, with a 404, or not at all. Output is JSON for
// tests/test_published_site.py.
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const [html, url, research = "ok"] = [fs.readFileSync(process.argv[2], "utf8"), process.argv[3], process.argv[4]];
const dir = path.dirname(process.argv[2]);
const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push(String(e.detail || e)));
vc.on("error", (e) => errors.push(String(e)));

let scrolledTo = null;
const fetched = [];
const dom = new JSDOM(html, {
  url, runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc,
  beforeParse(window) {
    window.scrollTo = () => {};
    window.HTMLElement.prototype.scrollIntoView = function () { scrolledTo = this; };
    window.fetch = (file) => {
      fetched.push(String(file));
      if (research === "down") return Promise.reject(new Error("offline"));
      if (research === "missing") return Promise.resolve({ ok: false, status: 404 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(fs.readFileSync(path.join(dir, String(file)), "utf8"))) });
    };
  },
});
const { document, Event } = dom.window;
const byId = (id) => document.getElementById(id);
const text = (n) => (n ? n.textContent : null);
const texts = (selector) => [...document.querySelectorAll(selector)].map((n) => n.textContent);
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function see() {
  const stack = document.querySelector("#score-chart .stack");
  return {
    lede: text(byId("lede")),
    sublede: text(byId("sublede")),
    showing: text(byId("showing")),
    feedUrl: byId("feed-url").value,
    leftOutSummary: text(document.querySelector("#left-out summary")),
    leftOutAllSummary: text(document.querySelector("#left-out-all summary")),
    leftOutGroups: texts("#left-out h3"),
    leftOut: [...document.querySelectorAll("#left-out .left-story")].map((n) => ({
      headline: text(n.querySelector("h4")), why: text(n.querySelector(".why")),
      bullets: n.querySelectorAll(".bullets li").length, sources: n.querySelectorAll(".source-line a").length,
    })),
    scoreLine: text(document.querySelector("#all .score")),
    chartLabel: stack && stack.getAttribute("aria-label"),
    chartWidths: stack && [...stack.querySelectorAll("i")].map((n) => parseFloat(n.style.width)),
    chartNote: text(byId("chart-weights")),
    weightsYours: byId("weights-yours").hidden ? null : text(byId("weights-yours")),
    weightsNow: text(byId("weights-now")),
    thresholdHint: text(byId("threshold-hint")),
    sliders: [...document.querySelectorAll("#weight-controls input")].map((n) => Number(n.value)),
    shares: texts("#weight-controls .pct"),
    recipeName: byId("recipe-name").value,
    recipeNote: byId("recipe-note").hidden ? null : text(byId("recipe-note")),
    recipeLink: byId("recipe-link").value,
  };
}

async function main() {
  await tick(); await tick(); await tick();
  const docs = [...document.querySelectorAll("#param-table code")].map((n) => n.textContent.split("=")[0]);
  const anchors = [...document.querySelectorAll("[id^='story-']")].map((n) => n.id);
  const loaded = see();
  const gapSides = document.querySelectorAll(".side.gap").length;
  const oneSide = [...document.querySelectorAll("#one-side .quick a")].map((n) => n.getAttribute("href"));
  const threshold = byId("threshold-strict");
  threshold.checked = true;
  threshold.dispatchEvent(new Event("change"));
  const strict = see();

  const report = {
    errors,
    lede: byId("lede").textContent,
    spotlight: document.querySelectorAll("#spotlight article.story, #spot-rest article.story").length,
    anchors,
    duplicates: anchors.filter((id, i) => anchors.indexOf(id) !== i),
    scrolledTo: scrolledTo && scrolledTo.id,
    scrolledToHidden: !!(scrolledTo && scrolledTo.closest("[hidden]")),
    ticker: document.querySelectorAll("#ticker-track .tick").length,
    tickerLabel: text(byId("ticker-label")),
    tickDates: texts("#ticker-track .tick-set:first-child .tick-date"),
    ledgerLede: text(byId("ledger-lede")),
    ledgerRows: document.querySelectorAll("#ledger-out tbody tr").length,
    ledgerIn: text(byId("ledger-in")),
    ledgerRules: document.querySelectorAll("#ledger-rules li").length,
    dataLink: !!document.querySelector("#data-line a"),
    feedUrl: byId("feed-url").value,
    docs,
    sideColumns: texts("#story-page .side-col h4"),
    leadLink: document.querySelector("#spotlight .meta a") && document.querySelector("#spotlight .meta a").getAttribute("href"),
    storyTitle: byId("view-story").hidden ? null : text(byId("story-title")),
    storyNote: text(byId("story-note")),
    storyScore: text(document.querySelector("#story-page .score")),
    title: document.title,
    notices: texts("#notices .notice"),
    footLinks: document.querySelectorAll(".foot-links a").length,
    socialImage: document.querySelector('meta[property="og:image"]').content,
    contactEmail: byId("contact-email").hidden ? null : text(byId("contact-email")),
    tabCount: document.querySelectorAll(".tabs a").length,
    sideSaid: texts("#story-page .side-said"),
    storyHeads: texts("#story-page h2"),
    storyLines: texts("#story-page .sheet-head p"),
    storySides: texts("#story-page .side-col .who"),
    wrongLink: document.querySelector("#story-page .story-wrong a") && document.querySelector("#story-page .story-wrong a").href,
    relatedLinks: document.querySelectorAll("#story-page .related a").length,
    plates: document.querySelectorAll("#view-today .plate").length,
    gapCircles: document.querySelectorAll("#view-today .plate-gap").length,
    leadRings: document.querySelectorAll(".lead .plate-ring").length,
    summaries: document.querySelectorAll("#spotlight .what, #spot-rest .what").length,
    gapSides,
    oneSide,
    settings: dom.window.BoringCore.SETTINGS.map((x) => x.name),
    loaded,
    strict,
    anchoredLeftOut: document.querySelectorAll(".left-out [id^='story-']").length,
    recipes: [...document.querySelectorAll("#recipe-list a")].map((a) => a.getAttribute("href")),
  };

  // Developing stories: nothing is fetched until a reader asks.
  const toggle = document.querySelector("#all .earlier-toggle");
  report.earlierButtons = document.querySelectorAll("#all .earlier-toggle").length;
  report.fetchedOnLoad = fetched.length;
  if (toggle) {
    toggle.click();
    await tick(); await tick(); await tick();
    const box = toggle.closest("article").querySelector(".earlier");
    report.earlier = {
      days: [...box.querySelectorAll(".earlier-day")].map((n) => ({
        when: text(n.querySelector(".topic")), headline: text(n.querySelector("h4")),
        bullets: n.querySelectorAll(".bullets li").length, sources: n.querySelectorAll(".source-line a").length,
      })),
      message: text(box.querySelector(".hint")),
      open: !box.hidden,
      fetched: fetched.length,
    };
  }

  // Controls, last, so the reports above show the page as loaded.
  const slider = byId("weight-record");
  slider.value = "100";
  slider.dispatchEvent(new Event("input"));
  report.slid = see();
  byId("recipe-name").value = "  My   mix ";
  byId("recipe-name").dispatchEvent(new Event("input"));
  report.named = see();
  byId("copy-recipe").click();
  report.copyStatus = text(byId("recipe-status"));
  report.savedQuery = dom.window.localStorage.getItem("boringnews.prefs.v3");
  byId("reset").click();
  report.reset = see();
  ["breadth", "coverage", "diversity", "record"].forEach((k) => {
    byId("weight-" + k).value = "0";
    byId("weight-" + k).dispatchEvent(new Event("input"));
  });
  report.allZero = see();

  console.log(JSON.stringify(report));
  dom.window.close();
}

main();
