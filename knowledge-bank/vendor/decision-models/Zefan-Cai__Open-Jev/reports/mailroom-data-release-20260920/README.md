# mailroom-control-v1 data publication

Published [114,800 original typed rows in five splits](https://huggingface.co/datasets/ZefanCai/Open-Jev/commit/c67699e13d0ae25e35b77165a4b6b079bedc8aba). All new Parquet rows and raw JSONL records were loaded anonymously and matched exactly. The dataset now had 12 configs and 60 splits at this revision.

All 219 prior files except the root dataset card retained their content identifiers and sizes. Earlier config definitions, default config and training mixtures stayed unchanged. No retraining or full-corpus model-quality result is implied by publication.

The independent corpus audits and generation code are documented in [mailroom-control-v1](../../docs/mailroom-control-data.md). API probes are separate from corpus publication. These are finite original controls, not third-party TREC documents or private mailbox data.

Evidence:

- [Anonymous remote and split verification](remote-verification.json)
- [Every uploaded file's byte verification](anonymous-payload-verification.json)
- [Sealed additive upload plan](upload-plan.json)
- [Local original-record round trip](local-verification.json)

These public evidence projections preserve counts, file digests and results, and replace local absolute paths with relative paths. The original evidence-file SHA-256 is included in each projection.
