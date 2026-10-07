---
license: apache-2.0
base_model: Qwen/Qwen3.5-9B
tags:
- open-jev
- non-generative
---

# Open-Jev decision checkpoint

This local package contains an Open-Jev LoRA adapter and scalar decision head derived from Qwen/Qwen3.5-9B.
Upstream revision: `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. The upstream model/tokenizer are required and are not bundled.

The adapter and Yes-minus-No-initialized scalar head are modified training products. Weights use Apache-2.0; Open-Jev source code remains MIT. See LICENSE, LICENSE-CODE and UPSTREAM.md.

## Recorded training

20,204 optimizer steps × global batch 4 = 80,816 consumed rows; 80,816 selected train rows out of 80,816.
Dataset: release-v2; source composition: release-v1, reasoning-control-v1.
Training coverage: one full pass over all train rows.
Topology: single process with gradient accumulation.
Code commit: `99e881108c6cacadafd364088505e84975ca43fc`. Full normalized hyperparameters and data hashes are in provenance.json.

## Recorded evaluation

The source run evaluated 512/10,532 test rows and 512/15,920 OOD rows using source/kind-balanced selection.
These results do not represent a separate full-data evaluation of all 26,452 held-out rows. Other pilot or benchmark results are not merged into this card.
Temperature 1.8969119 was recorded for 512 calibration rows; their ID hash is retained.

| Measurement | Rows | Hard-label accuracy | Expected accuracy | NLL | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_calibrated_ood | 512 | 0.667355 | 0.637869 | 0.864411 | 0.427617 | 0.0693149 |
| baseline_calibrated_test | 512 | 0.646809 | 0.615909 | 0.876303 | 0.43757 | 0.0380326 |
| baseline_ood | 512 | 0.667355 | 0.637869 | 0.862788 | 0.426134 | 0.0357867 |
| baseline_test | 512 | 0.646809 | 0.615909 | 0.881718 | 0.441505 | 0.0609296 |
| calibrated_ood | 512 | 0.923554 | 0.886388 | 0.327474 | 0.112074 | 0.0283001 |
| calibrated_test | 512 | 0.951064 | 0.903786 | 0.254392 | 0.0741149 | 0.0294664 |
| trained_ood | 512 | 0.923554 | 0.886388 | 0.413766 | 0.117756 | 0.0485585 |
| trained_test | 512 | 0.951064 | 0.903786 | 0.273097 | 0.0792583 | 0.0344311 |

## Load with Open-Jev

From an Open-Jev source checkout, install the training/inference dependencies and start the decision server:

```bash
python -m pip install '.[train]'
python -m jev.server --checkpoint /path/to/package/checkpoint \
  --device cuda:0 --max-length 4096 --batch-size 1 \
  --host 127.0.0.1 --port 8791
```

A suitable GPU and the exact upstream weights/tokenizer revision listed above are required, either cached locally or downloaded by the loader. The scalar decision head requires Open-Jev's loader; AutoPeftModel generation alone does not implement these decisions.

## Verification scope

Packaging verified source hashes, completed-step logs, frozen-data selection, model identity, calibration binding and saved reload logits. Both temperatures and all eight core/grouped metric sections were recomputed from the verified saved predictions using the repository's stdlib metrics. It hashes the current weight bytes but does not load tensors or repeat model inference. The training summary did not record output-weight hashes, so the historical reload is not an independent verification of the current packaged bytes.

Synthetic sampled scores do not establish general agent, browser, game, flight or closed-loop competence. The manifest identifies a local package; it does not imply an upload or public release.
