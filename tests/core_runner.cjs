// Runs web/core.js for the tests. Reads {"data", "queries", "scores", "index", "threads"} on stdin.
require("../web/core.js");
let input = "";
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  const { data, queries = [], scores = [], index = null, threads = [] } = JSON.parse(input);
  const C = globalThis.BoringCore.create(data);
  console.log(JSON.stringify({
    selections: queries.map((q) => {
      const p = C.fromQuery("?" + q);
      const res = C.select(p);
      return {
        query: C.toQuery(p),
        items: (p.spotlight ? C.spotlight(res.shown) : res.shown).map((x) => ({
          id: x.story.id, topic: x.story.topic, headline: x.story.headline, lane: x.lane, why: x.why,
          total: x.score.total, leans: x.score.leans, hasStatement: x.score.hasStatement, points: x.score.points,
        })),
        order: res.shown.map((x) => x.story.id),
        hidden: res.hidden,
        filtered: res.filtered.map((x) => ({ id: x.story.id, reason: x.reason, why: x.why })),
        rss: C.rss(p, data.base_url),
      };
    }),
    recipes: C.recipes(),
    reasons: globalThis.BoringCore.REASONS,
    threads: threads.map(([date, id]) => globalThis.BoringCore.research.earlier(index, date, id)),
    scores: scores.map((ids) => {
      const sc = C.score(ids);
      sc.lanes = {};
      for (const threshold of Object.keys(data.rubric.thresholds)) {
        sc.lanes[threshold] = [C.lane(sc, { threshold, official: true }), C.lane(sc, { threshold, official: false })];
      }
      return sc;
    }),
  }));
});
