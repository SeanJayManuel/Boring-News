// Runs web/core.js for the tests. Reads {"data", "queries", "scores"} on stdin.
require("../web/core.js");
let input = "";
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  const { data, queries = [], scores = [] } = JSON.parse(input);
  const C = globalThis.BoringCore.create(data);
  console.log(JSON.stringify({
    selections: queries.map((q) => {
      const p = C.fromQuery("?" + q);
      const res = C.select(p);
      return {
        query: C.toQuery(p),
        items: (p.spotlight ? C.spotlight(res.shown) : res.shown).map((x) => ({
          id: x.story.id, topic: x.story.topic, headline: x.story.headline, lane: x.lane, why: x.why,
          total: x.score.total, leans: x.score.leans, hasStatement: x.score.hasStatement,
        })),
      };
    }),
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
