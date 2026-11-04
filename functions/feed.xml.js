// Cloudflare Pages Function: serves /feed.xml with the reader's settings.
//
// The site itself is static. This function reads today's edition
// (/edition.json, written by `python -m boringnews.export_static`) and builds
// the RSS feed for whatever settings are in the address, using the same
// rubric code as the web page (web/core.js). Free tier: 100,000 requests a day.
import "../web/core.js";

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const edition = await env.ASSETS.fetch(new URL("/edition.json", url.origin));
  if (!edition.ok) {
    return new Response("No edition has been published yet.", { status: 503 });
  }
  const data = await edition.json();
  const core = globalThis.BoringCore.create(data);
  const prefs = core.fromQuery(url.search);
  const xml = core.rss(prefs, data.base_url || url.origin);
  return new Response(xml, {
    headers: {
      "content-type": "application/rss+xml; charset=utf-8",
      "cache-control": "public, max-age=900",
    },
  });
}
