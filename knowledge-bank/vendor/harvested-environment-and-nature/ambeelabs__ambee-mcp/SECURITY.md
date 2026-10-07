# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in this repository, please **do not** open a public GitHub issue.

Instead, report it privately via [support.getambee.com](https://support.getambee.com) or GitHub's [private vulnerability reporting](https://github.com/getambee/ambee-mcp-server/security/advisories/new) feature (Security tab → Report a vulnerability).

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any relevant logs or proof-of-concept code (with your API key redacted)

We aim to acknowledge reports within a few business days.

## Supported versions

Only the latest release on the `main` branch is actively supported with security fixes.

## Handling your Ambee API key

This server never logs, stores, or transmits your `AMBEE_API_KEY` anywhere other than as the `x-api-key` header on requests to `api.ambeedata.com`. Even so:

- Never commit your key to version control. `.env` is already excluded via `.gitignore`.
- Prefer environment variables or your MCP client's secret-storage mechanism over hardcoding the key in a config file.
- MCP client configuration files (`claude_desktop_config.json`, `~/.cursor/mcp.json`, `.vscode/mcp.json`, etc.) are typically stored in plain text on disk — keep them out of shared or synced locations you don't control.
- If you suspect your key has been exposed, regenerate it immediately from the [Ambee API dashboard](https://api-dashboard.getambee.com) or contact [support](https://support.getambee.com).
