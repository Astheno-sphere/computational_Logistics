# Published Open-Jev 2B and 9B inference packages

Both repositories are public, ungated, and verified through anonymous access.
Each contains 18 release payload files: the unchanged original package under
`package/`, a release model card, licenses, full held-out evaluation evidence,
and a release manifest. Base-model weights and source dataset rows are absent.

| Model | Published commit | Verified payload |
| --- | --- | ---: |
| [Open-Jev-2B](https://huggingface.co/ZefanCai/Open-Jev-2B) | [0c7aa498b1627be8da4acf34c863ff0ee0a92785](https://huggingface.co/ZefanCai/Open-Jev-2B/commit/0c7aa498b1627be8da4acf34c863ff0ee0a92785) | 12,217,529 bytes |
| [Open-Jev-9B](https://huggingface.co/ZefanCai/Open-Jev-9B) | [47e966881e489511c0c7f5633a9e1960a676a551](https://huggingface.co/ZefanCai/Open-Jev-9B/commit/47e966881e489511c0c7f5633a9e1960a676a551) | 25,791,930 bytes |

[preflight.json](preflight.json) records source package, license, checkpoint,
calibration, and evaluation bindings. Independent CPU inspection confirmed all
120/160 adapter tensors and both scalar heads are finite. The source packages
were already local; no cluster access, GPU allocation, or new model inference
was performed for publication.

The [2B](2b/remote-verification.json) and [9B](9b/remote-verification.json)
verification records contain SHA-256 for every payload file downloaded afresh
from its exact uploaded commit. They also check Hub LFS hashes where present,
both release and original package manifests, unchanged remote HEAD, and public
access. The existing `.gitattributes` is recorded separately as Hub metadata.

Each published model card supplies the actual `.[train]` installation command,
`hf download`, and the Open-Jev server checkpoint path ending in
`package/checkpoint`. These are LoRA adapters plus a separate scalar head and
calibration, not standalone merged Qwen models. Their upstream revisions are
fixed in `package/checkpoint/model.json`.

The cards distinguish the original 80,816-row training split from the public
79,116-row redistributable projection, and the full 26,452-row evaluation from
the original 512-test/512-OOD sampled evaluation. Per-file identity links the
published inference artifacts to the completed full-data audit. The source
checkpoint directory and packaged checkpoint directory have different whole
directory hashes because packaging omits the generated adapter README; those
digests are not presented as interchangeable.

The related dataset publication is
[`ZefanCai/Open-Jev` at 341d9338462da1cf56ba57519fb0f3f5258b825f](https://huggingface.co/datasets/ZefanCai/Open-Jev/tree/341d9338462da1cf56ba57519fb0f3f5258b825f).
Its public projection excludes Wiki rows whose archive redistribution terms
were not confirmed. No such source rows are included in either model upload.

## Archived model-card context

`2b/README.md` and `9b/README.md` are exact archived copies of the published
Hugging Face model cards. Their relative `package/`, `evaluation/` and license
links resolve within the corresponding model repository, not this reports
directory. Use the fixed [2B model card](https://huggingface.co/ZefanCai/Open-Jev-2B/blob/0c7aa498b1627be8da4acf34c863ff0ee0a92785/README.md)
and [9B model card](https://huggingface.co/ZefanCai/Open-Jev-9B/blob/47e966881e489511c0c7f5633a9e1960a676a551/README.md).
The public-code release audit verified exact card bytes and every relative
target at those public revisions; the archived cards themselves are unchanged.
