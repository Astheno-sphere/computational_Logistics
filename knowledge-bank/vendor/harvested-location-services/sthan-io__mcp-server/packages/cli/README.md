# @sthan/cli

Command-line tool for [sthan.io](https://sthan.io) — verify, parse, and geocode US addresses from your terminal, scripts, CI, or any AI agent.

One binary handles single lookups and batch files (CSV/Excel), so AI coding agents can run it directly instead of looping per row.

## Install

```bash
npm install -g @sthan/cli
# or run without installing:
npx @sthan/cli verify "1600 Pennsylvania Ave NW, Washington, DC 20500"
```

## Quickstart

```bash
# 1. Sign up at https://sthan.io (free tier, no credit card) and create an
#    API key from your dashboard: https://sthan.io/dashboard
# 2. Save it locally:
sthan login --api-key sthan_test_your_api_key_here

# 3. Verify an address:
sthan verify "123 Main St, New York, NY 10001"
```

```
123 Main St, New York, NY 10001-1234
✓ deliverable
  ZIP+4: 10001-1234
  DPV: Y
  Deliverable status: Confirmed
```

## Commands

| Command | Description |
|---------|-------------|
| `sthan login --api-key <key>` | Save your API key to `~/.sthan/credentials.json` |
| `sthan whoami` | Show the API key in use (masked) and its source |
| `sthan verify <address>` | Verify a US address — single, or batch with `--input` |
| `sthan parse <address>` | Parse a freeform address into structured components |
| `sthan geocode <address>` | Address → coordinates (use `-r lat,lon` for reverse) |
| `sthan ip <ip>` | Geolocate an IPv4 or IPv6 address |

Every data command prints a human-readable summary by default; add `--json` for the raw response.

## Batch file processing

Verify a whole file in one command — file parsing, throttling, and output are all handled for you:

```bash
sthan verify --input addresses.csv  --output results.csv
sthan verify -i customers.xlsx      -o results.xlsx
sthan verify -i data.csv -o out.csv --column "mailing_address"
sthan verify -i data.csv -o out.csv --concurrency 20
```

- **Input formats:** `.csv`, `.tsv`, `.xlsx`, or plain `.txt` (one address per line).
- **Output formats:** `.csv` or `.xlsx` (chosen by the output file's extension).
- **Address column:** auto-detected (`address`, `full_address`, `addr`, …) or set it with `--column`.
- **Output rows:** your original columns are preserved, with these appended:
  `standardized_address`, `dpv`, `deliverable_status`, `zip4`, `confidence`, `error`.
- Requests run with bounded concurrency (default 10) and automatic backoff if rate limited. Each address counts as one API call.

## Authentication

The API key is resolved in this order:

1. `--api-key <key>` flag (per command)
2. `STHAN_API_KEY` environment variable
3. `~/.sthan/credentials.json` (written by `sthan login`)

For CI/CD, set `STHAN_API_KEY` and skip `login`.

## Use with AI agents

Because it's a single binary with file I/O built in, AI coding agents (Claude Code, Cursor, …) can run it directly:

> "Verify the addresses in `customers.xlsx`."

→ the agent runs `sthan verify -i customers.xlsx -o results.csv` and reads back the summary. For an in-chat tool experience instead, see [`@sthan/mcp-server`](https://www.npmjs.com/package/@sthan/mcp-server).

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `STHAN_API_KEY` | No* | Your sthan.io API key. *Required unless saved via `sthan login` or passed with `--api-key`. |
| `STHAN_API_URL` | No | Override base URL (default: `https://api.sthan.io`) |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication error (missing/invalid API key) |
| 3 | Authorization error (plan limit / rate limited) |
| 4 | Input error (bad file or arguments) |
| 5 | Network error |
| 6 | Partial success (batch: some rows failed) |

## Links

- [API docs](https://sthan.io/docs)
- [Pricing](https://sthan.io/pricing/united-states)
- [OpenAPI spec](https://api.sthan.io/openapi.json)
- [AI reference](https://api.sthan.io/llms-full.txt)

## License

MIT
