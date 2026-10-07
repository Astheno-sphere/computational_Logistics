---
name: Bug report
about: Something is broken or producing wrong output
title: '[bug] '
labels: bug
assignees: ''
---

## What happened

<!-- Describe the bug clearly -->

## Expected behaviour

<!-- What should have happened instead -->

## Steps to reproduce

```bash
# Minimal config or command that triggers the bug
npx qa-probe run --config qa-probe.config.js
```

## Environment

- **qa-probe version**: <!-- run: npx qa-probe --version -->
- **Node.js version**: <!-- run: node --version -->
- **OS**: <!-- e.g. Ubuntu 22.04, macOS 14, Windows 11 -->
- **Framework**: <!-- fastapi / express / nextjs / generic -->
- **Router**: <!-- React Router v6 JSX / createBrowserRouter / TanStack Router / other -->

## Output / error message

```
# Paste the full terminal output here
```

## Config (sanitised — remove credentials)

```js
module.exports = {
  baseUrl: 'http://localhost:8000',
  // ...
};
```

## Additional context

<!-- Anything else that might help — OpenAPI spec snippet, router file snippet, etc. -->
