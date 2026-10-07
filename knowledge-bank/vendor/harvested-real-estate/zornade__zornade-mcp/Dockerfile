# ─────────────────────────────────────────────────────────────────────────────
# Zornade MCP server - container image
#
# Esegue la Supabase Edge Function `mcp` come server HTTP standalone (Deno).
# Usata da Glama per gli automated safety/quality checks della listing:
# il container espone l'endpoint MCP (streamable HTTP) sulla porta 8000.
# ─────────────────────────────────────────────────────────────────────────────

FROM denoland/deno:2.4.1

WORKDIR /app

# Solo il sorgente della funzione: le dipendenze sono dichiarate inline
# con specifier npm: versionati (nessun lockfile esterno necessario).
COPY functions/mcp/index.ts .
COPY healthcheck.ts .

# Pre-scarica le dipendenze nell'immagine (hono, mcp-lite, zod):
# a runtime non serve accesso alla rete verso registry npm.
RUN deno cache index.ts

# Porta su cui Deno.serve ascolta di default (0.0.0.0:8000).
EXPOSE 8000

# Healthcheck contro la rotta informativa di Hono (JSON).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD ["deno", "run", "--allow-net", "healthcheck.ts"]

# Utente non-root (presente nell'immagine ufficiale).
USER deno

CMD ["run", "--allow-net", "--allow-env", "index.ts"]
