# Website and video release verification

The static project site is served at https://zefan-cai.github.io/open-jev/.
Source: `site/`; regeneration and deployment: [website documentation](../../docs/website-and-videos.md).

The current gallery is an outcome-selected showcase of reviewed successful
saved examples and explicit interface walkthroughs. `site/catalog.json` owns
the current counts and coverage. `demo-outcome-review.json` records the per-item
review; curation excludes failed and unverified model videos from published
media. The original model predictions, failed episodes and evaluation metrics
remain unchanged in their source reports. Selected examples do not estimate
a domain success rate.

The game overview contains complete successful Doom, T-Rex and Wiki episodes,
in that order. Doom uses native ViZDoom/Freedoom screen captures from exact
replay of all 11 saved decisions; observations, rewards and terminal flags
match, and the engine reports one kill. T-Rex clears all 12 obstacles and Wiki
reaches its target. The local games use their original environments with
presentation-only motion tweening. No steps are omitted within a selected
episode, and no new model inference was performed. These are saved 9B pilot
episodes, not final-checkpoint gameplay evaluations.

The current catalog and `site/media/gameplay-verification.json` identify the
selected assets and overview chapters. Check audit catalog/file hashes and
deployment commit identities before treating an older report as evidence for
the current selection. Codec/playback verification alone does not establish
task success.

## Historical publication audits

These records remain evidence for their recorded earlier publications; their
item counts, asset lists and chapter timings do not describe the selected
showcase:

- `catalog-audit.json`: source-file hashes and declared input/prediction
  bindings for the initial gallery.
- `artifact-audit.json`: codec, duration, fast-start layout, posters, captions,
  transcripts and site file hashes for the initial gallery.
- `browser-audit.json`: initial gallery filters, search, playback, captions,
  desktop/mobile layout and page/network checks.
- `artifact-audit-gameplay.json`, `gameplay-browser-audit.json` and
  `gameplay-page-audit.json`: the earlier continuous-game edition, which
  included failed Snake and platformer episodes and its older overview.
- `doom-native-capture.json`: the native replay's source/frame hashes and
  engine checks. Curation does not alter the captured episode.
- `gameplay-deployment.json`: the earlier successful Pages workflow,
  byte-for-byte live assets and browser playback. Its Snake checks and older
  overview timestamps are historical, not checks of the selected showcase.

The independent full-data audits remain the source for `site/results.json`;
the website does not rerun inference or change scientific acceptance criteria.
The 21 older community/recipe examples lack original request-byte attestation
and are excluded from this showcase; their recorded responses and limitations
remain in the original reports.

Regeneration must run `python3 scripts/curate_demo_site.py` after
`attach_gameplay_catalog.py`, then validate the resulting assets. Export with:

```sh
python3 scripts/export_site.py \
  --destination /path/to/Zefan-Cai.github.io/open-jev --prune-media
```

This removes excluded managed files from earlier publications at the
destination. Verify the current Pages commit, live assets and browser playback
after publishing; an earlier deployment audit or successful push alone is
insufficient. Prefix-cache implementation work is separate: saved clips
preserve their original inference method and checkpoint.
