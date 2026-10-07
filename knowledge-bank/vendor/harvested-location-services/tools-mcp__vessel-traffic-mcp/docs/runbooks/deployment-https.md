# Deploying the Streamable HTTP MCP endpoint behind HTTPS (F6.AC2)

This runbook is the operator-facing guide for hosting
`vessel-traffic-mcp`'s Streamable HTTP transport (`POST /mcp`,
`GET/DELETE/OPTIONS /mcp`, plus public `GET/HEAD /health` and
`GET/HEAD /.well-known/mcp/server-card.json`) on a public network. It
covers the supplied `Dockerfile`, the `.dockerignore` boundary, and
three concrete HTTPS-termination topologies that satisfy the hard rule:
the container itself only speaks HTTP, and TLS is always terminated by
a trusted reverse proxy, load balancer, or platform edge in front of it.

Cross-reference runbooks:

- `docs/runbooks/streamable-http-server.md` — endpoints, bearer-token
  auth, request IDs, and observability for the HTTP transport.
- `docs/runbooks/operator.md` — provider credentials, rate limits,
  live-test toggles, and client setup.
- `docs/runbooks/credential-profiles.md` — BYOK env vars and the
  gitignored local profile overlay.

## Current distribution decision

As of 2026-08-24, the maintainers distribute this project as public source and
an npm package, but **do not operate a shared public HTTPS `/mcp` endpoint**.
The Streamable HTTP implementation is for an operator-owned deployment that
has its own domain, bearer-token secret, provider permissions, rate-limit
plan, and incident owner.

Do not represent the local server-card route or these deployment examples as a
public remote connector. A directory listing or client integration may name a
remote URL only after that operator has deployed it behind HTTPS, verified
`/health` and authenticated `/mcp`, and accepted the associated provider and
operational responsibilities. Until then, local stdio is the supported
installation path for ordinary users.

## Hard rules (must hold for every deployment)

- **HTTPS is non-negotiable for any non-loopback bind.** Do not expose
  `/mcp` over plaintext HTTP outside `127.0.0.1`. The container binds
  HTTP on `0.0.0.0` only so a reverse proxy on the same host or
  platform mesh can talk to it; the public listener must be HTTPS.
- **Bearer token on `/mcp`.** Set `VESSEL_MCP_AUTH_TOKEN` to a strong
  random value (32+ bytes of entropy). Clients must send
  `Authorization: Bearer <token>` on every `/mcp` request. `/health`
  stays public so the load balancer can probe without credentials.
- **Read-only contract.** The MCP tools shipped on this server are
  read-only. Do not add a deployment-side proxy that rewrites
  requests, adds provider write actions, or strips bearer
  enforcement.
- **No secrets in the image.** The `Dockerfile` and `.dockerignore`
  exclude `.env*`, `config/credential-profiles*.local.json`, raw
  captures, HAR files, logs, and `state/` from the build context.
  Inject BYOK credentials at runtime through the deployment secret
  manager, never bake them into a layer.
- **Default verification stays free.** `npm run lint`, `npm test`, and
  `npm run build` must not run `docker build` or call paid/live
  providers. The deterministic verification for this runbook is
  file-only.

## What ships in the container

The `Dockerfile` at the repository root is a two-stage build:

1. **Build stage** (`node:22-bookworm-slim`): copies `package.json`,
   `package-lock.json`, `tsconfig.json`, and `src/`, runs
   `npm ci` for a reproducible install, compiles TypeScript with
   `npm run build`, then runs `npm prune --omit=dev` so the runtime
   stage only carries production dependencies.
2. **Runtime stage** (`node:22-bookworm-slim`): copies `package.json`,
   the pruned `node_modules`, and `dist/`. Drops to the unprivileged
   built-in `node` user, exposes port `3000`, and starts the HTTP
   transport via `ENTRYPOINT ["node", "--enable-source-maps", "dist/index.js"]`.

Default container environment:

