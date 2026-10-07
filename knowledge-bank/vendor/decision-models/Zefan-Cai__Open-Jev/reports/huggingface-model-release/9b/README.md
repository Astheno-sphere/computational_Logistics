---
license: apache-2.0
base_model: Qwen/Qwen3.5-9B
base_model_relation: adapter
library_name: peft
tags:
- open-jev
- qwen3.5
- lora
- non-generative
- typed-decisions
---

# Open-Jev-9B

**A trained LoRA adapter and scalar decision head for Qwen/Qwen3.5-9B.** This repository contains the completed Open-Jev decision checkpoint, not merged or standalone base-model weights. It requires the exact upstream model/tokenizer revision **`c202236235762e1c871ad0ccb60c8ee5ba337b9a`** and the [Open-Jev loader](https://github.com/Zefan-Cai/Open-Jev).

Open-Jev scores caller-supplied candidates directly and returns typed decisions without autoregressive answer generation:

- **Choice:** probabilities over the supplied candidate set and its most probable candidate.
- **Noul:** a probability for a yes/no question.
- **Score:** probabilities over supplied ordinal levels and their expected value.

The adapter targets the Qwen text backbone. A generic `AutoPeftModel` text-generation call does not implement this interface or apply the separate decision head and saved temperature.

## Download and run

Use a suitable GPU with the upstream weights available locally or downloadable from Hugging Face. The loader uses the pinned upstream revision in `package/checkpoint/model.json`.

```bash
git clone https://github.com/Zefan-Cai/Open-Jev.git
cd Open-Jev
python -m pip install -e '.[train]'
hf download ZefanCai/Open-Jev-9B --local-dir ./checkpoints/open-jev-9b
python -m jev.server \
  --checkpoint ./checkpoints/open-jev-9b/package/checkpoint \
  --device cuda:0 --max-length 4096 --batch-size 1 --no-prefix-cache \
  --host 127.0.0.1 --port 8791
```

The repository's `train` extra supplies inference dependencies too, including Transformers 5.10.2 and PEFT 0.19.1. Prefix caching is opt-in and is disabled above; real-checkpoint GPU A/B validation remains separate. For reproducible deployments, add `--revision <commit>` to `hf download` using a commit from this model repository's history.

Once the server is ready, submit a request. This is an input example, not a claim about a recorded prediction:

```bash
curl http://127.0.0.1:8791/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{"state":"I was charged twice and want a refund.","questions":{"intent":{"type":"choice","instructions":"Choose the customer intent.","criteria":{"billing":"A payment or refund issue","technical":"A malfunction or setup issue","other":"Another request"}}}}'
```

The server returns declared keys and probabilities. It does not execute the proposed actions. The model's maximum input length is 4,096 tokens per independently scored candidate; input is rejected rather than silently truncated.

## Training and data

- 20,204 optimizer steps with global batch 4: **80,816 consumed training rows**, one full pass over the frozen `release-v2` training split.
- LoRA rank 8, alpha 16; scalar head initialized from the pretrained Yes-minus-No readout and trained jointly with LoRA.
- Training source commit: `99e881108c6cacadafd364088505e84975ca43fc`.
- Frozen data manifest SHA-256: `56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97`.
- Saved temperature: `1.8969118766347646`; fitted only on 512 calibration rows.

The [public dataset repository](https://huggingface.co/datasets/ZefanCai/Open-Jev) provides `release-v2-redistributable`. Its training split has **79,116 rows**, excluding the 1,700 original training records from `wikispeedia-v1` because redistribution permission for that archive has not been confirmed. It is **not byte-identical to the 80,816-row training set** used for these weights. The original manifest and split hashes remain recorded in [package/provenance.json](package/provenance.json); no source dataset rows are bundled here.

The later browser/drone expansion and five later extraction-control corpora are not part of this checkpoint's training mixture. Public game videos may use separately identified older pilot checkpoints and are not automatically evidence for these full-pass weights.

## Full held-out evaluation

The existing full-data evaluation covers **10,532 test + 15,920 OOD = 26,452 records**, with zero missing, duplicate, or failed inference records. This evaluation used the original frozen mixture, including its Wiki records, rather than the redistributable projection. Its five inference-file hashes match the weights and metadata published here.

| Split | All rows | Hard correct / hard rows | Hard accuracy | Expected accuracy | NLL | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Test | 10,532 | 9,799 / 10,046 | 97.54% | 94.72% | 0.130947 | 0.039113 | 0.007707 |
| OOD | 15,920 | 14,205 / 15,446 | 91.97% | 90.40% | 0.299441 | 0.126647 | 0.037398 |

Hard accuracy excludes soft-target rows. Expected accuracy is the reference target mass at the chosen candidate across all rows; it is not a game-win or workflow-completion rate. NLL, Brier, and ECE use all rows and the saved calibration. Full machine-readable results are in [evaluation/full-data.json](evaluation/full-data.json).

No full-data baseline was evaluated, so this table does not establish training gain. The original package also preserves the training run's separate 512-test/512-OOD sampled metrics in [package/metrics.json](package/metrics.json) and its original card in [package/README.md](package/README.md). Those smaller sampled results should not be confused with the full-data table above.

## Artifact layout and verification

`package/` is the unchanged verified inference package, including its original manifest, card, calibration, provenance, and sampled metrics. The root [release-manifest.json](release-manifest.json) binds the complete Hugging Face release layout.

| Artifact | SHA-256 |
| --- | --- |
| LoRA adapter | `f85650a8fb97c6d0ac3e948cdca2f30a0ca6ace8b8a43aebca1c152fe38aeb75` |
| Scalar head | `229fe9800384e824135e59d1af59bda7346da031aea61640be5f456b9be6ce70` |
| Original package manifest | `e83fd15c8715c9a7e474afd0830d55b0fe4b25ab61910114f6e36437a2964e37` |

The original evaluated checkpoint directory had digest `a691105dd5751bfcf72d276a6ce075d45054db77ae3272e87b5f07b2bd7e2193`. The packaged five-file inference directory has digest `9302c52feba99d079918755f2469f4f088266e9786327bab550248f3d83716d3` because the packaging whitelist omits the generated adapter README. These directory digests are not interchangeable: the evaluation binding is verified **per inference file**.

Release checks cover manifest bytes, pinned model/revision, licenses, calibration, finite CPU adapter/head tensors, and correspondence to the completed evaluation's inference files. No GPU inference was repeated during this upload. The trainer's historical reload logits were checked, but training did not record a contemporaneous output-weight digest; this upload does not invent one.

Synthetic held-out decision metrics do not establish broad real-world reliability, closed-loop browser/game/flight success, or a calibrated probability guarantee outside the evaluated distribution.

## License

The trained adapter and head are released under **Apache-2.0**, with the complete pinned Qwen/Alibaba Cloud attribution in [LICENSE](LICENSE) and [UPSTREAM.md](UPSTREAM.md). Open-Jev source code is **MIT**, preserved in [LICENSE-CODE](LICENSE-CODE). The upstream model/tokenizer must be obtained separately under their own terms.
