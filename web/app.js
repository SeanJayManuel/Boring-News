// Boring News reader page. Applies the same selection rubric as
// boringnews/rubric.py and the same preferences as boringnews/prefs.py.
(function () {
  "use strict";
  var D = window.BORING_NEWS;
  var R = D.rubric;
  var SPECTRUM = ["left", "center", "right"];
  var OUTLET_TYPES = ["wire", "national", "regional", "international"];
  var STORE_KEY = "boringnews.prefs.v1";
  var DEFAULTS = { topics: [], regions: [], exclude: [], threshold: "standard", underreported: true, length: "full" };
  var THRESHOLD_LABELS = { broad: "Broad", standard: "Standard", strict: "Strict" };
  var THRESHOLD_HINTS = {
    broad: "Includes stories that only one side of the spectrum covered.",
    standard: "Usually needs coverage from at least two of left, center and right.",
    strict: "Usually needs coverage from all three: left, center and right."
  };

  // ---------- rubric (mirror of rubric.py)
  function score(sourceIds) {
    var seen = {}, outlets = [], hasPrimary = false;
    sourceIds.forEach(function (id) {
      var s = D.sources[id];
      if (!s || seen[id]) return;
      seen[id] = true;
      if (s.type === "primary") hasPrimary = true; else outlets.push(s);
    });
    var leans = SPECTRUM.filter(function (l) { return outlets.some(function (s) { return s.lean === l; }); });
    var types = OUTLET_TYPES.filter(function (t) { return outlets.some(function (s) { return s.type === t; }); });
    var breadth = leans.length / 3;
    var coverage = Math.min(Math.log2(1 + outlets.length) / Math.log2(1 + R.coverage_cap), 1);
    var diversity = Math.min(types.length / 3, 1);
    var total = R.weights.breadth * breadth + R.weights.coverage * coverage + R.weights.diversity * diversity;
    return { total: Math.round(total * 1000) / 1000, outlets: outlets.length, leans: leans, hasPrimary: hasPrimary };
  }
  function lane(sc, p) {
    if (sc.outlets >= R.min_outlets && sc.total >= R.thresholds[p.threshold]) return "main";
    if (sc.hasPrimary && p.underreported) return "underreported";
    return null;
  }
  function select(p) {
    var shown = [], hidden = 0;
    D.stories.forEach(function (s) {
      if (p.topics.length && p.topics.indexOf(s.topic) < 0) { hidden++; return; }
      if (p.regions.length && p.regions.indexOf(s.region) < 0) { hidden++; return; }
      var kept = s.articles.filter(function (a) { return D.sources[a.source_id] && p.exclude.indexOf(a.source_id) < 0; });
      if (!kept.length) { hidden++; return; }
      var sc = score(kept.map(function (a) { return a.source_id; }));
      var ln = lane(sc, p);
      if (!ln) { hidden++; return; }
      shown.push({ story: s, lane: ln, score: sc, articles: kept });
    });
    shown.sort(function (a, b) {
      if (a.lane !== b.lane) return a.lane === "main" ? -1 : 1;
      return b.score.total - a.score.total || a.story.id - b.story.id;
    });
    return { shown: shown, hidden: hidden };
  }

  // ---------- preferences (mirror of prefs.py)
  function csv(v, allowed) {
    return (v || "").split(",").map(function (x) { return x.trim(); })
      .filter(function (x) { return x && (!allowed || allowed[x]); })
      .filter(function (x, i, arr) { return arr.indexOf(x) === i; }).sort();
  }
  function fromQuery(search) {
    var q = new URLSearchParams(search);
    var p = JSON.parse(JSON.stringify(DEFAULTS));
    if (q.has("topics")) p.topics = csv(q.get("topics"), D.topics);
    if (q.has("regions")) p.regions = csv(q.get("regions"), D.regions);
    if (q.has("exclude")) p.exclude = csv(q.get("exclude"));
    if (R.thresholds[q.get("threshold")] !== undefined) p.threshold = q.get("threshold");
    if (q.has("underreported")) p.underreported = ["0", "false", "no"].indexOf(q.get("underreported")) < 0;
    if (q.get("length") === "headlines") p.length = "headlines";
    return p;
  }
  function toQuery(p) {
    var parts = [];
    if (p.topics.length) parts.push("topics=" + p.topics.join(","));
    if (p.regions.length) parts.push("regions=" + p.regions.join(","));
    if (p.exclude.length) parts.push("exclude=" + p.exclude.join(","));
    if (p.threshold !== "standard") parts.push("threshold=" + p.threshold);
    if (!p.underreported) parts.push("underreported=0");
    if (p.length !== "full") parts.push("length=" + p.length);
    return parts.join("&");
  }
  function loadPrefs() {
    if (/[?&](topics|regions|exclude|threshold|underreported|length)=/.test(location.search)) return fromQuery(location.search);
    try {
      var saved = localStorage.getItem(STORE_KEY);
      if (saved !== null) return fromQuery("?" + saved);
    } catch (e) { /* storage unavailable */ }
    return JSON.parse(JSON.stringify(DEFAULTS));
  }
  function savePrefs(p) {
    var q = toQuery(p);
    try { localStorage.setItem(STORE_KEY, q); } catch (e) { /* storage unavailable */ }
    // On the real site, keep the address bar in sync so the page URL is shareable too.
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
      else n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }
  function listWords(arr) {
    return arr.length < 2 ? arr.join("") : arr.slice(0, -1).join(", ") + " and " + arr[arr.length - 1];
  }
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

  var prefs = loadPrefs();

  // ---------- settings
  function renderControls() {
    var th = document.getElementById("threshold");
    th.innerHTML = "";
    Object.keys(R.thresholds).forEach(function (k) {
      var input = el("input", { type: "radio", name: "threshold", id: "threshold-" + k, value: k });
      input.checked = prefs.threshold === k;
      input.addEventListener("change", function () { prefs.threshold = k; update(); });
      th.appendChild(el("label", { for: "threshold-" + k }, [input, THRESHOLD_LABELS[k]]));
    });

    [["topics", D.topics], ["regions", D.regions]].forEach(function (pair) {
      var key = pair[0], map = pair[1], box = document.getElementById(key);
      box.innerHTML = "";
      Object.keys(map).forEach(function (k) {
        box.appendChild(checkbox(key + "-" + k, map[k], prefs[key].indexOf(k) >= 0, function (on) {
          prefs[key] = toggleIn(prefs[key], k, on); update();
        }));
      });
    });

    var ur = document.getElementById("underreported");
    ur.checked = prefs.underreported;
    ur.onchange = function () { prefs.underreported = ur.checked; update(); };
    var ho = document.getElementById("headlines-only");
    ho.checked = prefs.length === "headlines";
    ho.onchange = function () { prefs.length = ho.checked ? "headlines" : "full"; update(); };

    var groups = document.getElementById("sources");
    groups.innerHTML = "";
    var buckets = [
      ["Left", function (s) { return s.lean === "left"; }],
      ["Center", function (s) { return s.lean === "center"; }],
      ["Right", function (s) { return s.lean === "right"; }],
      ["Unrated", function (s) { return s.lean === "unrated" && s.type !== "primary"; }],
      ["Official", function (s) { return s.type === "primary"; }]
    ];
    buckets.forEach(function (b) {
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

  function renderSummary() {
    var bits = [THRESHOLD_LABELS[prefs.threshold] + " agreement"];
    bits.push(prefs.topics.length ? prefs.topics.map(function (t) { return D.topics[t]; }).join(", ") : "all topics");
    if (prefs.regions.length) bits.push(prefs.regions.map(function (r) { return D.regions[r]; }).join(", "));
    if (prefs.exclude.length) bits.push(plural(prefs.exclude.length, "outlet off", "outlets off"));
    if (!prefs.underreported) bits.push("no official sources");
    if (prefs.length === "headlines") bits.push("headlines only");
    document.getElementById("settings-summary").textContent = bits.join(", ");
    document.getElementById("threshold-hint").textContent = THRESHOLD_HINTS[prefs.threshold];
  }

  // ---------- edition
  var WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
    "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen", "Twenty"];
  function countWord(n) { return n < WORDS.length ? WORDS[n] : String(n); }

  function storyNode(item, headlinesOnly) {
    var s = item.story, sc = item.score;
    var node = el("article", { className: "story", id: "story-" + s.id }, [
      el("p", { className: "topic", text: D.topics[s.topic] || s.topic }),
      el("h3", { className: "headline", text: s.headline })
    ]);
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
      var names = item.articles.map(function (a) { return D.sources[a.source_id].name; });
      meta.appendChild(el("span", { text: "From " + listWords(names) }));
    }

    var list = el("ul", { className: "sources", hidden: "" }, item.articles.map(function (a) {
      var src = D.sources[a.source_id];
      var who = src.type === "primary" ? src.name + ", official source" : src.name + ", " + src.lean;
      return el("li", {}, [el("span", { className: "who", text: who }),
        el("a", { href: a.url, target: "_blank", rel: "noopener", text: a.title })]);
    }));
    if (sc.outlets) list.appendChild(el("li", { className: "score", text: "Score " + sc.total.toFixed(2) +
      ". Your setting needs " + R.thresholds[prefs.threshold].toFixed(2) + "." }));

    var btn = el("button", { type: "button", className: "toggle", "aria-expanded": "false",
      text: sc.outlets ? "How each outlet headlined it" : "Read the original" });
    btn.addEventListener("click", function () {
      var open = list.hidden;
      list.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      btn.textContent = open ? "Hide" : (sc.outlets ? "How each outlet headlined it" : "Read the original");
    });
    meta.appendChild(btn);
    node.appendChild(meta);
    node.appendChild(list);
    return node;
  }

  function sheet(className, title, note, items, hl) {
    var box = el("section", { className: "sheet " + className, "aria-label": title }, [
      el("div", { className: "sheet-head" }, [el("h2", { text: title }), note ? el("p", { text: note }) : null])
    ]);
    items.forEach(function (x) { box.appendChild(storyNode(x, hl)); });
    return box;
  }

  function renderEdition() {
    var main = document.getElementById("edition");
    main.innerHTML = "";
    main.className = "edition" + (prefs.length === "headlines" ? " headlines-only" : "");
    var res = select(prefs);
    var top = res.shown.filter(function (x) { return x.lane === "main"; });
    var official = res.shown.filter(function (x) { return x.lane === "underreported"; });
    var hl = prefs.length === "headlines";

    document.getElementById("lede").textContent = top.length
      ? countWord(top.length) + (top.length === 1 ? " story today." : " stories today.")
      : "Nothing matches your settings.";
    document.getElementById("sublede").textContent = top.length
      ? (official.length ? "Plus " + plural(official.length, "item", "items") + " straight from official sources. " : "") +
        "Read these and you're caught up until tomorrow."
      : "Try needing less agreement, or turn on more topics.";

    if (top.length) {
      main.appendChild(sheet("today-sheet", "Today", "Covered across the spectrum", top, hl));
    }
    if (official.length) {
      main.appendChild(sheet("official-sheet", "Official sources", "Straight from Congress, agencies and courts", official, hl));
    }
    if (res.hidden) {
      var link = el("a", { href: "#settings", text: "Change settings" });
      link.addEventListener("click", function (e) { e.preventDefault(); openSettings(); });
      main.appendChild(el("p", { className: "left-out" }, [plural(res.hidden, "story", "stories") + " left out by your settings. ", link]));
    }
  }

  function renderFeed() {
    var q = toQuery(prefs);
    document.getElementById("feed-url").value = D.base_url + "/feed.xml" + (q ? "?" + q : "");
  }

  function renderStatic() {
    document.getElementById("dateline").textContent = longDate(D.edition);
    document.getElementById("sample-note").hidden = !D.sample;
    var w = R.weights;
    var f = document.getElementById("formula");
    f.innerHTML = "";
    f.appendChild(el("div", { className: "eq", text: "Score = " + w.breadth.toFixed(2) + " breadth + " +
      w.coverage.toFixed(2) + " coverage + " + w.diversity.toFixed(2) + " diversity" }));
    var dl = el("dl");
    Object.keys(R.thresholds).forEach(function (k) {
      dl.appendChild(el("dt", { text: THRESHOLD_LABELS[k] }));
      dl.appendChild(el("dd", { text: "needs a score of " + R.thresholds[k].toFixed(2) + " or more" }));
    });
    f.appendChild(dl);
    document.getElementById("cap").textContent = R.coverage_cap + " outlets";
    document.getElementById("min-outlets").textContent = String(R.min_outlets);
    var tb = document.getElementById("source-table");
    Object.keys(D.sources).sort(function (a, b) { return D.sources[a].name.localeCompare(D.sources[b].name); }).forEach(function (id) {
      var s = D.sources[id];
      tb.appendChild(el("tr", {}, [el("td", { text: s.name }),
        el("td", { text: s.type === "primary" ? "Not rated" : s.lean.charAt(0).toUpperCase() + s.lean.slice(1) }),
        el("td", { text: s.type === "primary" ? "Official" : s.type.charAt(0).toUpperCase() + s.type.slice(1) })]));
    });
    document.getElementById("rubric-version").textContent = "Selection rubric version " + R.version + ". Edition of " + longDate(D.edition) + ".";
  }

  // ---------- theme (light by default)
  function setTheme(dark, remember) {
    document.documentElement.classList.toggle("bn-dark", dark);
    var t = document.getElementById("theme-toggle");
    t.textContent = dark ? "Light" : "Dark";
    t.setAttribute("aria-pressed", String(dark));
    t.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    if (remember) { try { localStorage.setItem("boringnews.theme", dark ? "dark" : "light"); } catch (e) {} }
  }
  setTheme(document.documentElement.classList.contains("bn-dark"), false);
  document.getElementById("theme-toggle").addEventListener("click", function () {
    setTheme(!document.documentElement.classList.contains("bn-dark"), true);
  });

  function openSettings() {
    var d = document.getElementById("settings");
    d.open = true;
    d.scrollIntoView({ block: "start" });
  }

  function update() {
    savePrefs(prefs);
    renderSummary();
    renderEdition();
    renderFeed();
  }

  document.getElementById("open-settings").addEventListener("click", function (e) { e.preventDefault(); openSettings(); });
  document.getElementById("close-settings").addEventListener("click", function () { document.getElementById("settings").open = false; });
  document.getElementById("reset").addEventListener("click", function () {
    prefs = JSON.parse(JSON.stringify(DEFAULTS));
    renderControls();
    update();
  });
  document.getElementById("copy-feed").addEventListener("click", function () {
    var input = document.getElementById("feed-url");
    var status = document.getElementById("copy-status");
    function fallback() { input.focus(); input.select(); status.textContent = "Selected. Press Ctrl+C or Cmd+C to copy."; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(input.value).then(function () { status.textContent = "Copied."; }, fallback);
    } else fallback();
  });

  renderStatic();
  renderControls();
  update();
})();