| Variable | Default | Purpose |
| --- | --- | --- |
| `NODE_ENV` | `production` | Standard Node production mode. |
| `VESSEL_MCP_TRANSPORT` | `http` | Selects the Streamable HTTP transport. |
| `VESSEL_MCP_HTTP_HOST` | `0.0.0.0` | Bind inside the container so the host reverse proxy can reach it. The public surface is HTTPS, never this bind. |
| `VESSEL_MCP_HTTP_PORT` | `3000` | In-container port. Map to whatever your platform expects. |
| `VESSEL_MCP_AUTH_TOKEN` | _unset_ | **Required for any non-loopback deployment.** Inject through the deployment secret store. |

The image also declares a Docker `HEALTHCHECK` that calls the in-process
`/health` endpoint; it does not require the bearer token and never
exposes provider credential state.

## Build and run

`docker build` is **operator-only**. It is intentionally not part of
default CI (which would slow `npm test` and require Docker). Run it
locally or from your image pipeline:

```sh
docker build -t vessel-traffic-mcp:local .
```

Run the container locally for a smoke test (still HTTP-only on
loopback — do not publish this port to the public internet):

```sh
docker run --rm \
  -p 127.0.0.1:3000:3000 \
  -e VESSEL_MCP_AUTH_TOKEN="$(openssl rand -hex 32)" \
  vessel-traffic-mcp:local
```

Health probe (no bearer required):

```sh
curl -sf http://127.0.0.1:3000/health
```

Directory metadata probe (no bearer required):

```sh
curl -sf http://127.0.0.1:3000/.well-known/mcp/server-card.json
```

MCP probe (bearer required when `VESSEL_MCP_AUTH_TOKEN` is set):

```sh
curl -sf -X POST http://127.0.0.1:3000/mcp \
  -H "Authorization: Bearer <the-token-you-injected>" \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Never paste the real token into shell history that is checked into
version control or shared chat. Source it from your secret manager.

## HTTPS termination topologies

Pick one. In every option, the container keeps its HTTP listener bound
to the proxy (`0.0.0.0` inside the container, or a private network),
and the public listener is HTTPS only.

### Option A: nginx reverse proxy

`/etc/nginx/sites-available/vessel-traffic-mcp` (sketch — adapt to your
nginx layout and certificate source, e.g. Let's Encrypt via certbot):

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.example.com;

    # Use certificates managed by your ACME client or platform.
    ssl_certificate     /etc/letsencrypt/live/mcp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.example.com/privkey.pem;
    # Modern TLS profile; do not enable TLS 1.0/1.1.
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    # Public health probe — keep cheap and unauthenticated.
    location = /health {
        proxy_pass http://127.0.0.1:3000/health;
        proxy_set_header Host $host;
    }

    # Public MCP directory metadata — no bearer token required.
    location = /.well-known/mcp/server-card.json {
        proxy_pass http://127.0.0.1:3000/.well-known/mcp/server-card.json;
        proxy_set_header Host $host;
    }

    # MCP surface — Streamable HTTP supports POST/GET/DELETE/OPTIONS.
    location /mcp {
        proxy_pass http://127.0.0.1:3000/mcp;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
        proxy_buffering off;        # streaming responses
        proxy_read_timeout 1h;      # long-lived sessions
    }
}

server {
    listen 80;
    server_name mcp.example.com;
    return 301 https://$host$request_uri;
}
```

Operator notes:

- Strip any inbound `Authorization` from clients that should not pass
  through (if you front the proxy with a separate auth layer); the MCP
  server compares the bearer with a constant-time check, so passing a
  bad token returns `401` without leaking the configured value.
- Do not enable nginx `access_log` with `$http_authorization` in the
  format. The application logs already redact bearer tokens via
  `redactForLog`; mirror that on the proxy.

### Option B: Caddy reverse proxy

Caddy issues and renews certificates automatically. A minimal
`Caddyfile`:

```caddy
mcp.example.com {
    encode zstd gzip

    @health path /health
    handle @health {
        reverse_proxy 127.0.0.1:3000
    }

    @serverCard path /.well-known/mcp/server-card.json
    handle @serverCard {
        reverse_proxy 127.0.0.1:3000
    }

    @mcp path /mcp /mcp/*
    handle @mcp {
        reverse_proxy 127.0.0.1:3000 {
            flush_interval -1
            transport http {
                read_timeout 1h
            }
        }
    }

    handle {
        respond 404
    }

    log {
        # Do not log Authorization headers.
        format json
    }
}
```

Operator notes:

