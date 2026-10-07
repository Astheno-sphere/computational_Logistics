# Website and domain videos

The project website is published at **https://zefan-cai.github.io/open-jev/**.
The canonical static source is `site/` in this repository. The identical files
are copied into `open-jev/` in `Zefan-Cai/Zefan-Cai.github.io`, whose existing
GitHub Pages build serves the subsite. The personal homepage uses its existing
Jekyll configuration; this self-contained subsite needs no JavaScript build.

## What a video demonstrates

Every clip has its own request, provenance, model label, limitations, MP4,
poster and captions in `site/catalog.json`. Saved model replays use existing
outputs and disclose whether they came from the earlier 100-step pilot or the
completed 9B full-pass evaluation. Interface walkthroughs show the actual
request contract without inventing a model response. Animated game replays
visualize saved local state transitions; they are not captures of the original
commercial games or evidence that a final checkpoint can complete them.

The gallery is an **outcome-selected showcase** of reviewed successful saved
examples and explicitly labeled interface walkthroughs. The current
`site/catalog.json` owns its item counts and displayed coverage. Failed and
unverified model clips, including older mixed-outcome montages, are excluded
from the published media. This selection is not a representative evaluation
sample or a success-rate estimate; prepared task coverage is broader than the
selected gallery.

The native Doom recording replays all 11 saved decisions in ViZDoom 1.2.4 with
Freedoom: every observation, reward and terminal flag matches, and the engine
reports one kill. The game overview plays the complete successful Doom, T-Rex
and Wiki episodes in that order: the runner clears all 12 obstacles and Wiki
follows both links to its target. Episodes are selected by outcome; no saved
steps are omitted within a selected episode. These are original pilot episodes,
not later fully trained checkpoint results. Snake's wall collision and the
platformer's failure to reach a flag remain in the underlying evaluation
reports and trajectories, not in the published videos.

The initial gallery included 21 pilot community/recipe replays whose requests
were reconstructed from historical example revisions. Their original request
bytes were not recorded (`request_byte_attested: false`), so these unverified
clips are excluded from the selected showcase. Their saved responses and audit
limitations remain in the original reports. Browser/drone records and selected
full-pass rows have separate saved-request or dataset-hash bindings; the
per-item outcome review determines whether each is eligible for publication.

Playback is edited for readability; its duration is not inference latency.
Wrong decisions and unsuccessful episodes remain in the original evaluation
records; curation changes neither predictions nor metrics. No clip substitutes
reference labels, teacher actions or fixture answers for learned predictions.
The newly prepared citation, entity, amount, email, phone, context-retention,
sponsor-segment, silent-failure, retrieval and mailroom corpora have
no new-domain trained-model evaluation. A historical recipe smoke response
does not evaluate those corpora.

The gallery provides public per-clip evidence downloads. GitHub source links
may require repository access during the development preview. No checkpoints,
credentials, private official Jev cases, ROMs or upstream video assets are
included. The site identifies remaining unsupported community environments;
gallery coverage is not a claim of parity with every Jev example on X.

## Data and evaluation scope

The prepared inventory counts the 163,050-row browser/drone expansion once,
plus the ten newer corpora, without counting its constituent datasets again.

| Corpus | Train | Test | OOD | All splits |
| --- | ---: | ---: | ---: | ---: |
| Browser/drone expansion | 110,324 | 14,902 | 25,379 | 163,050 |
| Citation checking | 2,520 | 300 | 800 | 4,000 |
| Entity alignment | 6,944 | 1,008 | 2,240 | 11,200 |
| Amount extraction | 32,984 | 3,472 | 9,920 | 49,600 |
| Email selection | 3,618 | 432 | 1,080 | 5,400 |
| Phone extraction | 12,350 | 1,615 | 3,800 | 19,000 |
| Context retention | 6,138 | 522 | 2,160 | 9,834 |
| Sponsor segments | 6,345 | 999 | 2,160 | 10,800 |
| Silent failure | 6,432 | 624 | 1,920 | 9,600 |
| Graded retrieval | 7,366 | 986 | 2,320 | 11,600 |
| Multilingual mailroom | 73,472 | 8,323 | 22,960 | 114,800 |
| **Total** | **268,493** | **33,183** | **74,739** | **408,884** |

