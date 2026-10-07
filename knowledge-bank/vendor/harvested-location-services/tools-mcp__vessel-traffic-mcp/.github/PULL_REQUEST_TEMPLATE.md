## Summary

-

## Scope

-

## Safety Checklist

- [ ] This PR keeps all MCP tools read-only.
- [ ] This PR does not bypass authentication, paywalls, CAPTCHA, bot defenses, rate limits, or access controls.
- [ ] This PR does not commit API keys, bearer tokens, cookies, HAR files, raw captures, private browser sessions, `.env*`, or local credential profiles.
- [ ] New provider work exposes `source.provider` and `source.landingUrl` in live/public responses.
- [ ] Default verification does not call paid or live providers.

## Verification

- [ ] `npm run lint`
- [ ] `npm test`
- [ ] `npm run build`

## Notes for Reviewers

-
