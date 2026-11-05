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
  // The four parts of the score, in the order the weights setting lists them.
  var WEIGHT_PARTS = ["breadth", "coverage", "diversity", "record"];
  var NAME_LENGTH = 60;
  // Why a story isn't shown, each named for the setting that would bring it back.
  var REASONS = [
    { id: "topic", label: "Outside your categories" },
    { id: "sources", label: "All its sources are off" },
    { id: "threshold", label: "Below your threshold" },
    { id: "official", label: "Government items you turned off" }
  ];
  // Example recipes. Plain settings links: they change how much is shown or what
  // ranks first, and never single out an outlet or a side of the spectrum.
  var RECIPES = [
    { name: "Every side covered it", query: "threshold=strict", note: "The most agreement: usually left, center and right." },
    { name: "Paper trail", query: "weights=20,20,10,50", note: "Stories backed by a law, rule or ruling come first." },
    { name: "No press releases", query: "statements=0", note: "Records stay. Government statements go." },
    { name: "Money and the world", query: "topics=economy,world", note: "Two categories, nothing else." }
  ];

  // Every reader setting, once. Reading and writing the address, the defaults
  // and the page's check for settings in its address all come from this list.
  var SETTINGS = [
    { name: "topics", kind: "list", value: [], allowed: function (D) { return Object.keys(D.topics); },
      aliases: function (D) { return D.topic_aliases; } },
    { name: "exclude", kind: "list", value: [] },
    { name: "threshold", kind: "choice", value: "standard", allowed: function (D) { return Object.keys(D.rubric.thresholds); } },
    // Null means the published weights, which come with the edition.
    { name: "weights", kind: "weights", value: null },
    { name: "official", kind: "flag", value: true },
    { name: "statements", kind: "flag", value: true },
    { name: "spotlight", kind: "flag", value: false },
    { name: "length", kind: "choice", value: "full", allowed: function () { return ["full", "headlines"]; } },
    { name: "recipe", kind: "text", value: "" }
  ];
  var DEFAULTS = {};
  SETTINGS.forEach(function (x) { DEFAULTS[x.name] = x.value; });

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  // A recipe's name comes from whoever made the link, so it's cut down to plain
  // text: no line breaks, invisible characters or text-direction tricks.
  function cleanName(v) {
    return String(v).replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]/g, "")
      .replace(/\s+/g, " ").trim().slice(0, NAME_LENGTH).replace(/[\ud800-\udbff]$/, "").trim();
  }

  function create(D) {
    var R = D.rubric;

    function isStatement(s) { return s.type === "primary" && s.role !== "record"; }

    // ---------- rubric (score matches rubric.py)
    function score(sourceIds, weights) {
      var w = weights || R.weights;
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
      var total = 0, points = {};
      WEIGHT_PARTS.forEach(function (k) { points[k] = w[k] * parts[k]; total += points[k]; });
      return {
        total: Math.round(total * 1000) / 1000, parts: parts, points: points, custom: w !== R.weights,
        outlets: outlets.length, leans: leans,
        hasPrimary: hasRecord || hasStatement, hasRecord: hasRecord, hasStatement: hasStatement
      };
    }
    // A reader's weights are four whole numbers from 0 to 100, in WEIGHT_PARTS order.
    // Only their shares matter, so a score still runs from 0 to 1 and the thresholds
    // still apply. Anything invalid, or the published weights at any scale, is null.
    function cleanWeights(v) {
      if (!v || v.length !== WEIGHT_PARTS.length) return null;
      if (!v.every(function (n) { return n === Math.floor(n) && n >= 0 && n <= 100; })) return null;
      var sum = v.reduce(function (a, b) { return a + b; }, 0);
      if (!sum) return null;
      var same = WEIGHT_PARTS.every(function (k, i) { return Math.abs(v[i] / sum - R.weights[k]) < 1e-9; });
      return same ? null : v;
    }
    function weightsFor(p) {
      if (!p.weights) return R.weights;
      var sum = p.weights.reduce(function (a, b) { return a + b; }, 0), w = {};
      WEIGHT_PARTS.forEach(function (k, i) { w[k] = p.weights[i] / sum; });
      return w;
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
        (sc.hasRecord ? " Backed by a government record." : "") + " Score " + sc.total.toFixed(2) +
        (sc.custom ? " with your weights." : ".");
    }
    function leftOutWhy(reason, x, p) {
      var s = x.story, sc = x.score;
      var known = s.articles.filter(function (a) { return D.sources[a.source_id]; });
      if (reason === "topic") return "Its category, " + (D.topics[s.topic] || s.topic) + ", isn't one you chose.";
      if (reason === "sources") {
        if (!known.length) return "None of its sources are on the source list any more.";
        var onlyStatements = !p.statements && known.every(function (a) {
          return isStatement(D.sources[a.source_id]) && p.exclude.indexOf(a.source_id) < 0;
        });
        return onlyStatements ? "It comes only from government statements, and you turned those off."
          : "You turned off every source that covered it.";
      }
      var needs = R.thresholds[p.threshold], short = [];
      if (sc.outlets < R.min_outlets) {
        short.push("Only " + plural(sc.outlets, "outlet", "outlets") + " covered it; it needs at least " + R.min_outlets + ".");
      }
      if (sc.total < needs) {
        short.push("Score " + sc.total.toFixed(2) + (sc.custom ? " with your weights" : "") + "; your setting needs " + needs.toFixed(2) + ".");
      }
      if (x.articles.length < known.length) short.push("Sources you turned off no longer count toward it.");
      if (reason === "threshold") return short.join(" ");
      var item = "A government " + (sc.hasRecord ? "record" : "statement");
      return (sc.outlets ? [item + " that didn't make the main list."].concat(short) : [item + " no outlet covered."])
        .concat("You turned those off.").join(" ");
    }
    function excluded(p) {
      if (p.statements) return p.exclude;
      return p.exclude.concat(Object.keys(D.sources).filter(function (id) { return isStatement(D.sources[id]); }));
    }
    function scoreStory(s, exclude, weights) {
      var kept = s.articles.filter(function (a) { return D.sources[a.source_id] && exclude.indexOf(a.source_id) < 0; });
      return { story: s, articles: kept, score: score(kept.map(function (a) { return a.source_id; }), weights) };
    }
    function select(p) {
      var shown = [], filtered = [], ex = excluded(p), w = weightsFor(p);
      function byScore(a, b) { return b.score.total - a.score.total || a.story.id - b.story.id; }
      D.stories.forEach(function (s) {
        var x = scoreStory(s, ex, w), reason = null;
        if (p.topics.length && p.topics.indexOf(s.topic) < 0) reason = "topic";
        else if (!x.articles.length) reason = "sources";
        else {
          x.lane = lane(x.score, p);
          if (x.lane) { x.why = explain(x.score); shown.push(x); return; }
          reason = x.score.hasPrimary ? "official" : "threshold";
        }
        x.reason = reason;
        x.why = leftOutWhy(reason, x, p);
        filtered.push(x);
      });
      return { shown: shown.sort(byScore), hidden: filtered.length, filtered: filtered.sort(byScore) };
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
        else if (x.kind === "weights") p[x.name] = cleanWeights(v.split(",").map(function (n) { return /^\s*\d+\s*$/.test(n) ? Number(n) : NaN; }));
        else if (x.kind === "text") p[x.name] = cleanName(v);
        else if (x.allowed(D).indexOf(v) >= 0) p[x.name] = v;
      });
      return p;
    }
    function toQuery(p) {
      var parts = [];
      SETTINGS.forEach(function (x) {
        var v = p[x.name];
        if (x.kind === "list") { if (v.length) parts.push(x.name + "=" + v.map(encodeURIComponent).join(",")); }
        else if (v !== x.value) parts.push(x.name + "=" + (x.kind === "flag" ? (v ? "1" : "0") : x.kind === "text" ? encodeURIComponent(v) : v));
      });
      return parts.join("&");
    }
    function link(p, path) {
      var q = toQuery(p);
      return D.base_url + path + (q ? "?" + q : "");
    }
    function recipes() {
      return RECIPES.map(function (r) {
        return { name: r.name, note: r.note, query: r.query + "&recipe=" + encodeURIComponent(r.name) };
      });
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
        "<title>Boring News" + (p.recipe ? ": " + esc(p.recipe) : "") + "</title>",
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
      isStatement: isStatement, excluded: excluded, cleanWeights: cleanWeights, cleanName: cleanName,
      weightsFor: weightsFor, link: link, recipes: recipes
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

  // The earlier days of a story, oldest first. Null when the index can't say: it
  // didn't load, it doesn't have this story, or the story has no thread. Threads
  // are matched whole, because the end of a thread id is a position, not a story id.
  function earlier(index, date, id) {
    if (!index) return null;
    var me = index.stories.filter(function (s) { return s.date === date && s.id === id; })[0];
    if (!me || !me.thread_id) return null;
    var days = index.stories.filter(function (s) { return s.thread_id === me.thread_id && s.date < date; })
      .sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
    return { days: days, missing: Math.max(0, (me.day || 1) - 1 - days.length) };
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
    WEIGHT_PARTS: WEIGHT_PARTS, REASONS: REASONS,
    research: { tokens: tokens, lookup: lookup, searchRecords: searchRecords, earlier: earlier }
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
