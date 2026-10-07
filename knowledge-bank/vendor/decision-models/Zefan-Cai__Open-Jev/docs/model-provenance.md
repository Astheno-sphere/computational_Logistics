# Model provenance and license evidence

Audit date: 2026-09-20 UTC. Local code inspected at
`6f7e803f708a8b6b2f26ac059b3825a4d0c1611a`.

**All three exact Qwen revisions used by Open-Jev publish Apache License 2.0.**
This was checked separately against each revision's README, `LICENSE`, and
Hugging Face revision metadata. It was not inferred from another Qwen model or
from the model family. This document records provenance and packaging
requirements; it is not a trained-model card or a statement that a training run,
weight upload, or public release has completed.

## Exact starting weights

“Base” here means the upstream weights from which Open-Jev initializes. The
three selected repositories describe their artifacts as **post-trained models**.
They are not the similarly named `Qwen3.5-2B-Base` or `Qwen3.5-9B-Base`
repositories. Those names occur as ancestor metadata in the 2B/9B cards, but
their separate repositories and licenses were not audited here.

| Open-Jev tag | Exact upstream model | Revision | Verified repository license |
| --- | --- | --- | --- |
| 2B | `Qwen/Qwen3.5-2B` | `15852e8c16360a2fea060d615a32b45270f8a8fc` | Apache-2.0 |
| 9B | `Qwen/Qwen3.5-9B` | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | Apache-2.0 |
| 27B | `Qwen/Qwen3.8-27B` | `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` | Apache-2.0 |

These are the revisions in [launch_expansion.py](../scripts/launch_expansion.py).
For each revision, the README front matter says `license: apache-2.0`, the API
metadata reports that same `cardData.license`, and the returned API `sha` equals
the full revision above. The top-level API `license` field is absent; it was
not used as evidence. All nine requests returned HTTP 200.

The 2B/9B README `license_link` fields point at mutable `main` URLs. The license
evidence below instead uses each exact revision. The three retrieved license
files are byte-identical and include the notice **“Copyright 2026 Alibaba
Cloud”**. Their contents are the Apache 2.0 terms, sections 1–9 and the filled-in
appendix notice. None of the three returned file inventories lists a `NOTICE`
file. This absence in these inventories does not authorize dropping notices
from any additional files included in a later package.

## Retrieved sources and content hashes

The SHA-256 values below cover the original response bytes, including line
endings. Each source URL specifies the full revision. The API response includes
repository metadata that can change independently of a revision, so its hash
identifies this retrieval snapshot; the pinned README and `LICENSE` are the
primary license evidence.

