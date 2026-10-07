# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately, and we'll work with you on a fix and coordinated disclosure:

- **Preferred:** GitHub → the repository's **Security** tab → **Report a vulnerability**
  (private GitHub Security Advisory).
- **Alternatively:** email **contact@lightshieldsiem.in**.

Please include: affected version, a description, reproduction steps, and the
impact you observed. We aim to acknowledge within **3 business days** and to
provide a remediation timeline after triage.

## Supported versions

Security fixes are provided for the **latest released minor version**. Please
upgrade to the latest version before reporting.

## Security model & safe use

qa-probe runs against *your own* applications with credentials *you* supply.
A few properties to be aware of:

- **Config is executed as JavaScript.** `qa-probe.config.js` is loaded with
  `require()` (same as ESLint/Jest/Vite). Only run qa-probe with a config you
  trust.
- **Credentials stay local.** Auth tokens are held in memory for the run and are
  not written to any report file. Use environment variables — never hardcode
  secrets in your config.
- **`probe.ignoreHTTPSErrors: true` disables TLS verification.** Dev/staging
  only — never against production.
- **Write-flows mutate data.** `writeFlows` is **off by default**; when enabled
  it issues create/update/delete requests and cleans up after itself. Run it
  against a disposable / test-tenant environment only.
- **Security checks re-probe GET endpoints only** (auth-bypass, PII, persona
  matrix) — they never issue a write.
- **MCP output is sanitized.** SQL errors, stack traces, and table names are
  redacted before reaching an AI client; raw data stays on disk.

## Scope

In scope: vulnerabilities in qa-probe itself (e.g. credential leakage into
reports, command injection via config/inputs, unsafe handling of probed
responses). Out of scope: vulnerabilities in the applications you point qa-probe
at (that's what it helps you find), and issues that require running an untrusted
config.
