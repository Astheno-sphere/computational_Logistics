# MCP capability documentation contract

This contract defines the public pages for methods exposed by an MCP server to AI clients. The canonical directory is `docs/capabilities/`; the neutral name works for repositories that publish skills, tools, or other user-facing capabilities.

## When it applies

When a registered MCP tool is added, renamed, or removed, update its page, the catalog index, and the coverage test in the same PR. The work is complete when every tool has exactly one page, its impact matches the runtime annotations, and every local link resolves.

## How to write a page

1. Name the page after the user's task and use the exact category “MCP tool” in the H1 and opening sentence.
2. State the desired transition once as `> I want to + infinitive`. The methodology helps the author isolate the task and expected outcome; the public copy stays in the user's ordinary language.
3. Explain when to use the tool, required inputs, result, limits, and exact data impact.
4. Keep reads, changes, and destructive operations distinct. Creation, confirmation, publishing, money movement, cancellation, and deletion must not look like reads.
5. Verify claims in this order: tool registration and runtime annotations → client and tests → `docs/TOOLS.md` → README. Leave unsupported promises out.

## Required sections

- What task it solves
- When to use it
- What to provide
- What it returns
- What changes in the product
- Example request
- Errors and limitations
- Related MCP tools
- Technical details

## Web publishing

Markdown in `docs/capabilities/` is the single content source: HTML is rendered from it without a parallel copy. The website template adds any call to action after the substantive content instead of embedding it in Markdown. For every HTML page, the web layer exposes an equivalent `.md` route, advertises it with `Link: rel="alternate"; type="text/markdown"`, and supports `Accept: text/markdown` with correct q-value comparison. Both representations return `Vary: Accept` and reciprocal `Link` headers; representation selection never relies on User-Agent sniffing.

The site index and `llms.txt` should link to this catalog as a curated collection instead of duplicating page text. Search engines, people, and AI clients then receive the same material without drift.
