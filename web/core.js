// Boring News core: the selection rubric, reader settings and RSS output.
// One copy, used by the reader page (inlined before app.js) and by the
// Cloudflare Pages function that serves custom feeds (functions/feed.xml.js).
// It mirrors boringnews/rubric.py, prefs.py and feeds.py; tests/test_parity.py
// checks that both give the same scores and the same stories.
(function (root) {
  "use strict";
  var SPECTRUM = ["left", "center", "right"];
  var OUTLET_TYPES = ["wire", "national", "regional", "international"];
  var FALSE = ["0", "false", "no"];
  var DEFAULTS = { topics: [], regions: [], exclude: [], threshold: "standard", official: true, statements: true, spotlight: false, length: "full" };

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function create(D) {
    var R = D.rubric;

    function isStatement(s) { return s.type === "primary" && s.role !== "record"; }

    // ---------- rubric (mirror of rubric.py)
    function score(sourceIds) {
      var seen = {}, outlets = [], hasRecord = false, hasStatement = false;
      sourceIds.forEach(function (id) {
        var s = D.sources[id];
        if (!s || seen[id]) return;
        seen[id] = true;
        if (s.type !== "primary") outlets.push(s);
        else if (s.role === "record") hasRecord = true;
        else hasStatement = true;
      });
      var leans = SPECTRUM.filter(function (l) { return outlets.some(function (s) { return s.lean === l; }); });
      var types = OUTLET_TYPES.filter(function (t) { return outlets.some(function (s) { return s.type === t; }); });
      var parts = {
        breadth: leans.length / 3,
        coverage: Math.min(Math.log2(1 + outlets.reduce(function (n, s) { return n + (s.weight || 1); }, 0)) / Math.log2(1 + R.coverage_cap), 1),
        diversity: Math.min(types.length / 3, 1),
        record: hasRecord ? 1 : 0
      };
      var total = 0;
      ["breadth", "coverage", "diversity", "record"].forEach(function (k) { total += R.weights[k] * parts[k]; });
      return {
        total: Math.round(total * 1000) / 1000, parts: parts, outlets: outlets.length, leans: leans,
        hasPrimary: hasRecord || hasStatement, hasRecord: hasRecord, hasStatement: hasStatement
      };
    }
    function lane(sc, p) {
      if (sc.outlets >= R.min_outlets && sc.total >= R.thresholds[p.threshold]) return "main";
      if (sc.hasPrimary && p.official) return "official";
      return null;
    }
    function explain(sc) {
      if (sc.outlets === 0 && sc.hasPrimary) {
        return sc.hasRecord ? "From the official record; no news coverage yet." : "An official statement; no news coverage yet.";
      }
      var spectrum = !sc.leans.length ? "no rated outlets"
        : sc.leans.length === 1 ? sc.leans[0]
        : sc.leans.slice(0, -1).join(", ") + " and " + sc.leans[sc.leans.length - 1];
      return sc.outlets + (sc.outlets === 1 ? " outlet" : " outlets") + " across " + spectrum + "." +
        (sc.hasRecord ? " On the official record." : "") + " Score " + sc.total.toFixed(2) + ".";
    }
    function excluded(p) {
      if (p.statements) return p.exclude;
      return p.exclude.concat(Object.keys(D.sources).filter(function (id) { return isStatement(D.sources[id]); }));
    }
    function scoreStory(s, exclude) {
      var kept = s.articles.filter(function (a) { return D.sources[a.source_id] && exclude.indexOf(a.source_id) < 0; });
      return { story: s, articles: kept, score: score(kept.map(function (a) { return a.source_id; })) };
    }
    function select(p) {
      var shown = [], hidden = 0, ex = excluded(p);
      D.stories.forEach(function (s) {
        if (p.topics.length && p.topics.indexOf(s.topic) < 0) { hidden++; return; }
        if (p.regions.length && p.regions.indexOf(s.region) < 0) { hidden++; return; }
        var x = scoreStory(s, ex);
        if (!x.articles.length) { hidden++; return; }
        x.lane = lane(x.score, p);
        if (!x.lane) { hidden++; return; }
        x.why = explain(x.score);
        shown.push(x);
      });
      shown.sort(function (a, b) { return b.score.total - a.score.total || a.story.id - b.story.id; });
      return { shown: shown, hidden: hidden };
    }
    function spotlight(shown) {
      return shown.filter(function (x) { return x.lane === "main"; }).slice(0, R.spotlight);
    }

    // ---------- preferences (mirror of prefs.py)
    function csv(v, allowed) {
      return (v || "").split(",").map(function (x) { return x.trim(); })
        .filter(function (x) { return x && (!allowed || allowed[x]); })
        .filter(function (x, i, arr) { return arr.indexOf(x) === i; }).sort();
    }
    function fromQuery(search) {
      var q = new URLSearchParams(search);
      var p = clone(DEFAULTS);
      if (q.has("topics")) p.topics = csv(q.get("topics"), D.topics);
      if (q.has("regions")) p.regions = csv(q.get("regions"), D.regions);
      if (q.has("exclude")) p.exclude = csv(q.get("exclude"));
      if (R.thresholds[q.get("threshold")] !== undefined) p.threshold = q.get("threshold");
      if (q.has("official")) p.official = FALSE.indexOf(q.get("official")) < 0;
      if (q.has("statements")) p.statements = FALSE.indexOf(q.get("statements")) < 0;
      if (q.has("spotlight")) p.spotlight = FALSE.indexOf(q.get("spotlight")) < 0;
      if (q.get("length") === "headlines") p.length = "headlines";
      return p;
    }
    function toQuery(p) {
      var parts = [];
      if (p.topics.length) parts.push("topics=" + p.topics.join(","));
      if (p.regions.length) parts.push("regions=" + p.regions.join(","));
      if (p.exclude.length) parts.push("exclude=" + p.exclude.join(","));
      if (p.threshold !== "standard") parts.push("threshold=" + p.threshold);
      if (!p.official) parts.push("official=0");
      if (!p.statements) parts.push("statements=0");
      if (p.spotlight) parts.push("spotlight=1");
      if (p.length !== "full") parts.push("length=" + p.length);
      return parts.join("&");
    }

    // ---------- RSS (mirror of feeds.py)
    function esc(s) {
      return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
    function rss(p, baseUrl) {
      var res = select(p);
      var items = p.spotlight ? spotlight(res.shown) : res.shown;
      var pub = new Date(D.edition + "T12:00:00Z").toUTCString().replace("GMT", "+0000");
      var q = toQuery(p);
      var self = baseUrl + "/feed.xml" + (q ? "?" + q : "");
      var out = [
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
        "<title>Boring News</title>",
        "<link>" + esc(baseUrl) + "/</link>",
        '<atom:link href="' + esc(self) + '" rel="self" type="application/rss+xml"/>',
        "<description>The day's news, once a day, without the noise.</description>",
        "<language>en-us</language><ttl>720</ttl>",
        "<lastBuildDate>" + pub + "</lastBuildDate>"
      ];
      items.forEach(function (x) {
        var s = x.story, html = "";
        if (p.length === "full") {
          html += "<ul>" + s.bullets.map(function (b) { return "<li>" + esc(b) + "</li>"; }).join("") + "</ul>";
          if (s.whats_next) html += "<p><b>What's next:</b> " + esc(s.whats_next) + "</p>";
        }
        html += "<p><i>" + esc(x.why) + "</i></p>";
        html += "<p>Sources: " + x.articles.map(function (a) {
          return '<a href="' + esc(a.url) + '">' + esc(D.sources[a.source_id].name) + "</a>";
        }).join(", ") + "</p>";
        var title = x.lane === "main" ? s.headline : "Official: " + s.headline;
        out.push("<item><title>" + esc(title) + "</title>" +
          "<link>" + esc(baseUrl + "/#story-" + s.id) + "</link>" +
          '<guid isPermaLink="false">boringnews-' + D.edition + "-" + s.id + "</guid>" +
          "<category>" + esc(D.topics[s.topic] || s.topic) + "</category>" +
          "<pubDate>" + pub + "</pubDate>" +
          "<description>" + esc(html) + "</description></item>");
      });
      out.push("</channel></rss>\n");
      return out.join("");
    }

    return {
      DEFAULTS: DEFAULTS, score: score, lane: lane, explain: explain, scoreStory: scoreStory,
      select: select, spotlight: spotlight, fromQuery: fromQuery, toQuery: toQuery, rss: rss,
      isStatement: isStatement, excluded: excluded
    };
  }

  root.BoringCore = { create: create, DEFAULTS: DEFAULTS, SPECTRUM: SPECTRUM };
})(typeof globalThis !== "undefined" ? globalThis : this);
