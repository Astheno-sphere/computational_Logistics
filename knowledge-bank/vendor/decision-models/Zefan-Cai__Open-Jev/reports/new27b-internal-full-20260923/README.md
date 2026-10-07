# Open-Jev 27B v1.1: complete internal evaluation

The complete 127,787-row evaluation passed the independent full24 audit on 2026-09-23: `status=passed_complete_full24_audit`, `publishable=true`. Every expected prediction is present exactly once, with zero failed rows. All six controllers exited successfully and their owned GPU processes were cleaned up before the evidence was captured.

| Checkpoint | Old Test | Old OOD | Expanded Test | Expanded OOD |
|---|---:|---:|---:|---:|
| Open-Jev 27B v1.1 | 9,876 / 10,046 (98.31%) | 14,825 / 15,446 (95.98%) | 41,357 / 42,789 (96.65%) | 80,934 / 83,924 (96.44%) |
| All evaluated rows | 10,532 | 15,920 | 43,301 | 84,486 |
| Soft-target rows | 486 | 474 | 512 | 562 |

Accuracy uses exact one-hot targets. Soft-target records remain in the complete outputs and probability metrics. The old columns are unchanged-content subsets of the expanded columns; they overlap and must not be added to the expanded sample count. These are decision-row-weighted results, not game win rates or workflow completion rates.

[report.json](report.json) is the sanitized, audit-gated aggregate. It includes exact numerators, hard/soft denominators, expected accuracy, NLL, Brier, expected Brier and calibration error for all four panels. [source-identities.json](source-identities.json) records frozen code, dataset and checkpoint hashes. The report binds the complete private audit, capture receipt and merged summary by SHA-256.

The checkpoint is a rank-8 LoRA adapter plus a scalar FP32 decision head over BF16 `Qwen/Qwen3.8-27B`, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`. Its exact tree SHA-256 is `c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71`. The saved temperature is 2.5343690298472983. Evaluation used a 4,096-token limit, no truncation, cache disabled and one record per rank. Calibration was not refitted on Test or OOD.

## Evidence and independent checks

The immutable campaign combines 4,491 previously completed predictions with 123,296 disjoint new predictions from six independent four-GPU groups. The imported coordinates are not a contiguous prefix. Every raw byte, source identity, global coordinate and rank assignment was checked against the frozen manifest before aggregation. Padding forwards are excluded.

The collector verified all six successful controller exits, all 36 recorded process identities absent, completed progress and owned GPU cleanup. It then captured 268 remote files with identical source-before, source-after and local hashes, along with the frozen local launch evidence. No worker was retried or restarted during collection or audit.

The independent verifier uses Python's standard library and does not import the evaluator, project metric functions, Torch or a model runtime. It verifies the complete raw/merged union, finite logits, saved-temperature softmax, original and latest passing probes, identities and hashes. It recomputes every panel and each source/type/question breakdown, with exact integer agreement, a probability tolerance of 1e-12 and an absolute/relative metric tolerance of 3e-11. The capture is rehashed after arithmetic. Preparing a verifier or passing its CPU fixtures alone does not grant publication.

The original complete mixture has 328,672 rows (Train 148,639). The [HF dataset](https://huggingface.co/datasets/ZefanCai/Open-Jev-v1.1) is a 326,619-row redistributable projection (Train 147,139), excluding 2,053 Wiki rows. It is not the complete training/evaluation corpus. Restricted source records and private operational capture remain outside this public repository. Public hashes and code support inspection but cannot reconstruct omitted source records.

## Replaying the audit with the complete original capture

[verify_campaign.py](verify_campaign.py) checks the final campaign and uses the independent arithmetic in [verify.py](verify.py). Given access to the complete preserved capture and frozen merger output, run:

```bash
python3 -B reports/new27b-internal-full-20260923/verify_campaign.py \
  --campaign "$CAPTURE/campaign/manifest.json" \
  --capture-root "$CAPTURE" \
  --data "$CAPTURE/data/community-hard-mix-v2-final" \
  --old-data "$CAPTURE/data/release-v2" \
  --checkpoint "$CAPTURE/checkpoint" \
  --merged "$MERGED" \
  --output full24-independent-audit.json
```

The code hashes in source-identities.json refer to the frozen execution tree. The public projection replaces private hardware identities in the resource-policy modules with inert placeholders; PUBLIC_RELEASE.json records both original and projected hashes. Replaying the original audit requires the original hash-verified capture, not substituting those projected source files.

The output must be a new file. The standalone historical `verify.py` CLI expects the former single-group schema and must not be used for this campaign. The collector is an internal operations tool and is not included in the public projection. The audit performs no inference or job control.

## Separate external benchmark and limitations

The [independently audited JevBench result](../new27b-jevbench-20260922/README.md) is **197/231 (85.28%)**, Hard **80/111 (72.07%)**. It covers the public 231-task subset, not all 534 tasks. Jev 1.13 scored 200/231 and 81/111, so this 27B checkpoint remains three overall and one Hard answer behind it. JevBench used a separate 16,384-token protocol.

Released 2B/9B results retain their checkpoint identities. New 2B training was stopped and new 9B training was not started. The hosted [interactive workbench](https://zefan-cai.github.io/open-jev/workbench/) uses the released 2B CPU model. Shared multi-GPU evaluation times are not single-GPU or HTTP/API latency measurements and establish no speedup.
