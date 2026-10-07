# Security

## Default Mode

This MCP server does not require private keys in default mode. It makes unpaid requests to paid endpoints and returns structured x402 payment challenge metadata.

## Secrets

- Do not commit secrets.
- Do not paste private keys into chat, issue trackers, logs, or MCP prompts.
- Do not store wallet seed phrases in this repository.
- Do not hardcode wallet addresses or payment credentials in package code.

## Paid Settlement

Paid settlement should be handled by a trusted wallet or payment client. This MCP package does not implement private key handling or payment settlement in v1.

Future paid execution must be explicit, opt-in, documented, and testable without spending funds by default.

## Reporting Issues

Report security issues privately to the maintainers. Do not open a public issue with exploit details, private keys, credentials, or payment material.
