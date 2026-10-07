---
description: Apply venue-specific constraints for EasyPaper generation.
---

Use this skill when the user targets a specific conference or journal format.

## Supported venues

- `neurips`
- `icml`
- `iclr`
- `acl`
- `aaai`
- `colm`
- `nature`

## How to apply

1. Ask which venue the paper targets.
2. Set `style_guide` in the generation payload to the venue key.
3. If `target_pages` is not provided, use venue defaults.
4. Remind the user that final formatting must be validated against the official template for the target venue.

## Venue behavior

- Venue profiles inject page and style constraints used by the planning and writing stages.
- If a venue is unknown, fallback to neutral academic style and request manual constraints.
