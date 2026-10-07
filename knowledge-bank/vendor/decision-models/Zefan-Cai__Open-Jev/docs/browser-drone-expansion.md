# Browser and drone expansion training mixture

`data/browser-drone-expansion-v1` combines the frozen `release-v2`, `browser-v1`,
and `drone-control-v1` datasets. It is selected for the fresh four-GPU 27B run
in the [user-directed schedule](four-gpu-handoff.md). Completed 2B/9B runs used
release-v2. The mixture does not establish complete Jev task coverage.
The added browser and drone data cover synthetic snapshot decisions, not full
browser execution or drone flight; see [browser data](browser-data.md) and
[drone data](drone-data.md).

| Input dataset | Records | Train records | Groups |
| --- | ---: | ---: | ---: |
| `release-v2` | 115,821 | 80,816 | 10,771 |
| `browser-v1` | 21,980 | 13,814 | 1,000 |
| `drone-control-v1` | 25,249 | 15,694 | 500 |
| Expansion mixture | **163,050** | **110,324** | **12,271** |

| Split | Records |
| --- | ---: |
| Train | 110,324 |
| Calibration | 6,883 |
| Validation | 5,562 |
| Test | 14,902 |
| OOD | 25,379 |

The primitive totals are 58,239 Choice, 79,057 Noul, and 25,754 Score rows.
`jev.mix_data` concatenates existing split files without resampling, changing
labels, moving held-out rows to train, or deduplicating them. The 1,668 repeated
visible inputs already present within `release-v2` remain with their original
weights; the mixture has 161,382 unique visible inputs. No new duplicates
appear between the three datasets, and no duplicate-input target conflicts or
cross-split groups were found.

The [native manifest copy](../reports/data-manifests/browser-drone-expansion-v1.json)
records mixture counts and output split hashes and is byte-identical to the
unchanged CLI's output. The separate
[integrity report](../reports/data-manifests/browser-drone-expansion-integrity.json)
records each source's split counts, all three input-manifest SHA-256 values,
the 20 original files' unchanged before/after content hashes, and the unchanged
mixing/validation code hashes. Every mixed row was checked against the original
row in full, including its source, group, split, model inputs, target, and
metadata. No GPU work or benchmark-item access was used for this build.

## Rebuild the split files

Run from the repository root with the three frozen input directories present
and an absent output directory:

```bash
python -m jev.mix_data \
  --inputs data/release-v2 data/browser-v1 data/drone-control-v1 \
  --output-dir data/browser-drone-expansion-v1
python -m jev.data validate data/browser-drone-expansion-v1
```

The unchanged CLI reproduces the split files and native manifest without
manual enrichment. The integrity report records this build's separately
completed provenance checks. Original source directories and existing training
configurations were not modified.

The [complete tokenizer preflight](../reports/preflight/browser-drone-expansion-v1/README.md)
measured all 163,050 records for each of the three pinned models. Every candidate
fits the existing 4,096 training cap; the maximum is 1,756 tokens. Explicitly
set that cap: the direct trainer's default 512 and the older preflight's default
1,536 reject parts of this mixture. The new train split contains 3.801 times the
nonpadding input tokens of release-v2. The linked report preserves an earlier
2B pilot proposal that was superseded by the user-directed fresh 27B run and
was never launched. Tokenizer checks establish input lengths; actual training
progress, memory use and held-out results require separate runtime evidence.
