## Summary

<!-- What does this PR do? 1-3 bullet points. -->

## Type of change

- [ ] Bug fix
- [ ] New feature / rule / adapter
- [ ] Refactor / cleanup
- [ ] Docs only

## Testing

- [ ] `npm test` passes (`node --test src/**/*.test.js`)
- [ ] All modules load without errors
- [ ] Tested against a real project (describe briefly below)

<!-- What did you test against? e.g. "ran qa-probe analyze on a Vite + React + FastAPI app" -->

## Checklist

- [ ] My commits are signed off (DCO): `git commit -s` — see [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] No hardcoded project names, credentials, or internal paths in the code
- [ ] If adding a root-cause rule: tests cover the new rule and its priority vs existing rules
- [ ] If adding a framework adapter: added to `src/analyze/adapters/` and wired in `backend-fetcher.js`
- [ ] If adding a config key: added to `src/config/schema.js` and documented in `README.md`
- [ ] `rootCauseDetail` / `fixHint` messages are generic (no project-specific naming)
