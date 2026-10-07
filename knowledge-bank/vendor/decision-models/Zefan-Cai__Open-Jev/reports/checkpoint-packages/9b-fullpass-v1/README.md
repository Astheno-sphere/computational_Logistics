# Final 9B checkpoint package metadata

This directory archives metadata from the completed release-v2 9B run. The
actual inference package is retained on N1-1 at
`/data/zefan/open-jev/packages/release-v2-fullpass-n1-v1/9b`; this Git directory
does not contain its adapter/head weights and is not itself a loadable package.

The [generated model card](MODEL_CARD.md), [provenance](provenance.json),
[metrics](metrics.json) and [full package manifest](manifest.json) are exact
copies. Their package-relative license/loader references apply to the complete
bundle. The package carries Apache-2.0 for weights, upstream attribution and
the separate MIT source license; see the repository's
[license provenance](../../../docs/model-provenance.md).

Manifest SHA-256: `e83fd15c8715c9a7e474afd0830d55b0fe4b25ab61910114f6e36437a2964e37`.
All downloaded package file hashes match the remote manifest and the independent
current-weight snapshot. Packaging is CPU-only: it compares historical saved
reload evidence, not a new inference run on the packaged bytes. The subsequent [complete held-out evaluation](../../full-data-eval-n1-v1/README.md)
now binds new predictions to the same inference-file bytes. Final task-level
evaluation remains pending. No model upload or visibility change
was performed.

The [source evaluation identity](source-evaluation-identity.json) was computed
with the queued evaluator's immutable code, without loading a model. The independent full-data audit
matched it against the evaluation plan, every shard and the actual package
files. This new inference binding does not supply the missing historical
weight digest for the trainer's earlier reload check.

See [execution/copy evidence](../../runtime-checks/checkpoint-package-9b-n1.json)
and the [independent sampled-result audit](../../fullpass-9b-n1/README.md).