- `flush_interval -1` keeps Streamable HTTP responses unbuffered.
- Caddy's automatic HTTPS only works for a real public DNS name. For
  local smoke tests use `localhost` with the internal CA, or stick to
  Option A with self-signed certs.

### Option C: Managed platform HTTPS edge

For Cloud Run, Fly.io, AWS App Runner, Render, Railway, and similar
platforms, the platform terminates TLS for you. Configuration
checklist:

- Listen port: set `VESSEL_MCP_HTTP_PORT` to whatever the platform
  injects (Cloud Run sets `PORT`; map it: `VESSEL_MCP_HTTP_PORT=$PORT`).
- Bind: `VESSEL_MCP_HTTP_HOST=0.0.0.0`. The platform's edge proxies
  reach the container over its private network; the public listener
  is HTTPS only.
- Secrets: inject `VESSEL_MCP_AUTH_TOKEN` (and any
  `VESSEL_MCP_PROFILE_*__*` BYOK env vars) through the platform's
  secret manager. Do not embed them in environment variables that
  show up in the platform UI as plain text or in CI logs.
- Health check: point the platform liveness/readiness probe at
  `/health`. The Docker `HEALTHCHECK` in the image also works on
  hosts that honour it.
- Directory metadata: expose
  `/.well-known/mcp/server-card.json` through the same HTTPS edge so
  MCP directories can inspect tool/package metadata without receiving
  provider credentials or bearer-token material.
- Concurrency: this server is stateless across requests for
  fixture-backed tools; horizontal scaling is safe. When live
  providers are added, ensure their `RateLimitPolicy` `scope`
  (`per-credential`, `per-instance`, `global`) is compatible with
  the number of instances.

## Token rotation and revocation

`VESSEL_MCP_AUTH_TOKEN` is a single shared secret per deployment. To
rotate:

1. Generate a new token (`openssl rand -hex 32`).
2. Update the secret in the deployment secret manager.
3. Trigger a rolling restart (the value is read at process startup;
   the server does not reload on SIGHUP).
4. Update each MCP client (Claude remote MCP connector, ChatGPT
   connector, internal tooling) to use the new bearer.
5. Confirm the old token returns `401` on `/mcp` after the rollout
   completes.

If a token leaks, treat it like any other credential incident: rotate
immediately, audit the `X-Request-Id` correlation logs (stderr JSON)
for unauthorized calls, and consider rotating provider BYOK keys if
the same operator stored both in the same place.

## Secret-safety verification before each deploy

Before pushing an image:

- `git status` clean — no `.env`, `*.har`, raw capture files, or
  `config/credential-profiles*.local.json` accidentally staged.
- `grep -RIn "Bearer " --include='*.yaml' --include='*.yml' --include='*.json' .`
  returns only placeholder strings, never a real token.
- `docker build .` succeeds with the supplied `.dockerignore` so the
  build context excludes the secret/capture surfaces. (The `.gitignore`
  and `.dockerignore` both enforce this; verifying that both files
  list the same surfaces is part of the deterministic test for this
  runbook.)
- `docker image inspect vessel-traffic-mcp:local` shows
  `Config.User: "node"` (non-root) and `Config.ExposedPorts` includes
  `3000/tcp`.

## Verification

Run from the project root:

```sh
npm run lint
npm test
npm run build
```

The deterministic test `test/deployment-https.test.js` reads file
contents only and asserts that:

- the `Dockerfile` is a multi-stage build on `node:22-*`, runs as the
  unprivileged `node` user, exposes port `3000`, defaults to the HTTP
  transport, and never copies `.env*`, raw captures, or local
  credential overlays;
- `.dockerignore` excludes secrets, captures, logs, and local
  credential profiles so the build context cannot leak them;
- this runbook documents the HTTPS-termination contract, the bearer
  token, and at least one reverse-proxy or platform topology;
- the README links this runbook;
- `requirements.yaml` F6.AC2 is set to `status: implemented` with the
  `npm run build` verification mode the brief requires.

`npm run build` does not invoke `docker build`. Building the image is
an operator/CI-pipeline concern, kept out of default verification so
contributors without Docker can still pass the gate.

Default verification does not call any paid or live vessel-data
provider; everything above is checked from local file contents only.