| Model | Retrieved file / exact URL | SHA-256 |
| --- | --- | --- |
| 2B | [README.md](https://huggingface.co/Qwen/Qwen3.5-2B/raw/15852e8c16360a2fea060d615a32b45270f8a8fc/README.md) | `c0e83a849c776e6fa843d011f023132d942a0f0140d903205bf1c363adad2275` |
| 2B | [LICENSE](https://huggingface.co/Qwen/Qwen3.5-2B/raw/15852e8c16360a2fea060d615a32b45270f8a8fc/LICENSE) | `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a` |
| 2B | [Revision metadata](https://huggingface.co/api/models/Qwen/Qwen3.5-2B/revision/15852e8c16360a2fea060d615a32b45270f8a8fc) | `b816dbf0565d8890e1e6c0350a3edfb649cd074156af8a0b2a0ed223ba30785b` |
| 9B | [README.md](https://huggingface.co/Qwen/Qwen3.5-9B/raw/c202236235762e1c871ad0ccb60c8ee5ba337b9a/README.md) | `c5f5a8c2dddab69cfbf05279235aa5fddb137939a06539c4c7637aa900fef6d0` |
| 9B | [LICENSE](https://huggingface.co/Qwen/Qwen3.5-9B/raw/c202236235762e1c871ad0ccb60c8ee5ba337b9a/LICENSE) | `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a` |
| 9B | [Revision metadata](https://huggingface.co/api/models/Qwen/Qwen3.5-9B/revision/c202236235762e1c871ad0ccb60c8ee5ba337b9a) | `851a44da841b9d5b9f5c92d7235c147ae74a49bc1e2b0a628c709b8de7a3f6e1` |
| 27B | [README.md](https://huggingface.co/Qwen/Qwen3.8-27B/raw/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/README.md) | `57e4bdb258ee1a7d2635c5174ebd4e56abe392505cdb5f8bbb356b0dc4293641` |
| 27B | [LICENSE](https://huggingface.co/Qwen/Qwen3.8-27B/raw/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/LICENSE) | `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a` |
| 27B | [Revision metadata](https://huggingface.co/api/models/Qwen/Qwen3.8-27B/revision/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0) | `436567d87776402b963278013213b3886e217f570b80ec17550e276b16b3fb61` |

For example, retrieve the same pinned license without using a mutable branch:

```bash
curl --fail --location \
  https://huggingface.co/Qwen/Qwen3.5-2B/raw/15852e8c16360a2fea060d615a32b45270f8a8fc/LICENSE \
  --output Qwen3.5-2B-LICENSE
python -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('Qwen3.5-2B-LICENSE').read_bytes()).hexdigest())"
```

## What the verified license requires

The following requirements come from the retrieved license text itself; the
links above retain the complete terms.

- **Section 4(a):** give recipients of the work or a derivative work a copy of
  the Apache 2.0 license. A model card containing only a license identifier or
  external link is not the same as bundling that license text.
- **Section 4(b):** modified files must carry prominent notices stating that
  they were changed. A redistributed modified model package should identify
  the upstream revision and the Open-Jev modifications and mark affected
  artifacts, rather than presenting them as untouched Qwen files.
- **Section 4(c):** retain applicable copyright, patent, trademark, and
  attribution notices in distributed derivative source. Preserve the observed
  Alibaba Cloud notice when packaging these upstream artifacts.
- **Section 4(d):** if an included upstream work supplies a `NOTICE` file,
  preserve its applicable attribution notices in one of the locations allowed
  by that section. No `NOTICE` is listed in the three inspected repository
  inventories, but notices from additional bundled dependencies need their own
  check.
- **Section 6:** the license does not grant general trademark rights. Naming
  the Qwen origin and upstream revision is appropriate attribution, not a claim
  of endorsement by Alibaba Cloud or the Qwen Team.

Sections 2–3 grant copyright and specified patent permissions, including
modification and redistribution, subject to the terms and the patent
termination condition. Sections 7–9 retain the warranty/liability conditions.
The retrieved license text contains no added noncommercial-only restriction.
The 2B card's discussion of intended prototyping/research uses is separate from
the actual Apache license grant.

All three model cards say: “If you find our work helpful, feel free to give us
a cite.” This is an attribution request in the card, not an additional citation
condition written into the retrieved Apache license. Preserve the source
credit in release documentation. The cards provide these citations:

- The pinned 2B and 9B cards cite **Qwen Team, Qwen3.5: Towards Native Multimodal
  Agents**, February 2026, <https://qwen.ai/blog?id=qwen3.5>.
- The pinned 27B card cites **Qwen Team, Qwen3.8-Max: A New Bar for Coding and
  Cowork**, August 2026, <https://qwen.ai/blog?id=qwen3.8>. This title is copied
  from that card's citation; it is not a claim that the 27B weights are the Max
  hosted model.

## Which artifacts have which provenance

| Artifact | Provenance and current license evidence |
| --- | --- |
| Original Open-Jev Python/JavaScript code, request builders, clients, original tests and documentation | Repository [MIT license](../LICENSE), copyright 2026 Open-Jev contributors. Copies/substantial portions retain its copyright and permission notice. |
| Independently written task adapters such as `jev/community.py`, `jev/recipes.py`, and the local case generators | Original repository code under MIT; public task ideas and external integrations are attributed in [third-party notices](../THIRD_PARTY_NOTICES.md). A task adapter is code, not a licensed copy of TypeSafe weights or private RLCD. |
| Qwen safetensors, tokenizer files, configuration files and templates obtained from the three pinned repositories | Upstream model artifacts published under the corresponding verified Apache-2.0 declaration and `LICENSE`; the repository MIT file does not relicense them. Preserve any applicable per-file notices when redistributing them. |
| Generated `checkpoint/adapter/` LoRA files, `checkpoint/head.pt`, `model.json`, and `temperature.json` | Open-Jev training products tied to a Qwen base revision. No release-specific trained-weight license declaration or completed distribution package was verified in this audit. They must not be assumed MIT or CC0 merely because the code or some training records use those licenses. |
| Optional third-party runtime libraries, datasets, game engines and assets | Their own licenses and notices; not covered by this three-model audit or relicensed by either MIT or the Qwen license. |

[DecisionModel](../jev/model.py) downloads the tokenizer and complete source
model using the explicit revision, retains the language-model backbone, and
initializes its scalar head from the difference between the upstream `Yes` and
`No` output-embedding rows. Consequently, `head.pt` is not an independently
random-initialized weight artifact. With LoRA enabled, `save()` writes an
adapter directory, `head.pt`, and `model.json`; [training](../jev/train.py) adds
`temperature.json`. The serving checkpoint reloads the pinned upstream model
before applying those saved parameters.

For redistribution, preserve the Qwen origin and Apache conditions in a bundle
containing upstream-derived parameters, and explicitly state the license chosen
for new contributions. The current save routine does not itself assemble the
base `LICENSE`, attribution/change notices, and a release-specific model card.
That packaging remains work for the actual chosen release artifact. This audit
does not assign a new license to learned weights or treat a dataset's CC0
marker as a license grant for model weights.

The subsequent [checkpoint packaging tool](checkpoint-package.md) applies
Apache-2.0 to inference weight bundles, carries the exact upstream license and
attribution/modification notice, and includes the MIT source license separately.
It prepares a model card from a completed run's own evidence. This tooling is
separate from the original source-license audit above; an uncompleted run still
has no release package, and adding the tool does not publish any checkpoint.

On September 20, the completed full-pass runs produced local
[2B](../reports/checkpoint-packages/2b-fullpass-v1/README.md) and
[9B inference packages](../reports/checkpoint-packages/9b-fullpass-v1/README.md).
Their licenses, model cards, provenance and file hashes were checked and archived;
the adapter/head files are retained outside Git. This subsequent packaging does
not extend the original upstream-source audit or imply a model upload.

## Verification limits

The source license declarations and notices above are verified; a complete
weight-file integrity audit, all per-file tokenizer/template notices, and the
provenance/license chain of ancestor training data or separate `-Base`
repositories were not independently verified here. No safetensors were
downloaded or inspected during this audit. The inspected local Git file list
contained no tracked `.safetensors`, `.bin`, `.pt`, `.pth`, tokenizer, or adapter
weight files; research artifacts on another filesystem are not thereby
published.

During the original source audit, no model was uploaded, no repository visibility was changed, and no training
completion or benchmark-parity claim was created. Use an exact artifact
manifest and its actual measured results for each release-specific model card;
the subsequent 2B and 9B packages are linked above.
