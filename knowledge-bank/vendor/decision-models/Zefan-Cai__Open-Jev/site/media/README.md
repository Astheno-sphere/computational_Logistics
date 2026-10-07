# Reproducible demo videos

These silent videos visualize the frozen [`catalog.json`](../catalog.json).
The gallery selects reviewed successful saved examples and explicitly labeled
interface walkthroughs. Walkthroughs contain no invented model response.
Failed and unverified videos are excluded from published media; original
predictions, failed trajectories and metrics remain in the evaluation reports.
This outcome-selected showcase is not a representative success-rate estimate.
The catalog owns its current item counts and coverage.

Each selected item has an H.264 MP4, JPEG poster, English WebVTT captions and
plain-text transcript. Technical views are 16 seconds; complete game episodes
have their own durations. Playback timing is edited for readability and is not
inference latency. No audio track is included. Older mixed-outcome technical
montages are excluded from the selected publication.

## Regeneration and selection

From the repository root, after rebuilding the source catalog and results:

```sh
python3 scripts/render_demo_videos.py --workers 3
python3 scripts/render_gameplay_videos.py --doom-capture /path/to/doom-10001
python3 scripts/attach_gameplay_catalog.py
python3 scripts/curate_demo_site.py
python3 scripts/check_site_assets.py --output reports/site/artifact-audit-showcase.json
```

The curation step reads `reports/site/demo-outcome-review.json`, keeps reviewed
successes and interface walkthroughs, and removes excluded managed media.
Rendering alone does not apply this publication selection. Publish with:

```sh
python3 scripts/export_site.py \
  --destination /path/to/Zefan-Cai.github.io/open-jev --prune-media
```

This also removes excluded files from the destination's managed media.

Install Pillow, `ffmpeg` and `ffprobe`; use Python 3.10 or newer and a TrueType
font such as Helvetica on macOS or DejaVu Sans on Linux. Font and encoder
versions can affect file bytes. Rendering and replay verification are CPU
only and make no model inference calls. Regenerating the source catalog needs
its retained source predictions and frozen datasets; viewing committed media
requires neither a model nor a service.

The current artifact audit under `reports/site/` records every published
video's hash, dimensions and codec. Original generation audits remain there as
historical evidence. The public site supplies native player controls, captions
and transcripts.

## Selected continuous game videos

`gameplay-doom`, `gameplay-trex` and `gameplay-wiki` show complete successful
episodes with a visible goal and final outcome. `gameplay-overview` concatenates
those episodes in that order. Its exact duration and chapter boundaries are
recorded in `gameplay-verification.json`.

The runner and Wiki re-execute every saved action through their original local
Python environments, checking observations, rewards and terminal state. Doom
uses all 42 captured native ViZDoom frames from its 11-decision episode at
0.2× playback speed. The engine supplies no screen buffer after terminal, so
the last available screen is held behind the result overlay. No saved steps
or captured frames are omitted within a selected episode.

These episodes use fixed seed 10001 and the original 100-step 9B pilot. They
were selected because they succeeded; failed Snake and platformer episodes
remain in the underlying evaluation reports. No new policy evaluation is
implied. `gameplay-verification.json` binds the source/native-frame hashes,
engine matches, successful outcomes, codecs and complete overview chapters.
Earlier broader-gallery audits are historical; see
[the report index](../../reports/site/README.md).
