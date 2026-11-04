// Boring News reader page. Applies the same selection rubric as
// boringnews/rubric.py and the same preferences as boringnews/prefs.py.
(function () {
  "use strict";
  var D = window.BORING_NEWS;
  var R = D.rubric;
  var PARTS = [
    ["breadth", "Breadth"], ["record", "Government record"], ["coverage", "Coverage"], ["diversity", "Diversity"]
  ];
  var C = window.BoringCore.create(D);
  var SPECTRUM = window.BoringCore.SPECTRUM;
  var DEFAULTS = C.DEFAULTS;
  var STORE_KEY = "boringnews.prefs.v3";
  var THRESHOLD_LABELS = { broad: "Broad", standard: "Standard", strict: "Strict" };
  var THRESHOLD_HINTS = {
    broad: "Includes stories that only one side of the spectrum covered.",
    standard: "Usually needs coverage from at least two of left, center and right.",
    strict: "Usually needs left, center and right, or two sides plus a government record."
  };
  var VIEWS = ["today", "all-stories", "outlets", "how-it-works", "your-feed"];

  // Rubric and settings live in core.js, shared with the feed function.
  var lane = C.lane, scoreStory = C.scoreStory, select = C.select, spotlight = C.spotlight;
  var fromQuery = C.fromQuery, toQuery = C.toQuery;

  function loadPrefs() {
    if (/[?&](topics|exclude|threshold|official|statements|spotlight|length)=/.test(location.search)) return fromQuery(location.search);
    try {
      var saved = localStorage.getItem(STORE_KEY);
      if (saved !== null) return fromQuery("?" + saved);
    } catch (e) { /* storage unavailable */ }
    return JSON.parse(JSON.stringify(DEFAULTS));
  }
  function savePrefs(p) {
    var q = toQuery(p);
    try { localStorage.setItem(STORE_KEY, q); } catch (e) { /* storage unavailable */ }
    if (window.self === window.top && /^https?:$/.test(location.protocol)) {
      try { history.replaceState(null, "", location.pathname + (q ? "?" + q : "") + location.hash); } catch (e) { /* ignore */ }
    }
  }

  // ---------- helpers
  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "className") n.className = attrs[k];
      else if (k === "style") n.setAttribute("style", attrs[k]);
      else n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function $(id) { return document.getElementById(id); }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }
  function listWords(arr) {
    return arr.length < 2 ? arr.join("") : arr.slice(0, -1).join(", ") + " and " + arr[arr.length - 1];
  }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  var WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];
  function countWord(n) { return n < WORDS.length ? WORDS[n] : String(n); }
  function longDate(iso) {
    return new Date(iso + "T12:00:00Z").toLocaleDateString("en-US",
      { weekday: "long", year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
  }
  function checkbox(id, label, checked, onChange) {
    var input = el("input", { type: "checkbox", id: id });
    input.checked = checked;
    input.addEventListener("change", function () { onChange(input.checked); });
    return el("label", { for: id }, [input, label]);
  }
  function toggleIn(list, value, on) {
    return on ? list.concat(value).sort() : list.filter(function (x) { return x !== value; });
  }
  function topicOrder() { return Object.keys(D.topics); }

  var prefs = loadPrefs();

  // ---------- stories
  function storyNode(item, headlinesOnly) {
    var s = item.story, sc = item.score;
    var topicLine = el("p", { className: "topic" }, [el("span", { className: "topic-name", text: D.topics[s.topic] || s.topic })]);
    if (s.day > 1) topicLine.appendChild(el("span", { className: "badge day", text: "Day " + s.day }));
    if (sc.hasRecord) topicLine.appendChild(el("span", { className: "badge", text: "Government record",
      title: "Backed by a law, rule, court ruling, vote or official statistics" }));
    else if (sc.hasStatement) topicLine.appendChild(el("span", { className: "badge statement", text: "Government statement",
      title: "A government press release or announcement. It doesn't add to the score." }));
    var node = el("article", { className: "story", id: "story-" + s.id }, [topicLine, el("h3", { className: "headline", text: s.headline })]);
    if (headlinesOnly) return node;

    node.appendChild(el("ul", { className: "bullets" }, s.bullets.map(function (b) { return el("li", { text: b }); })));
    if (s.whats_next) node.appendChild(el("p", { className: "next" }, [el("b", { text: "Next: " }), s.whats_next]));

    var meta = el("div", { className: "meta" });
    if (sc.outlets) {
      var meter = el("span", { className: "meter", role: "img", "aria-label": "Covered by " + listWords(sc.leans) },
        SPECTRUM.map(function (l) { return el("i", { className: sc.leans.indexOf(l) >= 0 ? "on" : "" }); }));
      meta.appendChild(el("span", { className: "coverage" }, [meter,
        el("span", { text: plural(sc.outlets, "outlet", "outlets") + " across " + listWords(sc.leans) })]));
    } else {
      meta.appendChild(el("span", { text: "From " + listWords(item.articles.map(function (a) { return D.sources[a.source_id].name; })) + ". No news coverage yet." }));
    }

    var list = el("ul", { className: "sources", hidden: "" }, item.articles.map(function (a) {
      var src = D.sources[a.source_id];
      var who = src.type !== "primary" ? src.name + ", " + src.lean
        : src.name + (src.role === "record" ? ", government record" : ", government statement (doesn't add to the score)");
      return el("li", {}, [el("span", { className: "who", text: who }),
        el("a", { href: a.url, target: "_blank", rel: "noopener", text: a.title })]);
    }));
    list.appendChild(el("li", { className: "score", text: "Score " + sc.total.toFixed(2) + ": " +
      PARTS.map(function (p) { return p[1].toLowerCase() + " " + (R.weights[p[0]] * sc.parts[p[0]]).toFixed(2); }).join(", ") +
      ". Your setting needs " + R.thresholds[prefs.threshold].toFixed(2) + "." }));

    var ck = s.checks || {};
    if (ck.method) {
      var dropped = ck.dropped || [];
      var note = el("li", { className: "checks" }, ["Fact check (" + ck.method + "): " +
        plural(ck.checked || 0, "statement", "statements") + " checked against the sources. " +
        (dropped.length ? dropped.length + (dropped.length === 1 ? " was" : " were") + " removed:" : "Nothing removed.")]);
      if (dropped.length) {
        note.appendChild(el("ul", {}, dropped.map(function (d) {
          return el("li", {}, [el("s", { text: d.text }), " (" + d.reason + ")"]);
        })));
      }
      list.appendChild(note);
    }

    var label = sc.outlets ? "How each outlet headlined it" : "Read the original";
    var btn = el("button", { type: "button", className: "toggle", "aria-expanded": "false", text: label });
    btn.addEventListener("click", function () {
      var open = list.hidden;
      list.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      btn.textContent = open ? "Hide sources" : label;
    });
    meta.appendChild(btn);
    node.appendChild(meta);
    node.appendChild(list);
    return node;
  }

  function sheet(title, note, items, hl, id) {
    var box = el("section", { className: "sheet", "aria-label": title }, [
      el("div", { className: "sheet-head", id: id || null }, [el("h2", { text: title }), note ? el("p", { text: note }) : null])
    ]);
    if (!id) box.firstChild.removeAttribute("id");
    items.forEach(function (x) { box.appendChild(storyNode(x, hl)); });
    return box;
  }

  function showingLine(target, res) {
    var box = $(target);
    box.innerHTML = "";
    var bits = [THRESHOLD_LABELS[prefs.threshold] + " agreement"];
    bits.push(prefs.topics.length ? plural(prefs.topics.length, "category", "categories") : "all categories");
    if (prefs.exclude.length) bits.push(plural(prefs.exclude.length, "source", "sources") + " off");
    var text = "Showing " + listWords(bits) + ". ";
    if (res.hidden) text += plural(res.hidden, "story", "stories") + " left out by your settings. ";
    box.appendChild(document.createTextNode(text));
    box.appendChild(el("a", { href: "#your-feed", text: "Change what you see" }));
  }

  function renderToday(res) {
    var top = spotlight(res.shown);
    var rest = res.shown.length - top.length;
    var hl = prefs.length === "headlines";
    $("lede").textContent = top.length
      ? countWord(top.length) + (top.length === 1 ? " story today." : " stories today.")
      : "Nothing matches your settings.";
    $("sublede").textContent = top.length
      ? "Ranked by how widely left, center and right outlets covered them. Stories backed by a government record, like a new law or a court ruling, rank higher."
      : "Try needing less agreement, or turn on more categories.";
    var box = $("spotlight");
    box.innerHTML = "";
    box.className = hl ? "headlines-only" : "";
    if (top.length) box.appendChild(sheet("Spotlight", "Highest scores today", top, hl));
    var unc = $("uncovered");
    unc.innerHTML = "";
    var records = res.shown.filter(function (x) { return x.lane === "official" && x.score.hasRecord; });
    if (records.length) {
      var sh = el("section", { className: "sheet", "aria-label": "Government records the news missed" }, [
        el("div", { className: "sheet-head" }, [el("h2", { text: "Government records the news missed" }),
          el("p", { text: "Laws, rules and rulings no outlet covered" })])
      ]);
      sh.appendChild(el("ul", { className: "quick" }, records.map(function (x) {
        var a = el("a", { href: "#story-" + x.story.id, text: x.story.headline });
        return el("li", {}, [a, el("span", { text: (D.topics[x.story.topic] || x.story.topic) + ". From " +
          listWords(x.articles.map(function (r) { return D.sources[r.source_id].name; })) + "." })]);
      })));
      unc.appendChild(sh);
    }
    unc.style.marginTop = "20px";
    if (rest > 0) {
      unc.appendChild(el("div", { className: "more" }, [el("a", { href: "#all-stories",
        text: "See all " + res.shown.length + " stories, by category" })]));
      unc.lastChild.style.marginTop = "20px";
    }
    showingLine("showing", res);
  }

  function renderAll(res) {
    var hl = prefs.length === "headlines";
    var groups = {};
    res.shown.forEach(function (x) { (groups[x.story.topic] = groups[x.story.topic] || []).push(x); });
    // Topics ordered by their strongest story, so the day's biggest news comes first.
    var order = Object.keys(groups).sort(function (a, b) {
      return groups[b][0].score.total - groups[a][0].score.total || topicOrder().indexOf(a) - topicOrder().indexOf(b);
    });

    var official = res.shown.filter(function (x) { return x.score.hasRecord; }).length;
    $("all-summary").textContent = res.shown.length
      ? plural(res.shown.length, "story", "stories") + " in " + plural(order.length, "category", "categories") +
        ", highest score first in each. " + official + " are backed by a government record."
      : "Nothing matches your settings.";

    var jump = $("topic-jump");
    jump.innerHTML = "";
    order.forEach(function (t) {
      var a = el("a", { href: "#all-stories" }, [D.topics[t] || t, el("span", { className: "n", text: String(groups[t].length) })]);
      a.addEventListener("click", function (e) { e.preventDefault(); var h = $("topic-" + t); if (h) h.scrollIntoView({ block: "start" }); });
      jump.appendChild(a);
    });

    var box = $("all");
    box.innerHTML = "";
    box.className = "view-stack" + (hl ? " headlines-only" : "");
    box.style.display = "grid";
    box.style.gap = "20px";
    order.forEach(function (t) {
      box.appendChild(sheet(D.topics[t] || t, plural(groups[t].length, "story", "stories"), groups[t], hl, "topic-" + t));
    });
    showingLine("showing-all", res);
  }

  // What each outlet covered, measured against stories every side covered.
  function renderOutlets() {
    var everyone = D.stories.map(function (s) { return scoreStory(s, []); });
    var wide = everyone.filter(function (x) { return x.score.leans.length === 3; });
    var box = $("outlet-list");
    box.innerHTML = "";
    var groups = [["Left", "left"], ["Center", "center"], ["Right", "right"]];
    groups.forEach(function (g) {
      var ids = Object.keys(D.sources).filter(function (id) { return D.sources[id].type !== "primary" && D.sources[id].lean === g[1]; })
        .sort(function (a, b) { return D.sources[a].name.localeCompare(D.sources[b].name); });
      if (!ids.length) return;
      var sh = el("section", { className: "sheet", "aria-label": g[0] + " outlets" }, [
        el("div", { className: "sheet-head" }, [el("h2", { text: g[0] }), el("p", { text: plural(ids.length, "outlet", "outlets") })])
      ]);
      ids.forEach(function (id) {
        function has(x) { return x.articles.some(function (a) { return a.source_id === id; }); }
        var covered = wide.filter(has);
        var missed = wide.filter(function (x) { return !has(x); });
        var oneSided = everyone.filter(function (x) { return x.score.leans.length === 1 && has(x); });
        var total = everyone.filter(has).length;
        var pct = wide.length ? Math.round(100 * covered.length / wide.length) : 0;
        var row = el("div", { className: "outlet" }, [
          el("div", { className: "outlet-head" }, [el("h3", { text: D.sources[id].name }),
            el("span", { text: plural(total, "story", "stories") + " in today's edition" })]),
          el("div", { className: "ratio" }, [
            el("span", { className: "track", role: "img", "aria-label": pct + " percent" }, [el("i", { style: "width:" + pct + "%" })]),
            el("span", { text: "Covered " + covered.length + " of " + wide.length + " stories that every side covered" })
          ])
        ]);
        if (missed.length) {
          row.appendChild(el("p", { className: "label", text: "Didn't run:" }));
          row.appendChild(el("ul", {}, missed.map(function (x) { return el("li", { text: x.story.headline }); })));
        }
        if (oneSided.length) {
          row.appendChild(el("p", { className: "label", text: "Ran, but only its side covered:" }));
          row.appendChild(el("ul", {}, oneSided.map(function (x) { return el("li", { text: x.story.headline }); })));
        }
        sh.appendChild(row);
      });
      box.appendChild(sh);
      box.style.display = "grid";
      box.style.gap = "20px";
    });
  }

  function renderHow() {
    var w = $("weights");
    w.innerHTML = "";
    PARTS.forEach(function (p) {
      var v = R.weights[p[0]];
      w.appendChild(el("div", { className: "weight" }, [
        el("span", { text: p[1] }),
        el("span", { className: "bar" }, [el("i", { style: "width:" + (v * 100) + "%;background:var(--c-" + p[0] + ")" })]),
        el("span", { className: "pct", text: Math.round(v * 100) + "%" })
      ]));
    });
    $("cap").textContent = R.coverage_cap + " outlets";
    $("threshold-text").textContent = "A story makes the edition when its score reaches your threshold (broad " +
      R.thresholds.broad.toFixed(2) + ", standard " + R.thresholds.standard.toFixed(2) + ", strict " +
      R.thresholds.strict.toFixed(2) + ") and at least " + R.min_outlets + " outlets covered it. The top " + R.spotlight +
      " make Today's spotlight. Government records and statements that no outlet covered are listed under their category.";

    var lg = $("legend");
    lg.innerHTML = "";
    PARTS.forEach(function (p) { lg.appendChild(el("span", {}, [el("i", { style: "background:var(--c-" + p[0] + ")" }), p[1]])); });

    var thr = R.thresholds[prefs.threshold];
    $("chart-threshold").textContent = THRESHOLD_LABELS[prefs.threshold].toLowerCase() + " (" + thr.toFixed(2) + ")";
    var rows = D.stories.map(function (s) { return scoreStory(s, C.excluded(prefs)); })
      .filter(function (x) { return x.articles.length; })
      .sort(function (a, b) { return b.score.total - a.score.total; });
    var chart = $("score-chart");
    chart.innerHTML = "";
    rows.forEach(function (x) {
      var inEdition = !!lane(x.score, prefs);
      var stack = el("div", { className: "stack", role: "img",
        "aria-label": "Score " + x.score.total.toFixed(2) + ": " + PARTS.map(function (p) {
          return p[1] + " " + (R.weights[p[0]] * x.score.parts[p[0]]).toFixed(2); }).join(", ") });
      PARTS.forEach(function (p) {
        var v = R.weights[p[0]] * x.score.parts[p[0]];
        if (v > 0) stack.appendChild(el("i", { style: "width:" + (v * 100) + "%;background:var(--c-" + p[0] + ")" }));
      });
      stack.appendChild(el("span", { className: "cut", style: "left:calc(" + (thr * 100) + "% - 1px)" }));
      chart.appendChild(el("div", { className: "row" + (inEdition ? "" : " out") }, [
        el("div", { className: "row-head" }, [el("span", { text: x.story.headline }),
          el("span", { text: x.score.total.toFixed(2) + (inEdition ? "" : ", left out") })]),
        stack
      ]));
    });

    var tb = $("source-table");
    tb.innerHTML = "";
    Object.keys(D.sources).sort(function (a, b) { return D.sources[a].name.localeCompare(D.sources[b].name); }).forEach(function (id) {
      var s = D.sources[id];
      var raters = s.ratings && Object.keys(s.ratings).length
        ? Object.keys(s.ratings).map(function (r) { return r + ": " + s.ratings[r]; }).join("; ")
        : (s.type === "primary" ? "" : "Starting label");
      tb.appendChild(el("tr", {}, [el("td", { text: s.name }),
        el("td", { text: s.type === "primary" ? "Not rated" : cap(s.lean) }),
        el("td", { text: raters }),
        el("td", { text: s.type === "primary" ? "" : (s.weight || 1).toFixed(2) + " outlets" }),
        el("td", { text: s.type !== "primary" ? cap(s.type) : (s.role === "record" ? "Government record" : "Government statement") })]));
    });
    var cbox = $("corrections");
    cbox.innerHTML = "";
    if (D.corrections && D.corrections.length) {
      cbox.appendChild(el("ul", { className: "corrections" }, D.corrections.map(function (c) {
        return el("li", {}, [el("span", { className: "when", text: c.date + ", edition of " + c.edition }),
          el("b", { text: c.story }), el("span", { text: c.correction })]);
      })));
    } else {
      cbox.appendChild(el("p", { text: "No corrections yet. When a published story is wrong, the correction is listed here with the date, and the list is kept in the public code." }));
    }
    var dl = $("data-line");
    dl.innerHTML = "";
    dl.appendChild(document.createTextNode("Every edition's inputs are published: each article that was read, how they were grouped, every score and every fact-check result. "));
    if (D.data_url) dl.appendChild(el("a", { href: D.data_url, text: "Download today's edition data" }));
    else dl.appendChild(document.createTextNode("Edition files appear here once the site is live."));
    if (D.data_url) dl.appendChild(document.createTextNode("."));

    $("rubric-version").textContent = "Selection rubric version " + R.version + ". Edition of " + longDate(D.edition) + ".";
  }

  // ---------- settings + feed docs
  function renderControls() {
    var th = $("threshold");
    th.innerHTML = "";
    Object.keys(R.thresholds).forEach(function (k) {
      var input = el("input", { type: "radio", name: "threshold", id: "threshold-" + k, value: k });
      input.checked = prefs.threshold === k;
      input.addEventListener("change", function () { prefs.threshold = k; update(); });
      th.appendChild(el("label", { for: "threshold-" + k }, [input, THRESHOLD_LABELS[k]]));
    });
    [["topics", D.topics]].forEach(function (pair) {
      var key = pair[0], map = pair[1], box = $(key);
      box.innerHTML = "";
      Object.keys(map).forEach(function (k) {
        var label = el("span", { className: "opt" }, [el("span", { text: map[k] }),
          D.topic_descriptions && D.topic_descriptions[k] ? el("small", { text: D.topic_descriptions[k] }) : null]);
        box.appendChild(checkbox(key + "-" + k, label, prefs[key].indexOf(k) >= 0, function (on) {
          prefs[key] = toggleIn(prefs[key], k, on); update();
        }));
      });
    });
    var off = $("official");
    off.checked = prefs.official;
    off.onchange = function () { prefs.official = off.checked; update(); };
    var st = $("statements");
    st.checked = prefs.statements;
    st.onchange = function () { prefs.statements = st.checked; update(); };
    var ho = $("headlines-only");
    ho.checked = prefs.length === "headlines";
    ho.onchange = function () { prefs.length = ho.checked ? "headlines" : "full"; update(); };
    var so = $("spotlight-only");
    so.checked = prefs.spotlight;
    so.onchange = function () { prefs.spotlight = so.checked; update(); };

    var groups = $("sources");
    groups.innerHTML = "";
    [["Left", function (s) { return s.lean === "left"; }],
     ["Center", function (s) { return s.lean === "center"; }],
     ["Right", function (s) { return s.lean === "right"; }],
     ["Unrated", function (s) { return s.lean === "unrated" && s.type !== "primary"; }],
     ["Government records", function (s) { return s.type === "primary" && s.role === "record"; }],
     ["Government statements", function (s) { return s.type === "primary" && s.role !== "record"; }]].forEach(function (b) {
      var ids = Object.keys(D.sources).filter(function (id) { return b[1](D.sources[id]); })
        .sort(function (x, y) { return D.sources[x].name.localeCompare(D.sources[y].name); });
      if (!ids.length) return;
      var g = el("div", {}, [el("h3", { text: b[0] })]);
      ids.forEach(function (id) {
        g.appendChild(checkbox("src-" + id, D.sources[id].name, prefs.exclude.indexOf(id) < 0, function (on) {
          prefs.exclude = toggleIn(prefs.exclude, id, !on); update();
        }));
      });
      groups.appendChild(g);
    });
  }

  function renderDocs() {
    var any = Object.keys(D.sources)[0];
    var rows = [
      ["topics=economy,world", "Only these categories: " + Object.keys(D.topics).join(", ") + "."],
      ["exclude=" + any, "Leave out these sources by their id, then score every story again. Ids are listed in sources.yaml."],
      ["threshold=strict", "How much agreement a story needs: broad, standard (default) or strict."],
      ["official=0", "Leave out government records and statements that no outlet has covered yet."],
      ["statements=0", "Leave out government statements, such as White House and agency press releases. Records still count."],
      ["spotlight=1", "Only the top " + R.spotlight + " stories each day."],
      ["length=headlines", "Headlines without the bullet points."]
    ];
    var tb = $("param-table");
    tb.innerHTML = "";
    rows.forEach(function (r) { tb.appendChild(el("tr", {}, [el("td", {}, [el("code", { text: r[0] })]), el("td", { text: r[1] })])); });

    var base = D.base_url + "/feed.xml";
    var ex = [
      ["Just the spotlight", base + "?spotlight=1"],
      ["Economy and world news, strict agreement", base + "?topics=economy,world&threshold=strict"],
      ["Politics and government, no press releases", base + "?topics=government&statements=0"]
    ];
    var ul = $("examples");
    ul.innerHTML = "";
    ex.forEach(function (e) { ul.appendChild(el("li", {}, [el("span", { text: e[0] }), el("code", { text: e[1] })])); });
    $("repo-link").href = D.repo_url;
    Array.prototype.forEach.call(document.querySelectorAll(".spot-n"), function (n) { n.textContent = String(R.spotlight); });
  }

  function renderSettingsSummary() {
    var bits = [THRESHOLD_LABELS[prefs.threshold] + " agreement"];
    bits.push(prefs.topics.length ? prefs.topics.map(function (t) { return D.topics[t]; }).join(", ") : "all categories");
    if (prefs.exclude.length) bits.push(plural(prefs.exclude.length, "source", "sources") + " off");
    if (!prefs.official) bits.push("no uncovered government items");
    if (!prefs.statements) bits.push("no government statements");
    if (prefs.length === "headlines") bits.push("headlines only");
    $("settings-summary").textContent = "Now: " + bits.join(", ") + ".";
    $("threshold-hint").textContent = THRESHOLD_HINTS[prefs.threshold];
    var q = toQuery(prefs);
    $("feed-url").value = D.base_url + "/feed.xml" + (q ? "?" + q : "");
  }

  // ---------- market ticker (yesterday's closes)
  function renderTicker() {
    var items = D.markets || [];
    var box = $("ticker");
    if (!items.length) { box.hidden = true; return; }
    function fmt(v, d) { return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }); }
    function tick(m) {
      var dir = m.change > 0 ? "up" : m.change < 0 ? "down" : "flat";
      var arrow = dir === "up" ? "\u25B2" : dir === "down" ? "\u25BC" : "";
      var size = Math.abs(m.change);
      var change = m.kind === "rate" ? fmt(size, 2) + " pt" : fmt(size, 2) + "%";
      var sign = dir === "up" ? "+" : dir === "down" ? "\u2212" : "";
      var words = m.label + " " + m.prefix + fmt(m.value, m.decimals) + m.suffix + ", " +
        (dir === "flat" ? "unchanged" : (dir === "up" ? "up " : "down ") + change);
      return el("a", { className: "tick", href: m.source_url, target: "_blank", rel: "noopener", title: words + " (FRED)" }, [
        el("b", { text: m.label }),
        el("span", { text: m.prefix + fmt(m.value, m.decimals) + m.suffix }),
        el("span", { className: dir, text: dir === "flat" ? "unch" : arrow + " " + sign + change })
      ]);
    }
    var track = $("ticker-track");
    track.innerHTML = "";
    track.appendChild(el("span", { className: "tick-set" }, items.map(tick)));
    var copy = el("span", { className: "tick-set", "aria-hidden": "true" }, items.map(tick));
    Array.prototype.forEach.call(copy.querySelectorAll("a"), function (a) { a.setAttribute("tabindex", "-1"); });
    track.appendChild(copy);
    track.style.setProperty("--tick-duration", Math.max(30, items.length * 7) + "s");
    var day = items[0].date;
    var label = new Date(day + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
    $("ticker-label").textContent = (D.sample ? "Sample. " : "") + "Close, " + label;
    $("ticker-label").setAttribute("title", "End-of-day values from FRED, the St. Louis Fed's data service");
    $("ticker-label").href = "#how-it-works";
    box.setAttribute("aria-label", "Market closes for " + label);
    box.hidden = false;
  }

  // ---------- routing
  function route() {
    var h = (location.hash || "").replace("#", "");
    var target = null;
    if (/^story-\d+$/.test(h)) { target = h; h = "all-stories"; }
    if (VIEWS.indexOf(h) < 0) h = "today";
    VIEWS.forEach(function (v) { $("view-" + v).hidden = v !== h; });
    Array.prototype.forEach.call(document.querySelectorAll(".tabs a"), function (a) {
      if (a.getAttribute("data-view") === h) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    if (target && $(target)) $(target).scrollIntoView({ block: "start" });
    else window.scrollTo(0, 0);
  }

  // ---------- theme (light by default)
  function setTheme(dark, remember) {
    document.documentElement.classList.toggle("bn-dark", dark);
    var t = $("theme-toggle");
    t.textContent = dark ? "Light" : "Dark";
    t.setAttribute("aria-pressed", String(dark));
    t.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    if (remember) { try { localStorage.setItem("boringnews.theme", dark ? "dark" : "light"); } catch (e) {} }
  }

  function update() {
    savePrefs(prefs);
    var res = select(prefs);
    renderToday(res);
    renderAll(res);
    renderHow();
    renderSettingsSummary();
  }

  setTheme(document.documentElement.classList.contains("bn-dark"), false);
  $("theme-toggle").addEventListener("click", function () {
    setTheme(!document.documentElement.classList.contains("bn-dark"), true);
  });
  $("reset").addEventListener("click", function () {
    prefs = JSON.parse(JSON.stringify(DEFAULTS));
    renderControls();
    update();
  });
  $("copy-feed").addEventListener("click", function () {
    var input = $("feed-url"), status = $("copy-status");
    function fallback() { input.focus(); input.select(); status.textContent = "Selected. Press Ctrl+C or Cmd+C to copy."; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(input.value).then(function () { status.textContent = "Copied."; }, fallback);
    } else fallback();
  });
  window.addEventListener("hashchange", route);

  $("dateline").textContent = longDate(D.edition);
  $("sample-note").hidden = !D.sample;
  renderTicker();
  renderControls();
  renderDocs();
  renderOutlets();
  update();
  route();
})();
