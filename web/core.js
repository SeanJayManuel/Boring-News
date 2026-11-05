// Boring News core: the selection rubric, reader settings and RSS output.
// One copy, used by the reader page (inlined before app.js) and by the
// Cloudflare Pages function that serves custom feeds (functions/feed.xml.js).
// Python uses it too, for ready-made feeds (boringnews/reader.py). The only rules
// that also exist in Python are the score and lane (boringnews/rubric.py), because
// the pipeline needs them; tests/test_parity.py checks that both agree.
(function (root) {
  "use strict";
  var SPECTRUM = ["left", "center", "right"];
  var OUTLET_TYPES = ["wire", "national", "regional", "international"];
  var FALSE = ["0", "false", "no"];

  // Every reader setting, once. Reading and writing the address, the defaults
  // and the page's check for settings in its address all come from this list.
  var SETTINGS = [
    { name: "topics", kind: "list", value: [], allowed: function (D) { return Object.keys(D.topics); },
      aliases: function (D) { return D.topic_aliases; } },
    { name: "exclude", kind: "list", value: [] },
    { name: "threshold", kind: "choice", value: "standard", allowed: function (D) { return Object.keys(D.rubric.thresholds); } },
    { name: "official", kind: "flag", value: true },
    { name: "statements", kind: "flag", value: true },
    { name: "spotlight", kind: "flag", value: false },
    { name: "length", kind: "choice", value: "full", allowed: function () { return ["full", "headlines"]; } }
  ];
  var DEFAULTS = {};
  SETTINGS.forEach(function (x) { DEFAULTS[x.name] = x.value; });

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function create(D) {
    var R = D.rubric;

    function isStatement(s) { return s.type === "primary" && s.role !== "record"; }

    // ---------- rubric (score matches rubric.py)
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
        return sc.hasRecord ? "A government record; no news coverage yet." : "A government statement; no news coverage yet.";
      }
      var spectrum = !sc.leans.length ? "no rated outlets"
        : sc.leans.length === 1 ? sc.leans[0]
        : sc.leans.slice(0, -1).join(", ") + " and " + sc.leans[sc.leans.length - 1];
      return sc.outlets + (sc.outlets === 1 ? " outlet" : " outlets") + " across " + spectrum + "." +
        (sc.hasRecord ? " Backed by a government record." : "") + " Score " + sc.total.toFixed(2) + ".";
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

    // ---------- preferences
    function list(x, v) {
      var allowed = x.allowed && x.allowed(D), aliases = (x.aliases && x.aliases(D)) || {};
      return v.split(",").map(function (i) {
        i = i.trim();
        return Object.prototype.hasOwnProperty.call(aliases, i) ? aliases[i] : i;
      }).filter(function (i, n, arr) {
        return i && (!allowed || allowed.indexOf(i) >= 0) && arr.indexOf(i) === n;
      }).sort();
    }
    function fromQuery(search) {
      var q = new URLSearchParams(search);
      var p = clone(DEFAULTS);
      SETTINGS.forEach(function (x) {
        if (!q.has(x.name)) return;
        var v = q.get(x.name);
        if (x.kind === "list") p[x.name] = list(x, v);
        else if (x.kind === "flag") p[x.name] = FALSE.indexOf(v) < 0;
        else if (x.allowed(D).indexOf(v) >= 0) p[x.name] = v;
      });
      return p;
    }
    function toQuery(p) {
      var parts = [];
      SETTINGS.forEach(function (x) {
        var v = p[x.name];
        if (x.kind === "list") { if (v.length) parts.push(x.name + "=" + v.map(encodeURIComponent).join(",")); }
        else if (v !== x.value) parts.push(x.name + "=" + (x.kind === "flag" ? (v ? "1" : "0") : v));
      });
      return parts.join("&");
    }

    // ---------- RSS
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
        var title = x.lane === "main" ? s.headline
          : (x.score.hasRecord ? "Government record: " : "Government statement: ") + s.headline;
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

  // ---------- research tools (coverage lookup, records search)
  // These describe coverage. They never judge whether a claim is true.
  var STOP = ("a an and are as at be been but by for from has have he her his i if in into is it its of on or " +
    "our she so than that the their them they this to was were will with you your not no after over says said " +
    "new more about who what when where why how http https www com org gov html").split(" ");
  function tokens(text) {
    return (String(text || "").toLowerCase().match(/[a-z0-9]+(?:\.[0-9]+)?/g) || [])
      .map(function (w) { return w.length > 4 && /[^s]s$/.test(w) ? w.slice(0, -1) : w; })
      .filter(function (w) { return w.length > 1 && STOP.indexOf(w) < 0; });
  }
  function isUrl(q) { return /^https?:\/\//i.test(String(q).trim()); }
  function urlWords(q) {
    // Only the words in the path: dates, ids and the site's own name say nothing about the story.
    try {
      return new URL(String(q).trim()).pathname.split(/[\/_\-.]+/)
        .filter(function (w) { return /[a-z]/i.test(w) && !/^(index|html?|php|amp|article|story|news)$/i.test(w); }).join(" ");
    } catch (e) { return q; }
  }

  // Find stories in the index that match a claim, headline or link.
  function lookup(index, query, opts) {
    opts = opts || {};
    var q = String(query || "").trim();
    if (!q || !index) return { matches: [], how: "empty" };
    if (isUrl(q)) {
      var exact = index.stories.filter(function (s) {
        return s.articles.some(function (a) { return a.url.replace(/\/$/, "") === q.replace(/\/$/, ""); });
      });
      if (exact.length) return { matches: exact.map(function (s) { return { story: s, strength: 1 }; }), how: "link" };
      q = urlWords(q);
    }
    var qt = tokens(q).filter(function (t, i, a) { return a.indexOf(t) === i; });
    if (!qt.length) return { matches: [], how: "words" };
    var docs = index.stories.map(function (s) {
      var set = {};
      tokens([s.headline].concat(s.bullets, s.articles.map(function (a) { return a.title; })).join(" "))
        .forEach(function (t) { set[t] = true; });
      return set;
    });
    var n = docs.length;
    var idf = {};
    qt.forEach(function (t) {
      var df = docs.filter(function (d) { return d[t]; }).length;
      idf[t] = Math.log((n + 1) / (df + 0.5));
    });
    var total = qt.reduce(function (sum, t) { return sum + idf[t]; }, 0) || 1;
    var min = opts.min || 0.4;
    var matches = index.stories.map(function (s, i) {
      var hit = qt.reduce(function (sum, t) { return sum + (docs[i][t] ? idf[t] : 0); }, 0);
      return { story: s, strength: Math.round((hit / total) * 100) / 100 };
    }).filter(function (m) { return m.strength >= min; })
      .sort(function (a, b) { return b.strength - a.strength || (a.story.date < b.story.date ? 1 : -1); })
      .slice(0, opts.limit || 5);
    return { matches: matches, how: "words" };
  }

  // Filter government records. Every search word must appear (in any order).
  function searchRecords(index, f) {
    f = f || {};
    var qt = tokens(f.q || "");
    return (index ? index.records : []).filter(function (r) {
      if (f.source && r.source_id !== f.source) return false;
      if (f.role && r.role !== f.role) return false;
      if (f.uncovered && r.outlets > 0) return false;
      if (f.from && r.date < f.from) return false;
      if (f.to && r.date > f.to) return false;
      if (qt.length) {
        var have = tokens(r.title + " " + r.summary + " " + r.story_headline);
        if (!qt.every(function (t) { return have.indexOf(t) >= 0; })) return false;
      }
      return true;
    }).sort(function (a, b) { return a.published_at < b.published_at ? 1 : a.published_at > b.published_at ? -1 : 0; });
  }

  root.BoringCore = {
    create: create, DEFAULTS: DEFAULTS, SETTINGS: SETTINGS, SPECTRUM: SPECTRUM,
    research: { tokens: tokens, lookup: lookup, searchRecords: searchRecords }
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
