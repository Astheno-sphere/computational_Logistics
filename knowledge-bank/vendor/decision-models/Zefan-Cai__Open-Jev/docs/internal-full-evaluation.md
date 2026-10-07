# Full internal evaluation

**Open-Jev 27B v1.1 passed the complete independent audit on 2026-09-23.** All 127,787 expanded held-out records have exactly one successful prediction, with zero failures, missing rows or duplicates. All six evaluation groups exited successfully and their owned GPU processes were cleaned up. See the [compact audited report](../reports/new27b-internal-full-20260923/report.json).

| Model | Old Test | Old OOD | Expanded Test | Expanded OOD | JevBench public 231 | Hard 111 |
|---|---:|---:|---:|---:|---:|---:|
| Released 2B | 9,515 / 10,046 (94.71%) | 13,287 / 15,446 (86.02%) | Not evaluated | Not evaluated | 150 / 231 (64.94%) | 46 / 111 (41.44%) |
| Released 9B | 9,799 / 10,046 (97.54%) | 14,205 / 15,446 (91.97%) | Not evaluated | Not evaluated | 179 / 231 (77.49%) | 66 / 111 (59.46%) |
| 27B v1.1 | 9,876 / 10,046 (98.31%) | 14,825 / 15,446 (95.98%) | 41,357 / 42,789 (96.65%) | 80,934 / 83,924 (96.44%) | 197 / 231 (85.28%) | 80 / 111 (72.07%) |

Old Test/OOD cover all 10,532 / 15,920 rows; Expanded Test/OOD cover all 43,301 / 84,486 rows. Internal cells show hard-correct / hard rows. Soft targets (486 / 474 / 512 / 562 rows, respectively) remain in probability metrics. The old panels are unchanged-content subsets of the expanded panels; they overlap and must not be added together.

The released 2B/9B rows retain their [original audit](../reports/full-data-eval-n1-v1/README.md). Their expanded columns are not evaluated. New 2B training stopped, and new 9B training did not start; neither receives a result from the 27B run.

The separate [27B JevBench audit](../reports/new27b-jevbench-20260922/README.md) covers the 231 public tasks, not the complete 534-task benchmark. Its 197/231 overall and 80/111 Hard remain below Jev's 200/231 and 81/111. JevBench uses its own 16,384-token protocol; the internal protocol below uses 4,096.

## Checkpoint and protocol

- Model: `Qwen/Qwen3.8-27B`, base revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Checkpoint tree SHA-256: `c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71`.
- LoRA rank 8, BF16 base and FP32 scalar head; saved temperature `2.5343690298472983`.
- Predeclared final checkpoint after 37,160 optimizer steps; evaluation scores did not select a checkpoint.
- Maximum length 4,096, no truncation, one row per rank and caching disabled. Temperature was not refitted on evaluation data.
- Expanded dataset manifest: `7b26f948d2ae11f20d7a18be437d1ada616fc479e1596ae94be7596787fe4e54`.
- Original release dataset manifest: `56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97`.

Every source split file was checked against its manifest. Original Test/OOD records retain their inputs, candidate order and targets inside the expanded splits. The same new 27B predictions therefore provide both the old and expanded panels. Expanded means the complete expanded split, including original rows.

## Complete capture and independent replay

The evaluation combined 4,491 preserved original predictions with 123,296 predictions from six independent four-GPU groups. The imported coordinates were checked individually, including the uneven shard tails, rather than treated as a contiguous prefix. Padding forwards were excluded from predictions and denominators.

The audit verified exact IDs, order, raw bytes, rank assignments, frozen code/data/checkpoint identities, complete controller exits and owned GPU cleanup. Remote hashes before and after capture matched the captured local files. All nine parity fixtures passed in all six groups; the maximum logit difference across the 15 group pairs was zero.

Independent standard-library arithmetic recomputed saved-temperature softmax, hard numerators and denominators, expected accuracy, NLL, Brier, expected Brier, 15-bin top-label ECE and per-source/type/question metrics. The maximum probability difference was 8.88e-16; aggregate metric differences were zero. The report records the exact tolerances, source hashes and audit implementation identities. Only `status: passed_complete_full24_audit` with `publishable: true` is accepted by the site exporter.

Hard-label accuracy counts only one-hot targets. The 1,074 expanded soft-target rows remain in probability metrics. All aggregates weight decision rows; they are not equal-source or equal-group averages. Source-defined OOD controls do not establish unrestricted real-world generalization. No matching full-data base-model evaluation was run, and comparisons with the older 2B/9B also change model scale and training history.

The archived 512-row training diagnostics are separate sampled measurements and do not fill these full-evaluation columns. Shared multi-GPU execution times are not single-GPU latency, HTTP/API latency or speedup measurements. Final-model JF100 and closed-loop task results remain pending.

## Data release scope

The internal evaluation used the complete original mixture: 328,672 rows, including 148,639 training rows. The [HF v1.1 dataset](https://huggingface.co/datasets/ZefanCai/Open-Jev-v1.1) is a redistributable projection with 326,619 rows / 147,139 training rows, excluding 2,053 Wiki rows. It is not the complete training or evaluation corpus. WANLI retains CC BY 4.0; original generated records use CC0; TypeSafe short questions retain their documented source-license limitation.

Public artifacts provide allowlisted aggregates, identities and verifier code. Restricted source records and private capture evidence remain outside the public projection; their hashes are retained. The public aggregate alone cannot reconstruct restricted records.
