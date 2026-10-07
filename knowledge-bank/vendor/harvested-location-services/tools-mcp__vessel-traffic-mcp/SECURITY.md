# Security Policy

`vessel-traffic-mcp` is a read-only MCP server that brokers authorized
vessel/AIS data sources. Because it sits in front of user credentials
(BYOK) and authorized capture fixtures, this project treats credential
hygiene and least-privilege access as first-class security requirements.

This policy covers F7.AC1.

## Supported Versions

This project is pre-1.0. Security fixes are made against the default
branch (`main`); there are no long-lived release branches yet.

| Version | Supported          |
| ------- | ------------------ |
| `0.x`   | :white_check_mark: |

## Reporting a Vulnerability

**Do not open a public GitHub issue for a suspected vulnerability.**

Please report privately through one of the following channels:

- Preferred: email `smgu@futhing.com` with the subject line
  `vessel-traffic-mcp security: <short summary>`.
- Alternatively, use GitHub's
  [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
  on the project repository if the repository has it enabled.

When reporting, include:

1. A description of the issue and the impact you observed.
2. Reproduction steps (configuration, transport, provider, command).
3. Affected commit SHA or version, and the platform you ran on.
4. Whether you believe the issue is exploitable without operator
   authorization (e.g., missing auth on `/mcp`, log leakage of raw
   credentials, sanitized-fixture bypass) versus a hardening request.

Please **do not** include real API keys, bearer tokens, cookies, raw HAR
files, or private capture sessions in the report. Redact them first;
the project's redaction CLI (`npm run capture:import`) can help. We will
ask for additional details if needed.

You should expect:

- An acknowledgement within **5 business days**.
- A triage update within **10 business days** of acknowledgement.
- A fix or documented mitigation tracked through a private branch or
  draft advisory. Coordinated disclosure timing is negotiable and
  defaults to publishing the advisory and patch together.

## In Scope

The following classes of issue are explicitly in scope:

- Credential leakage in logs, error responses, MCP tool output, or
  committed files (raw API keys, bearer tokens, cookies, request bodies,
  query strings, HAR fragments).
- Authentication or authorization bypass on the Streamable HTTP MCP
  endpoint (`/mcp` accepting unauthenticated requests when
  `VESSEL_MCP_AUTH_TOKEN` is set, header parsing weaknesses,
  request-smuggling, header injection through `X-Request-Id`).
- MCP tools performing write operations against any provider account,
  fleet, billing setting, saved search, or user profile — this server
  must remain strictly read-only.
- Capture-fixture importer failing to redact sensitive headers,
  cookies, tokens, query parameters, or body fields before writing
  sanitized fixtures.
- BYOK profile loader exposing raw keys (e.g., via `credential_profiles`
  MCP responses, log lines, or error messages) instead of profile
  labels and status only.
- Provider router bypass that calls paid/live providers from default
  verification (`npm run lint`, `npm test`, `npm run build`) without the
  documented `VESSEL_MCP_LIVE_TEST_*` opt-in.
- Path traversal, prototype pollution, deserialization, command
  injection, SSRF, and similar standard server-side vulnerabilities in
  the MCP server or its CLIs.

## Out of Scope

- Vulnerabilities in third-party AIS providers, their websites, or
  their APIs themselves. Report those to the upstream provider.
- Issues that require an attacker who already controls the operator's
  shell or the local filesystem holding `config/credential-profiles.local.json`.
- Reports based on AIS data accuracy, position freshness, or coverage
  gaps. The project documents missing/stale data as valid states; it is
  not a navigation-safety product.
- Reports requesting that the project bypass authentication, paywalls,
  CAPTCHA, bot defenses, rate limits, or access controls of any
  provider. Those requests are explicitly forbidden by the project's
  hard rules in `AGENTS.md`.
- Denial-of-service findings that require unrealistic request volume,
  network position, or destructive setup.

## Safe-Harbor Expectations

If you act in good faith — only against your own deployment or a test
deployment, do not exfiltrate other operators' data, do not violate any
third-party provider's terms of service, give us reasonable time to
investigate and patch before disclosure, and follow this policy — we
will not pursue or support legal action related to your report.

## Hardening Defaults (for operators)

When self-hosting:

- Keep `.env`, `*.env.*`, `*.har`, `captures/raw/`, `captures/private/`,
  `state/`, and `config/credential-profiles*.local.json` out of git.
  The committed `.gitignore` enforces this; verify it on every fork.
- Run the Streamable HTTP transport behind HTTPS. Set
  `VESSEL_MCP_AUTH_TOKEN` to a strong random value and require
  `Authorization: Bearer <token>` on `/mcp`. `/health` may stay public.
- Treat `VESSEL_MCP_LIVE_TEST_*` flags as production-only opt-ins. Do
  not enable them in CI by default.
- See `docs/runbooks/operator.md` and `docs/runbooks/release-checklist.md`
  for the full secret-safety checklist before each release.
