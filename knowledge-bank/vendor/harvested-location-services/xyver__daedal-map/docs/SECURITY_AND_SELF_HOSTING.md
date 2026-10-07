# Security And Self-Hosting

The public runtime can operate without DaedalMap's private account or business
systems. Self-hosters are responsible for the trust boundary around their own
instance, data, model providers, and storage.

## Secrets

Keep these server-side:

- model API keys;
- object-storage credentials;
- database or analytics credentials;
- internal bridge tokens;
- signing or payment keys;
- partner/private MCP credentials.

Do not commit `.env`, credential files, raw tokens, or private keys. Do not add
server secrets to browser configuration.

## Data trust

Imported data can affect:

- generated SQL and filtering;
- model context;
- map labels and descriptions;
- links shown to users;
- browser storage and downloadable artifacts.

Treat source text as untrusted input:

- preserve provenance;
- validate schemas and types;
- sanitize prompt-facing text;
- avoid executable HTML in labels or metadata;
- review URLs before presenting them;
- keep raw archives outside the served runtime tree.

## Network exposure

A local development server should not be exposed publicly without:

- a production ASGI deployment;
- TLS termination;
- authentication or network controls where appropriate;
- request/body limits;
- rate limiting;
- logging and monitoring;
- explicit CORS and proxy configuration.

Debug, cache-clear, admin, and local-wrapper routes deserve particular review
before internet exposure.

## Model providers

Prompts and selected source material may be sent to the configured model
provider. Researchers handling restricted or sensitive data should review
provider retention terms or use an approved local/provider deployment.

Deterministic data execution does not remove the need to understand what enters
model context.

## Object storage

Use least-privilege credentials and separate public-readable artifacts from
write-capable or operator-only storage.

Do not assume a public object URL makes all neighboring keys safe to expose.
Catalogs and manifests should reference only intended runtime artifacts.

## Packs and artifacts

Before sharing a pack:

- verify its license permits redistribution;
- remove credentials, local paths, and raw restricted inputs;
- include provenance and limitations;
- inspect metadata and browser artifacts for sensitive text;
- provide checksums for large files when practical.

## Hosted bridges

Optional hosted-control-plane bridges must fail clearly when not configured.
Public local operation should not silently depend on them.

If you add a bridge:

- name the boundary explicitly;
- authenticate server to server;
- define timeout and failure behavior;
- avoid exposing internal tokens to the browser;
- test the self-host fallback.

## Reporting

Use the repository's published security contact or `security.txt` endpoint for
responsible vulnerability reporting. Do not include live secrets or sensitive
personal data in a public issue.

