# Public dataset release verification

Published repository: https://huggingface.co/datasets/ZefanCai/Open-Jev

Verified release commit: [`341d9338462da1cf56ba57519fb0f3f5258b825f`](https://huggingface.co/datasets/ZefanCai/Open-Jev/commit/341d9338462da1cf56ba57519fb0f3f5258b825f)

The release has 148 published files (approximately 58.5 MB, excluding repository metadata): 35 Parquet splits, deterministic raw JSONL gzip files, original manifests, reproduction artifacts, source code and documentation.

| Config | Train | All splits |
|---|---:|---:|
| `release-v2-redistributable` | 79,116 | 113,568 |
| `browser-drone-expansion-v1-redistributable` | 108,624 | 160,797 |
| `citation-control-v1` | 2,520 | 4,000 |
| `entity-alignment-control-v1` | 6,944 | 11,200 |
| `amount-extraction-control-v1` | 32,984 | 49,600 |
| `email-selection-control-v1` | 3,618 | 5,400 |
| `phone-extraction-control-v1` | 12,350 | 19,000 |

Do not sum these config totals as unique examples: release-v2 is contained in the expansion mixture. The five newer control corpora are prepared/audited data, with no training or actual model inference performed at publication.

The original 2B/9B training mixture contained 80,816 training rows. Each public mixture excludes only the 2,253 Wikispeedia rows with an explicitly documented unverified redistribution license: train 1,700; calibration 89; validation 69; test 176; OOD 219. The public mixtures are not the exact original training datasets. The unchanged original manifests and source hashes are included with a restoration utility. No external Frontier 100 payload, private examples, ROMs, game assets, model weights or credentials were uploaded.

Validation completed:

- All 35 original split SHA-256 hashes matched their frozen manifests before export.
- Every Parquet row round-tripped to the exact public raw JSONL bytes; all counts, unique IDs and within-config cross-split group separation passed.
- Restoring the two original mixtures with separately held Wiki rows matched all ten original split hashes.
- Fresh regeneration from the pinned upstream Wiki archive using the bundled source snapshot matched all seven original Wiki artifact hashes.
- All 148 uploaded files matched local sizes and remote Git/LFS content hashes.
- `datasets.load_dataset` downloaded the pinned public commit and loaded all seven configs and 35 splits with exact expected counts and decoded-state checks.

Evidence: [local-verification.json](local-verification.json), [wiki-regeneration-verification.json](wiki-regeneration-verification.json), [remote-verification.json](remote-verification.json), [upload-result.json](upload-result.json), [export-summary.json](export-summary.json).

`build_release.py` creates a fresh audited staging directory from the frozen local data. `upload_release.py` takes `HUGGINGFACE_TOKEN` from the environment; it does not store the credential. Use `--verify-only <commit>` to repeat remote verification without publishing a new commit. `restore_original_mixture.py` is also shipped with the public dataset.

No active training data, GPU jobs or remote training checkouts were modified by this release.

## Archived dataset-card context

`dataset-card.md` is an exact archived copy of the published dataset README.
Its relative `THIRD_PARTY_NOTICES.md` link resolves at the dataset repository
root. Use the [fixed dataset card](https://huggingface.co/datasets/ZefanCai/Open-Jev/blob/341d9338462da1cf56ba57519fb0f3f5258b825f/README.md)
for that original context. The public-code release audit verified its exact
bytes and relative target at this public revision; the archived card is unchanged.
