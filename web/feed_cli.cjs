// Builds RSS feeds with web/core.js for Python (boringnews/reader.py).
// Reads {"data": <page data>, "queries": ["topics=economy", ...]} on stdin and
// prints one feed per query as a JSON list.
require("./core.js");
let input = "";
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  const { data, queries } = JSON.parse(input);
  const core = globalThis.BoringCore.create(data);
  console.log(JSON.stringify(queries.map((q) => core.rss(core.fromQuery("?" + q), data.base_url))));
});
