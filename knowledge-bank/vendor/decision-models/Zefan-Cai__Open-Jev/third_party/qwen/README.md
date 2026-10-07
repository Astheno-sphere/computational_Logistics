# Qwen attribution and license

Copyright 2026 Alibaba Cloud.

The accompanying `LICENSE` is the exact Apache License 2.0 text retrieved from
[Qwen3.5-2B revision 15852e8](https://huggingface.co/Qwen/Qwen3.5-2B/raw/15852e8c16360a2fea060d615a32b45270f8a8fc/LICENSE).
Its SHA-256 is
`bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a`.
The same bytes were independently verified for all three selected revisions:

| Upstream model | Fixed revision |
| --- | --- |
| Qwen/Qwen3.5-2B | `15852e8c16360a2fea060d615a32b45270f8a8fc` |
| Qwen/Qwen3.5-9B | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` |
| Qwen/Qwen3.8-27B | `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` |

See [the source audit](https://github.com/Zefan-Cai/Open-Jev-Dev/blob/main/docs/model-provenance.md) for the fixed README,
license and revision-API evidence. The inspected inventories contain no
upstream `NOTICE` file; notices in additional bundled artifacts still apply.

Open-Jev modifies the upstream model by training LoRA adapters and a scalar
decision head, initially derived from the upstream Yes-minus-No embedding
rows. Its published inference artifacts require the exact corresponding
upstream weights and the Open-Jev loader. They are not unmodified Qwen models,
standard text-generation checkpoints, or a reproduction of private Jev weights.

The checkpoint packaging tool applies Apache-2.0 to its inference weight
package and retains the upstream copyright and terms. Original Open-Jev source
code remains under the repository MIT license, which is included separately
when packaging. The generated data's CC0 markers do not license model weights.
No checkpoint has been published merely by adding this notice or the packaging
tool; an actual package must name its model revision, training run and measured
results. No endorsement by Alibaba Cloud, the Qwen Team or TypeSafe is implied.
