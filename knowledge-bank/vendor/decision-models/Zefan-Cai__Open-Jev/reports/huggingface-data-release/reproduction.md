# Reproduction and original training-set restoration

Download a pinned dataset revision before reproducing an experiment:

```python
from huggingface_hub import snapshot_download
snapshot_download("ZefanCai/Open-Jev", repo_type="dataset",
                  revision="<dataset commit SHA>", local_dir="open-jev-data")
```

`export-manifest.json` identifies every public artifact by SHA-256. Original frozen manifests are preserved unchanged in `provenance/original-manifests/`. Source code used during export is in `reproduce/source-code/` with file hashes in the export manifest; this snapshot is authoritative if the linked GitHub branch changes.

## Exact published raw files

Decompress `raw/<config>/<split>.jsonl.gz` to obtain native Open-Jev JSONL. For the five new configs the uncompressed SHA equals the original manifest SHA. For the two composite projections it equals `raw_uncompressed_sha256` in the export manifest, because only Wikispeedia rows are missing. Gzip encoding uses `mtime=0` and no embedded filename.

Parquet retains the same records in `record_json`, and exposes structured top-level columns plus `state_json`/`metadata_json`. Parse those JSON columns before passing examples to the original code. Do not use audit metadata as model input.

## Restore the exact original release-v2 and expansion mixtures

The original `release-v2` includes 115,821 rows, and the original `browser-drone-expansion-v1` includes 163,050 rows. Both contain the same 2,253 Wikispeedia rows. Obtain those source data separately under their upstream terms:

- Landing page: https://snap.stanford.edu/data/wikispeedia.html
- Archive: https://snap.stanford.edu/data/wikispeedia/wikispeedia_paths-and-graph.tar.gz
- Archive SHA-256: `97697096f5d2dcb77aa69e3992305c6c561de89edb9fb10b5ad9feaf8ba534d5`

From `open-jev-data/reproduce/source-code`, with Python 3.10 or newer:

```bash
python -m jev.case_wikiracing --output-dir ../../../separately-obtained-wikiracing \
  --targets 300 --pairs-per-target 12 --max-candidates 12 --seed 42
```

The generator fetches and verifies the fixed upstream archive. To use an existing archive, pass `--archive /path/to/wikispeedia_paths-and-graph.tar.gz` with the same SHA. This operation does not download any data from the public projections or modify a training directory.

From the directory containing `open-jev-data` and `separately-obtained-wikiracing`:

```bash
python open-jev-data/reproduce/restore_original_mixture.py \
  --release-root open-jev-data --config release-v2-redistributable \
  --wiki-dir separately-obtained-wikiracing --output-dir restored-release-v2
python open-jev-data/reproduce/restore_original_mixture.py \
  --release-root open-jev-data --config browser-drone-expansion-v1-redistributable \
  --wiki-dir separately-obtained-wikiracing --output-dir restored-browser-drone-expansion-v1
```

The utility checks every separate Wiki split against the original import manifest. It inserts Wiki rows at the recorded original positions, using exactly `jev.mix_data`'s JSON serialization, then verifies all ten restored split files against the original mixture hashes. It refuses to overwrite existing split files. This complete restoration was verified against the original frozen files during publication.

Excluded row counts in each mixture are: train 1,700; calibration 89; validation 69; test 176; OOD 219. Their positions, but not their question/answer payload, are in `export-manifest.json`.

## Original build commands

The commands below document the original generator settings. Run in a separate workspace using the bundled source snapshot. Downloading/restoring the published frozen raw artifacts is the strongest byte-for-byte reproduction path; game generation additionally depends on its pinned runtime. The five newer manifests pin the relevant Python source hashes explicitly.

Base mixture:

```bash
python -m jev.case_customer --output-dir data/case-customer --groups 1000
python -m jev.case_workflows build --output-dir data/workflows-v1 --groups-per-workflow 250 --seed 42
python -m jev.game_cli build-data all --output-dir data/games-v1 --episodes 100 --max-steps 80 --seed 42
python -m jev.painting --output-dir data/painting-geometry-v1 --groups 60 --seed 42
python -m jev.game_cli build-control-data --output-dir data/control-games-v1 --episodes 100 --max-steps 40 --seed 42
python -m pip install vizdoom==1.2.4
python -m jev.case_doom build --output-dir data/doom-basic-v1 --episodes 400 --ood-episodes 80 --seed 190919
python -m jev.case_wikiracing --output-dir data/wikiracing --targets 300 --pairs-per-target 12 --max-candidates 12 --seed 42
python -m jev.mix_data --inputs data/case-customer data/doom-basic-v1 data/wikiracing \
  data/workflows-v1 data/painting-geometry-v1 data/games-v1 data/control-games-v1 --output-dir data/release-v1
python -m jev.case_reasoning --output-dir data/reasoning-control-v1 --groups 2500 --seed 76109
python -m jev.mix_data --inputs data/release-v1 data/reasoning-control-v1 --output-dir data/release-v2
```

Expansion:

```bash
python -m jev.case_browser --output-dir data/browser-v1 --groups 1000 --ood-groups 200 --seed 42
python -m jev.case_drone --output-dir data/drone-control-v1 --groups 500 --ood-groups 100 --seed 42
python -m jev.mix_data --inputs data/release-v2 data/browser-v1 data/drone-control-v1 \
  --output-dir data/browser-drone-expansion-v1
```

Separately prepared new corpora:

```bash
python -m jev.case_citation --output-dir data/citation-control-v1 --groups 200 --ood-groups 40 --seed 42
python -m jev.case_entity_alignment --output-dir data/entity-alignment-control-v1 --groups 200 --ood-groups 40 --seed 42
python -m jev.case_amount_extraction --output-dir data/amount-extraction-control-v1 --groups 200 --ood-groups 40 --seed 42
python -m jev.case_email_selection --output-dir data/email-selection-control-v1 --groups 200 --ood-groups 40 --seed 42
python -m pip install phonenumbers==9.0.14
python -m jev.case_phone_extraction --output-dir data/phone-extraction-control-v1 --groups 200 --ood-groups 40 --seed 42
```

This does not retrain any model. Check all generated files against the original manifest hashes before using them as a reproduction of a frozen corpus. Auxiliary case/document/family files in `artifacts/` can be decompressed directly; their uncompressed hashes are also recorded.

## Rebuild this export from the frozen project workspace

The GitHub repository keeps the export script and its input documentation in `reports/huggingface-data-release/`. With frozen source corpora available under that repository's `data/`, install `pyarrow`, then run:

```bash
python reports/huggingface-data-release/build_release.py \
  --repo /path/to/Open-Jev-Dev --output /path/to/fresh-staging-directory
```

The exporter checks every frozen input split hash, applies the single documented source filter, validates all Parquet/raw round-trips and verifies both full-mixture restorations. Its allowlist excludes external benchmark payload, data drafts, game assets, credentials and model weights.