There are 25 task-source identifiers (24 domains if the two
customer sources are grouped). Calibration adds 16,937 rows and validation
15,532. These are typed decision rows, not distinct documents or episodes.
Citation quote-not-found controls are separate: 400 across all splits,
including 30 test and 80 OOD. They are not added to the typed counts above.

The displayed 2B/9B accuracy belongs to the earlier release-v2 evaluation:
26,452 rows per model, including 25,492 hard-label rows and 960 soft-label
rows. It does not evaluate the entire prepared inventory. The independent
JF100 holdout contains 100 questions with three option rotations, not 300
independent questions. Final-model JF100 and closed-loop task scores remain
pending. Read the [full-data audit](../reports/full-data-eval-n1-v1/README.md)
for denominators, probability metrics and weak subgroups.

## Reproduce and publish

The catalog builder and renderer run locally without a GPU. Rendering requires
Python 3.10+, Pillow, ffmpeg/ffprobe and a TrueType font (Helvetica on macOS or
DejaVu Sans on Linux). Clips are silent H.264 videos with English captions and
plain-text transcripts. Catalog rebuilding needs the locally retained source
predictions and frozen datasets; the committed catalog and media can be viewed
without them. The renderer uses only the catalog and makes no inference calls.

```sh
python3 scripts/build_demo_catalog.py
python3 scripts/build_site_results.py
python3 scripts/render_demo_videos.py --workers 3
python3 scripts/render_gameplay_videos.py --doom-capture /path/to/doom-10001
python3 scripts/attach_gameplay_catalog.py
python3 scripts/curate_demo_site.py
python3 scripts/check_site_assets.py --output reports/site/artifact-audit-showcase.json
```

The curation step reads `reports/site/demo-outcome-review.json`, retains only
reviewed successes and interface walkthroughs, updates catalog coverage, and
removes excluded managed media. Rebuilding the raw catalog or rendering alone
does not apply the publication selection; always finish with curation and
asset verification.

For Doom, `scripts/capture_doom_gameplay.py` re-executes the saved episode in a
CPU ViZDoom environment and writes PNGs plus a hash-bound `capture.json`:

```sh
CUDA_VISIBLE_DEVICES='' python3 scripts/capture_doom_gameplay.py \
  --trace reports/pilot-suite-n1-4k/9b/games/trajectories/doom_basic-model-seed-10001.json \
  --output /path/to/new/doom-10001
```

It never calls a model and rejects any mismatch with the saved trajectory.
The native engine exposes no screen buffer after terminal; the last available
frame is held behind the result overlay. All available game tics are included.
The other games are rendered from exact re-execution of their original local
Python environments, with presentation-only motion tweening.

Video coverage and verification results are recorded with the website release
in `reports/site/`. Do not start another inference server on the four training
GPUs to regenerate videos while the 27B run is active.

To preview the committed site:

```sh
python3 -m http.server 8792 --directory site
# Open http://127.0.0.1:8792/
```

After verifying catalog provenance, media playback and mobile layout, copy
the static assets to the personal-site checkout:

```sh
python3 scripts/export_site.py \
  --destination /path/to/Zefan-Cai.github.io/open-jev --prune-media
```

The exporter writes only below `open-jev/`. With `--prune-media`, it removes
managed media absent from the reviewed selection, including files left by an
earlier publication; original evaluation records are not export targets.
Review and commit both repositories, then push the personal site's `main`
branch. Verify the Pages build and the live HTML, catalog and media responses;
a successful Git push alone does not establish that the site is live.
