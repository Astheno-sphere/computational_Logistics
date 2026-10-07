// Cloudflare Worker entry — the hosted edge endpoint (free tier, 100k req/day).
// Web-standard fetch handler over the same stateless JSON-RPC core as stdio.
// Deploy with `wrangler deploy`; the MCP endpoint is POST /mcp.
//
// NOTE: the bundled dataset is inlined into the Worker. The illustrative sample
// bundles fine; the FULL England dataset (~1.6M postcodes) exceeds the Worker
// bundle size limit, so the hosted edge build should move the data into
// Cloudflare D1/KV (a follow-on). The npm library + stdio server have no such
// limit and run the full dataset directly.
import { handleRpc } from "./core.js";

const LOGO_SVG =
  '<svg width="512" height="512" viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg" aria-label="Qiniso">' +
  '<defs><linearGradient id="e" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#10b981"/><stop offset="1" stop-color="#047857"/></linearGradient></defs>' +
  '<rect x="16" y="16" width="480" height="480" rx="112" fill="url(#e)"/>' +
  '<circle cx="248" cy="248" r="118" fill="none" stroke="#fff" stroke-width="40"/>' +
  '<path d="M250 300 L300 360 L412 196" fill="none" stroke="#fff" stroke-width="40" stroke-linecap="round" stroke-linejoin="round"/></svg>';

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

    if (request.method === "GET" && url.pathname === "/health") return json({ status: "ok" });
    if (request.method === "GET" && (url.pathname === "/icon.svg" || url.pathname === "/favicon.ico")) {
      return new Response(LOGO_SVG, {
        headers: { "content-type": "image/svg+xml", "cache-control": "public, max-age=86400" },
      });
    }
    if (request.method === "GET" && url.pathname === "/") {
      return json({
        name: "floodwise",
        description: "Verified England flood-risk-by-postcode lookups for AI agents (Environment Agency, OGL).",
        mcp: "/mcp",
        icon: "/icon.svg",
        docs: "https://qinisolabs.github.io/floodwise",
      });
    }
    if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

    let payload: any;
    try {
      payload = await request.json();
    } catch {
      return json({ error: "invalid json" }, 400);
    }
    if (Array.isArray(payload)) {
      const out = payload.map(handleRpc).filter(Boolean);
      return json(out);
    }
    const r = handleRpc(payload);
    if (r === null) return new Response(null, { status: 202 });
    return json(r);
  },
};
