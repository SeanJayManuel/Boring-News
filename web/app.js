// Standard Edition reader page. The rubric and settings it applies are in core.js.
(function () {
  "use strict";
  var D = window.BORING_NEWS;
  var R = D.rubric;
  var PARTS = [
    ["breadth", "Breadth"], ["record", "Government record"], ["coverage", "Coverage"], ["diversity", "Diversity"]
  ];
  var C = window.BoringCore.create(D);
  var SPECTRUM = window.BoringCore.SPECTRUM;
  var WEIGHT_PARTS = window.BoringCore.WEIGHT_PARTS;
  var DEFAULTS = C.DEFAULTS;
  var STORE_KEY = "boringnews.prefs.v3";
  var THRESHOLD_LABELS = { broad: "Broad", standard: "Standard", strict: "Strict" };
  var THRESHOLD_HINTS = {
    broad: "Includes stories that only one side of the spectrum covered.",
    standard: "Usually needs coverage from at least two of left, center and right.",
    strict: "Usually needs left, center and right, or two sides plus a government record."
  };
  var VIEWS = ["today", "all-stories", "outlets", "research", "how-it-works", "your-feed"];

  // Rubric and settings live in core.js, shared with the feed function.
  var lane = C.lane, scoreStory = C.scoreStory, select = C.select, spotlight = C.spotlight;
  var fromQuery = C.fromQuery, toQuery = C.toQuery;

  function loadPrefs() {
    var address = new URLSearchParams(location.search);
    if (window.BoringCore.SETTINGS.some(function (x) { return address.has(x.name); })) return fromQuery(location.search);
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
      else if (attrs[k] !== null) n.setAttribute(k, attrs[k]);
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

  function partLabel(k) { return PARTS.filter(function (p) { return p[0] === k; })[0][1]; }
  function weightWords() {
    var w = C.weightsFor(prefs);
    return listWords(WEIGHT_PARTS.map(function (k) { return partLabel(k).toLowerCase() + " " + Math.round(w[k] * 100) + "%"; }));
  }
  function scoreWords(sc) { return "Score " + sc.total.toFixed(2) + (sc.custom ? " with your weights" : ""); }
  function sourceLine(articles) {
    var links = [];
    articles.forEach(function (a) {
      if (links.length) links.push(", ");
      links.push(el("a", { href: a.url, target: "_blank", rel: "noopener", text: D.sources[a.source_id] ? D.sources[a.source_id].name : a.source_id }));
    });
    return el("p", { className: "source-line" }, ["Sources: "].concat(links).concat("."));
  }

  // ---------- earlier days of a developing story
  // The index is a large file, so it's only fetched when a reader asks.
  function earlierDays(s) {
    var label = "Earlier days of this story", done = false;
    var box = el("div", { className: "earlier", hidden: "", "aria-live": "polite" });
    var btn = el("button", { type: "button", className: "toggle earlier-toggle", "aria-expanded": "false", text: label });
    function say(text) { box.innerHTML = ""; box.appendChild(el("p", { className: "hint", text: text })); }
    function unavailable() { say("Earlier days aren't available right now. Try again later."); }
    function fill(idx) {
      var found = RS.earlier(idx, D.edition, s.id);
      if (!found) { unavailable(); return; }
      done = true;
      box.innerHTML = "";
      found.days.forEach(function (d) {
        box.appendChild(el("section", { className: "earlier-day" }, [
          el("p", { className: "topic", text: shortDate(d.date) + ", day " + d.day }),
          el("h4", { text: d.headline }),
          el("ul", { className: "bullets" }, d.bullets.map(function (b) { return el("li", { text: b }); })),
          sourceLine(d.articles)
        ]));
      });
      if (found.missing) box.appendChild(el("p", { className: "hint", text: plural(found.missing, "earlier day is", "earlier days are") + " older than the last 30 days of editions." }));
    }
    btn.addEventListener("click", function () {
      var open = box.hidden;
      box.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      btn.textContent = open ? "Hide earlier days" : label;
      if (!open || done) return;
      say("Loading…");
      loadResearch().then(fill, unavailable);
    });
    return { button: btn, box: box };
  }

  // ---------- stories
  // A story appears twice (Today and All stories), so only one copy, in
  // All stories, carries the #story-N anchor that feed links open.
  function outletsBySide(articles) {
    var sides = {};
    SPECTRUM.forEach(function (l) { sides[l] = []; });
    articles.forEach(function (a) {
      var src = D.sources[a.source_id];
      if (!src || src.type === "primary" || !sides[src.lean]) return;
      sides[src.lean].push(a);
    });
    return sides;
  }

  // The scale: one segment per side, one tick per outlet. A side that ran
  // nothing is striped, so what wasn't covered is as visible as what was. A side
  // we couldn't fully read is left blank, because it may have run the story.
  function scale(item) {
    var sides = outletsBySide(item.articles), gap = C.coverageGap(item.score, prefs);
    var missing = gap.missing.filter(function (l) { return gap.unreadSides.indexOf(l) < 0; });
    var words = "Covered by " + listWords(item.score.leans) + (missing.length ? ". Not covered by " + listWords(missing) : "") +
      (gap.unreadSides.length ? ". Unknown for " + listWords(gap.unreadSides) : "");
    return el("span", { className: "scale", role: "img", "aria-label": words }, SPECTRUM.map(function (l) {
      var outlets = {};
      sides[l].forEach(function (a) { outlets[a.source_id] = true; });
      return el("span", { className: "side " + (sides[l].length ? "on" : gap.unreadSides.indexOf(l) >= 0 ? "unread" : "gap") },
        Object.keys(outlets).map(function () { return el("i"); }));
    }));
  }
  function gapWords(sc) {
    var gap = C.coverageGap(sc, prefs);
    if (gap.unread.length) return "We couldn't read " + listWords(gap.unread).replace(" and ", " or ") + " today.";
    return "No " + listWords(gap.missing).replace(" and ", " or ") + " outlet " + (gap.ours ? "" : "you kept ") + "ran this.";
  }

  // The lead story's outlets under the scale, each side in its own column.
  function sideColumns(item) {
    var sides = outletsBySide(item.articles);
    return el("div", { className: "sides" }, SPECTRUM.map(function (l) {
      var rows = sides[l];
      return el("div", { className: "side-col" }, [
        el("h4", { text: cap(l) }),
        rows.length
          ? el("ul", {}, rows.map(function (a) {
              return el("li", {}, [el("span", { className: "who", text: D.sources[a.source_id].name }),
                el("a", { href: a.url, target: "_blank", rel: "noopener", text: a.title })]);
            }))
          : el("p", { className: "none", text: C.coverageGap(item.score, prefs).unreadSides.indexOf(l) >= 0
              ? "Unknown: a " + l + " feed couldn't be read." : "No " + l + " outlet ran this." })
      ]);
    }));
  }

  function storyNode(item, headlinesOnly, anchored, lead) {
    var s = item.story, sc = item.score;
    var topicLine = el("p", { className: "topic" }, [el("span", { className: "topic-name", text: D.topics[s.topic] || s.topic })]);
    if (s.day > 1) topicLine.appendChild(el("span", { className: "badge day", text: "Day " + s.day }));
    if (sc.hasRecord) topicLine.appendChild(el("span", { className: "badge", text: "Government record",
      title: "Backed by a law, rule, court ruling, vote or official statistics" }));
    else if (sc.hasStatement) topicLine.appendChild(el("span", { className: "badge statement", text: "Government statement",
      title: "A government press release or announcement. It doesn't add to the score." }));
    var node = el("article", { className: "story", id: anchored ? "story-" + s.id : null }, [topicLine, el("h3", { className: "headline", text: s.headline })]);
    var days = s.day > 1 ? earlierDays(s) : null;
    if (headlinesOnly) {
      if (days) { node.appendChild(el("div", { className: "meta" }, [days.button])); node.appendChild(days.box); }
      return node;
    }

    if (lead && sc.outlets) {
      node.appendChild(scale(item));
      node.appendChild(sideColumns(item));
    }
    node.appendChild(el("ul", { className: "bullets" }, s.bullets.map(function (b) { return el("li", { text: b }); })));
    if (s.whats_next) node.appendChild(el("p", { className: "next" }, [el("b", { text: "Next: " }), s.whats_next]));

    var meta = el("div", { className: "meta" });
    if (sc.outlets) {
      meta.appendChild(el("span", { className: "coverage" }, [lead ? null : scale(item),
        el("span", { text: plural(sc.outlets, "outlet", "outlets") + " across " + listWords(sc.leans) +
          (sc.leans.length < 3 ? ". " + gapWords(sc) : "") })]));
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
    list.appendChild(el("li", { className: "score", text: scoreWords(sc) + ": " +
      PARTS.map(function (p) { return p[1].toLowerCase() + " " + sc.points[p[0]].toFixed(2); }).join(", ") +
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
    if (days) meta.appendChild(days.button);
    node.appendChild(meta);
    node.appendChild(list);
    if (days) node.appendChild(days.box);
    return node;
  }

  function sheet(title, note, items, hl, id) {
    var box = el("section", { className: "sheet", "aria-label": title }, [
      el("div", { className: "sheet-head", id: id || null }, [el("h2", { text: title }), note ? el("p", { text: note }) : null])
    ]);
    items.forEach(function (x) { box.appendChild(storyNode(x, hl, !!id)); });
    return box;
  }

  function showingLine(target, res) {
    var box = $(target);
    box.innerHTML = "";
    var bits = [THRESHOLD_LABELS[prefs.threshold] + " agreement"];
    bits.push(prefs.topics.length ? plural(prefs.topics.length, "category", "categories") : "all categories");
    if (prefs.exclude.length) bits.push(plural(prefs.exclude.length, "source", "sources") + " off");
    if (prefs.weights) bits.push("your own weights");
    var text = "Showing " + listWords(bits) + ". ";
    if (res.hidden) text += plural(res.hidden, "story", "stories") + " left out by your settings. ";
    box.appendChild(document.createTextNode(text));
    box.appendChild(el("a", { href: "#your-feed", text: "Change what you see" }));
  }

  // What the settings hid, and why. These rows carry no #story-N anchor: a feed
  // link should open the story's place in All stories, not this list.
  function leftOut(target, res) {
    var box = $(target), hl = prefs.length === "headlines";
    box.innerHTML = "";
    if (!res.filtered.length) return;
    var body = el("div", { className: "left-out-body" }, [el("p", { className: "hint",
      text: "Each story your settings hid, and why. Only stories that were written up can be listed: the published rule drops the rest before any setting applies." })]);
    window.BoringCore.REASONS.forEach(function (r) {
      var rows = res.filtered.filter(function (x) { return x.reason === r.id; });
      if (!rows.length) return;
      body.appendChild(el("h3", { text: r.label + " (" + rows.length + ")" }));
      rows.forEach(function (x) {
        var s = x.story, row = el("article", { className: "left-story" }, [
          el("p", { className: "topic", text: D.topics[s.topic] || s.topic }),
          el("h4", { text: s.headline }),
          el("p", { className: "why", text: x.why })
        ]);
        if (!hl) row.appendChild(el("ul", { className: "bullets" }, s.bullets.map(function (b) { return el("li", { text: b }); })));
        if (s.articles.length) row.appendChild(sourceLine(s.articles));
        body.appendChild(row);
      });
    });
    box.appendChild(el("details", { className: "left-out sheet" }, [
      el("summary", { text: "See the " + plural(res.filtered.length, "story", "stories") + " left out, and why" }), body
    ]));
  }

  function renderToday(res) {
    var top = spotlight(res.shown);
    var rest = res.shown.length - top.length;
    var hl = prefs.length === "headlines";
    $("lede").textContent = top.length
      ? countWord(top.length) + (top.length === 1 ? " story today." : " stories today.")
      : "Nothing matches your settings.";
    $("sublede").textContent = top.length
      ? (prefs.weights ? "Ranked by your own weights: " + weightWords() + "."
        : "Ranked by how widely left, center and right outlets covered them. Stories backed by a government record, like a new law or a court ruling, rank higher.")
      : "Try needing less agreement, or turn on more categories.";
    var box = $("spotlight");
    box.innerHTML = "";
    box.className = hl ? "headlines-only" : "";
    if (top.length) box.appendChild(el("div", { className: "lead" }, [storyNode(top[0], hl, false, true)]));
    var restBox = $("spot-rest");
    restBox.innerHTML = "";
    restBox.className = hl ? "headlines-only" : "";
    if (top.length > 1) restBox.appendChild(sheet("Also in the spotlight", "Highest scores today", top.slice(1), hl));
    renderOneSide(res, top);
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
    var more = $("see-all");
    more.innerHTML = "";
    if (rest > 0) {
      more.appendChild(el("div", { className: "more" }, [el("a", { href: "#all-stories",
        text: "See all " + res.shown.length + " stories, by category" })]));
    }
    showingLine("showing", res);
    leftOut("left-out", res);
  }

  // Which stories only one side ran. The thesis in one list: what gets told at all.
  function renderOneSide(res, top) {
    var box = $("one-side");
    box.innerHTML = "";
    var rows = res.shown.filter(function (x) { return C.isBlindspot(x.score) && top.indexOf(x) < 0; });
    if (!rows.length) return;
    box.appendChild(el("section", { className: "sheet", "aria-label": "Only one side covered" }, [
      el("div", { className: "sheet-head" }, [el("h2", { text: "Only one side covered" }),
        el("p", { text: "Two or more outlets on one side ran these" })]),
      el("ul", { className: "quick" }, rows.map(function (x) {
        return el("li", {}, [el("a", { href: "#story-" + x.story.id, text: x.story.headline }),
          el("span", { className: "coverage" }, [scale(x), el("span", { text: C.blindspotWords(x.score, prefs) })])]);
      }))
    ]));
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
    order.forEach(function (t) {
      box.appendChild(sheet(D.topics[t] || t, plural(groups[t].length, "story", "stories"), groups[t], hl, "topic-" + t));
    });
    showingLine("showing-all", res);
    leftOut("left-out-all", res);
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
    var yours = $("weights-yours");
    yours.hidden = !prefs.weights;
    yours.textContent = prefs.weights ? "These bars are the published rule. Your page and feed use your own weights: " + weightWords() + "." : "";
    $("chart-weights").textContent = prefs.weights
      ? " Scored with your own weights: " + weightWords() + ". The thresholds stay the same." : "";
    $("cap").textContent = R.coverage_cap + " outlets";
    $("threshold-text").textContent = "A story makes the edition when its score reaches your threshold (broad " +
      R.thresholds.broad.toFixed(2) + ", standard " + R.thresholds.standard.toFixed(2) + ", strict " +
      R.thresholds.strict.toFixed(2) + ") and at least " + R.min_outlets + " outlets covered it. A story below that which at least " + R.blindspot_outlets + " outlets ran, all on one side, is listed apart under Only one side covered. The top " + R.spotlight +
      " make Today's spotlight. Government records and statements that no outlet covered are listed under their category.";

    var lg = $("legend");
    lg.innerHTML = "";
    PARTS.forEach(function (p) { lg.appendChild(el("span", {}, [el("i", { style: "background:var(--c-" + p[0] + ")" }), p[1]])); });

    var thr = R.thresholds[prefs.threshold];
    $("chart-threshold").textContent = THRESHOLD_LABELS[prefs.threshold].toLowerCase() + " (" + thr.toFixed(2) + ")";
    var rows = D.stories.map(function (s) { return scoreStory(s, C.excluded(prefs), C.weightsFor(prefs)); })
      .filter(function (x) { return x.articles.length; })
      .sort(function (a, b) { return b.score.total - a.score.total; });
    var chart = $("score-chart");
    chart.innerHTML = "";
    rows.forEach(function (x) {
      var inEdition = !!lane(x.score, prefs);
      var stack = el("div", { className: "stack", role: "img",
        "aria-label": scoreWords(x.score) + ": " + PARTS.map(function (p) {
          return p[1] + " " + x.score.points[p[0]].toFixed(2); }).join(", ") });
      PARTS.forEach(function (p) {
        var v = x.score.points[p[0]];
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
    renderWeights();
    $("recipe-name").value = prefs.recipe;
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
    var bs = $("blindspots");
    bs.checked = prefs.blindspots;
    bs.onchange = function () { prefs.blindspots = bs.checked; update(); };
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

  function renderShares() {
    var w = C.weightsFor(prefs);
    WEIGHT_PARTS.forEach(function (k) { $("weight-share-" + k).textContent = Math.round(w[k] * 100) + "%"; });
  }
  function renderWeights() {
    var box = $("weight-controls"), v = prefs.weights;
    box.innerHTML = "";
    WEIGHT_PARTS.forEach(function (k, i) {
      var input = el("input", { type: "range", id: "weight-" + k, min: "0", max: "100", step: "1" });
      input.value = String(v ? v[i] : Math.round(R.weights[k] * 100));
      input.addEventListener("input", function () {
        var values = WEIGHT_PARTS.map(function (part) { return Number($("weight-" + part).value); });
        prefs.weights = C.cleanWeights(values);
        // All four at zero means nothing to rank by, so go back to the published rule.
        if (!values.some(function (n) { return n > 0; })) renderWeights();
        renderShares();
        update();
      });
      box.appendChild(el("div", { className: "weight" }, [
        el("label", { for: "weight-" + k, text: partLabel(k) }), input,
        el("span", { className: "pct", id: "weight-share-" + k })
      ]));
    });
    renderShares();
  }

  function renderDocs() {
    var any = Object.keys(D.sources)[0];
    var rows = [
      ["topics=economy,world", "Only these categories: " + Object.keys(D.topics).join(", ") + "."],
      ["exclude=" + any, "Leave out these sources by their id, then score every story again. Ids are listed in sources.yaml."],
      ["threshold=strict", "How much agreement a story needs: broad, standard (default) or strict."],
      ["weights=60,20,10,10", "Your own weights for " + WEIGHT_PARTS.join(", ") + ": four whole numbers from 0 to 100, in that order. Each counts as its share of their total. This re-ranks stories that were written; it can't bring back one the published rule dropped."],
      ["official=0", "Leave out government records and statements that no outlet has covered yet."],
      ["blindspots=0", "Leave out stories that only one side ran and that didn't reach your threshold."],
      ["statements=0", "Leave out government statements, such as White House and agency press releases. Records still count."],
      ["spotlight=1", "Only the top " + R.spotlight + " stories each day."],
      ["length=headlines", "Headlines without the bullet points."],
      ["recipe=Morning%20brief", "A name for this setup, up to 60 characters. It labels the page and the feed and changes nothing else."]
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
    var recipes = $("recipe-list");
    recipes.innerHTML = "";
    C.recipes().forEach(function (r) {
      recipes.appendChild(el("li", {}, [el("a", { href: "?" + r.query + "#today", text: r.name }), el("span", { text: r.note })]));
    });
    $("repo-link").href = D.repo_url;
    Array.prototype.forEach.call(document.querySelectorAll(".spot-n"), function (n) { n.textContent = String(R.spotlight); });
  }

  function renderSettingsSummary() {
    var bits = [THRESHOLD_LABELS[prefs.threshold] + " agreement"];
    bits.push(prefs.topics.length ? prefs.topics.map(function (t) { return D.topics[t]; }).join(", ") : "all categories");
    if (prefs.exclude.length) bits.push(plural(prefs.exclude.length, "source", "sources") + " off");
    if (!prefs.official) bits.push("no uncovered government items");
    if (!prefs.blindspots) bits.push("no one-sided stories");
    if (!prefs.statements) bits.push("no government statements");
    if (prefs.weights) bits.push("your own weights");
    if (prefs.length === "headlines") bits.push("headlines only");
    $("settings-summary").textContent = "Now: " + bits.join(", ") + ".";
    $("threshold-hint").textContent = THRESHOLD_HINTS[prefs.threshold] +
      (prefs.weights ? " That describes the published weights; yours can change which stories reach it." : "");
    $("weights-now").textContent = prefs.weights ? "Yours: " + weightWords() + "." : "These are the published weights.";
    $("feed-url").value = C.link(prefs, "/feed.xml");
    $("recipe-link").value = C.link(prefs, "/");
    var note = $("recipe-note");
    note.hidden = !prefs.recipe;
    note.innerHTML = "";
    if (prefs.recipe) {
      note.appendChild(document.createTextNode("Using the recipe \u201c" + prefs.recipe + "\u201d. Whoever made the link chose that name, not Standard Edition. "));
      note.appendChild(el("a", { href: "#your-feed", text: "See its settings" }));
    }
  }

  // ---------- research tools
  var RS = window.BoringCore.research;
  var researchIndex = D.research || null;
  var researchLoading = null;

  function loadResearch() {
    if (researchIndex) return Promise.resolve(researchIndex);
    if (!D.research_url) return Promise.resolve(null);
    if (!researchLoading) {
      researchLoading = fetch(D.research_url).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).then(function (j) { researchIndex = j; return j; }, function (e) { researchLoading = null; throw e; });
    }
    return researchLoading;
  }

  function shortDate(iso) {
    return new Date(iso.slice(0, 10) + "T12:00:00Z").toLocaleDateString("en-US",
      { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  }

  function citation(st) {
    var parts = st.articles.map(function (a) {
      var src = D.sources[a.source_id];
      return (src ? src.name : a.source_id) + ', "' + a.title + '," ' + a.url;
    });
    return '"' + st.headline + '." Standard Edition, ' + shortDate(st.date) + ". Sources: " + parts.join("; ") + ".";
  }

  function copyText(text, button, fallbackBox) {
    function fallback() {
      fallbackBox.hidden = false;
      fallbackBox.textContent = text;
      button.textContent = "Select the text below to copy";
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { button.textContent = "Copied"; }, fallback);
    } else fallback();
  }

  function matchNode(m) {
    var st = m.story;
    var sc = C.score(st.articles.map(function (a) { return a.source_id; }));
    var box = el("article", { className: "match" });
    box.appendChild(el("div", { className: "match-head" }, [
      el("span", { text: shortDate(st.date) + (st.day > 1 ? ", day " + st.day + " of this story" : "") }),
      el("span", { text: m.strength >= 0.75 ? "Close match" : "Possible match" })
    ]));
    box.appendChild(el("h3", { text: st.headline }));

    var meter = el("span", { className: "meter", role: "img", "aria-label": "Covered by " + (listWords(sc.leans) || "no rated outlets") },
      SPECTRUM.map(function (l) { return el("i", { className: sc.leans.indexOf(l) >= 0 ? "on" : "" }); }));
    box.appendChild(el("div", { className: "meta" }, [el("span", { className: "coverage" }, [meter,
      el("span", { text: sc.outlets ? plural(sc.outlets, "outlet", "outlets") + " across " + listWords(sc.leans) : "No news coverage" })])]));

    var groups = el("div", { className: "who-covered" });
    function group(title, arts, note) {
      if (!arts.length) return;
      groups.appendChild(el("div", {}, [el("h4", { text: title }), el("ul", {}, arts.map(function (a) {
        var src = D.sources[a.source_id];
        return el("li", {}, [el("a", { href: a.url, target: "_blank", rel: "noopener", text: a.title }),
          el("span", { text: " (" + (src ? src.name : a.source_id) + (note ? note(src) : "") + ")" })]);
      }))]));
    }
    ["left", "center", "right"].forEach(function (l) {
      group(cap(l), st.articles.filter(function (a) { var s = D.sources[a.source_id]; return s && s.type !== "primary" && s.lean === l; }));
    });
    group("Unrated outlets", st.articles.filter(function (a) { var s = D.sources[a.source_id]; return s && s.type !== "primary" && s.lean === "unrated"; }));
    group("Government", st.articles.filter(function (a) { var s = D.sources[a.source_id]; return s && s.type === "primary"; }),
      function (s) { return s && s.role === "record" ? ", record" : ", statement"; });
    var covered = {};
    st.articles.forEach(function (a) { covered[a.source_id] = true; });
    var missing = Object.keys(D.sources).filter(function (id) {
      var s = D.sources[id]; return s.type !== "primary" && s.lean !== "unrated" && !covered[id];
    }).map(function (id) { return D.sources[id].name; }).sort();
    if (missing.length) groups.appendChild(el("div", {}, [el("h4", { text: "Didn't run it" }), el("p", { className: "empty-note", text: missing.join(", ") })]));
    box.appendChild(groups);

    var cite = el("pre", { className: "formula", hidden: "" });
    var copy = el("button", { type: "button", text: "Copy citation" });
    copy.addEventListener("click", function () { copyText(citation(st), copy, cite); });
    var actions = el("div", { className: "actions" }, [copy]);
    if (st.date === D.edition) actions.appendChild(el("a", { href: "#story-" + st.id, text: "Read the summary" }));
    box.appendChild(actions);
    box.appendChild(cite);
    return box;
  }

  function runLookup() {
    var q = $("lookup-q").value;
    var out = $("lookup-results");
    out.innerHTML = "";
    if (!q.trim()) return;
    out.appendChild(el("p", { className: "empty-note", text: "Searching…" }));
    loadResearch().then(function (idx) {
      out.innerHTML = "";
      var res = RS.lookup(idx, q);
      if (!res.matches.length) {
        out.appendChild(el("p", { className: "empty-note", text: "No coverage found in the last 30 days. That doesn't mean it's false: it may be newer than our latest edition, or covered only by outlets we don't read." }));
        return;
      }
      if (res.how === "link") out.appendChild(el("p", { className: "hint", text: "We read this exact article. Here's the story it belongs to." }));
      res.matches.forEach(function (m) { out.appendChild(matchNode(m)); });
      out.appendChild(el("p", { className: "hint", text: "Matches are found by shared words, so check that each one is really about your claim." }));
    }, function () {
      out.innerHTML = "";
      out.appendChild(el("p", { className: "empty-note", text: "The research data didn't load. Check your connection and try again." }));
    });
  }

  function renderRecords() {
    var list = $("rec-list"), count = $("rec-count");
    loadResearch().then(function (idx) {
      if (!idx) { count.textContent = "Government records appear here once the site is live."; return; }
      var sel = $("rec-source");
      if (sel.options.length === 1) {
        var ids = {};
        idx.records.forEach(function (r) { ids[r.source_id] = true; });
        Object.keys(ids).sort(function (a, b) { return (D.sources[a] || {}).name > (D.sources[b] || {}).name ? 1 : -1; })
          .forEach(function (id) { sel.appendChild(el("option", { value: id, text: D.sources[id] ? D.sources[id].name : id })); });
      }
      var rows = RS.searchRecords(idx, { q: $("rec-q").value, source: sel.value, role: $("rec-role").value, uncovered: $("rec-uncovered").checked });
      count.textContent = plural(rows.length, "item", "items") + " from the last " + plural(idx.days.length, "edition", "editions") + ".";
      list.innerHTML = "";
      rows.slice(0, 100).forEach(function (r) {
        var src = D.sources[r.source_id];
        var summary = r.summary.length > 240 ? r.summary.slice(0, 237).replace(/\s+\S*$/, "") + "…" : r.summary;
        list.appendChild(el("li", {}, [
          el("span", { className: "meta-line" }, [shortDate(r.published_at) + ", " + (src ? src.name : r.source_id),
            el("span", { className: "badge" + (r.role === "record" ? "" : " statement"), text: r.role === "record" ? "Government record" : "Government statement" })]),
          el("a", { className: "rec-title", href: r.url, target: "_blank", rel: "noopener", text: r.title }),
          summary ? el("p", { text: summary }) : null,
          r.outlets ? el("span", { className: "status", text: "Covered by " + plural(r.outlets, "outlet", "outlets") + ": " + r.story_headline })
                    : el("span", { className: "status" }, [el("span", { className: "badge none", text: "No news coverage" })])
        ]));
      });
    }, function () { count.textContent = "The records didn't load. Check your connection and try again."; });
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
    if (h === "research") renderRecords();
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
  function copyField(buttonId, inputId, statusId) {
    $(buttonId).addEventListener("click", function () {
      var input = $(inputId), status = $(statusId);
      function fallback() { input.focus(); input.select(); status.textContent = "Selected. Press Ctrl+C or Cmd+C to copy."; }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(input.value).then(function () { status.textContent = "Copied."; }, fallback);
      } else fallback();
    });
  }
  copyField("copy-feed", "feed-url", "copy-status");
  copyField("copy-recipe", "recipe-link", "recipe-status");
  $("recipe-name").addEventListener("input", function () {
    prefs.recipe = C.cleanName(this.value);
    update();
  });
  window.addEventListener("hashchange", route);
  $("lookup-form").addEventListener("submit", function (e) { e.preventDefault(); runLookup(); });
  ["rec-q", "rec-source", "rec-role", "rec-uncovered"].forEach(function (id) {
    $(id).addEventListener(id === "rec-q" ? "input" : "change", renderRecords);
  });
  if (D.research_url) $("research-file").href = D.research_url;

  $("dateline").textContent = longDate(D.edition);
  $("sample-note").hidden = !D.sample;
  renderTicker();
  renderControls();
  renderDocs();
  renderOutlets();
  update();
  route();
})();
