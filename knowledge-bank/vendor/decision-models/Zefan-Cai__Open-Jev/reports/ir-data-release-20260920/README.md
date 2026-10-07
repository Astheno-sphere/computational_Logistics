# ir-control-v1 data publication

Published [11,600 original typed rows in five splits](https://huggingface.co/datasets/ZefanCai/Open-Jev/commit/b0aad4004b8d74f4a6ca66c7a9175fe17478d688). All new Parquet rows and raw JSONL records were loaded anonymously and matched exactly. The dataset now had 11 configs and 55 splits at this revision.

All 202 prior files except the root dataset card retained their content identifiers and sizes. Earlier config definitions, default config and training mixtures stayed unchanged. No retraining or full-corpus model-quality result is implied by publication.

The independent corpus audits and generation code are documented in [ir-control-v1](../../docs/ir-control-data.md). API probes are separate from corpus publication. These are finite original controls, not third-party TREC documents or private mailbox data.

Evidence:

- [Anonymous remote and split verification](remote-verification.json)
- [Every uploaded file's byte verification](anonymous-payload-verification.json)
- [Sealed additive upload plan](upload-plan.json)
- [Local original-record round trip](local-verification.json)

These public evidence projections preserve counts, file digests and results, and replace local absolute paths with relative paths. The original evidence-file SHA-256 is included in each projection.
