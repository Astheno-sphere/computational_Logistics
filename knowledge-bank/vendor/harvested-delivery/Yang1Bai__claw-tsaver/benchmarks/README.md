# Benchmarks

Real measurement data from claw-tsaver runs.

## mvp-day1-fetch.jsonl

First end-to-end test of MVP (2026-04-25):
- Setup: OpenClaw + Claude Sonnet 4.6 + claw-tsaver + mcp-server-fetch
- Threshold: 200 tokens
- Test: fetch a Wikipedia page on tokenization
- Result: 11,507 tokens compressed to 104 tokens (**99.1% saved**)
- Model successfully called expand_content to retrieve full text when needed
