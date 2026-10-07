# Contributing to Ambee MCP Server

Thanks for your interest in improving the Ambee MCP server! This project is maintained by the Ambee team, and community contributions are welcome.

## Before you start

- For small fixes (typos, docs, minor bugs), feel free to open a PR directly.
- For larger changes (new tools, new transports, breaking changes to existing tool schemas), please open an issue first to discuss the approach before writing code — this saves you from doing work that might not fit the project's direction.

## Development setup

```bash
git clone https://github.com/getambee/ambee-mcp-server.git
cd ambee-mcp-server
npm install
export AMBEE_API_KEY="your-ambee-api-key"
npm start
```

To test your changes against a real MCP client without building a full integration, use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector node src/index.js -e AMBEE_API_KEY=your-ambee-api-key
```

This opens a local web UI where you can call each tool and inspect raw responses. For a quick non-interactive check (e.g. in a script), use `--cli`:

```bash
npx @modelcontextprotocol/inspector --cli node src/index.js -e AMBEE_API_KEY=your-ambee-api-key --method tools/list
```

## Making changes

1. **Fork** the repository and create a branch off `main`:
   ```bash
   git checkout -b my-feature
   ```
2. **Keep tools consistent with the Ambee API.** If you're adding or changing a tool, cross-check the parameter names, types, and defaults against Ambee's OpenAPI spec (`docs.ambeedata.com/apis`) so the tool description and schema stay accurate.
3. **Handle errors, don't just throw.** Every network call should surface Ambee's documented status codes (see the [error handling table](README.md#error-handling) in the README) as a clear MCP tool error rather than an unhandled exception.
4. **Update the README** if you add, remove, or change a tool's parameters or behavior.
5. **Test locally** with the Inspector or a real MCP client (Claude Desktop, Claude Code, Cursor, etc.) before opening a PR — include what you tested in the PR description.

## Commit messages

Use clear, imperative commit messages, e.g. `Add historical air quality tool`, not `updates`.

## Pull requests

1. Push your branch and open a PR against `main`.
2. Fill in the PR template — what changed, why, and how you tested it.
3. A maintainer will review; expect feedback or requested changes on larger PRs.
4. Once approved, a maintainer will merge.

## Reporting bugs

Please use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:
- Node.js version
- MCP client you're using (Claude Desktop, Cursor, etc.)
- The exact tool call and arguments that failed
- The error message returned (redact your API key if it appears anywhere)

## Reporting security issues

Please **do not** open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) instead.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be respectful and constructive.
