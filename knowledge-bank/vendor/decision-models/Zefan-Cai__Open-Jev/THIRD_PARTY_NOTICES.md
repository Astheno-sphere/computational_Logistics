# Third-party attribution and release boundaries

Open-Jev is independently implemented and is not affiliated with TypeSafe.

- TypeSafe Jev/System One documentation and the public Jev launch inspired the task forms. Links and pinned source revisions are in `docs/public-capabilities.md`. No proprietary RLCD code, weights or private training dataset is included. Publicly viewable evaluation examples have not been assigned a verified general redistribution/training license and are not copied into our training data.
- `achimala/jev-paint` (previously `jevinci`), copyright Anshu Chimala, MIT, inspired the four pixel probability representations. Our request builders, simple mean-color renderer and geometry generator are independently written. We do not bundle its impasto renderer or recorded model-probability fixtures.
- Community projects are attributed in `docs/games.md` and `docs/community.md`. External game code/ROMs/assets are not bundled. Our grid, runner and platformer engines are original simplified environments.
- Qwen model weights and tokenizer files retain the terms of their exact source repositories. The three pinned revisions were each verified as Apache-2.0; [model provenance](docs/model-provenance.md) records the fixed sources, content hashes and attribution. Code licensing here does not relicense weights. Publication of adapters must include the applicable license text, modification notices and a model card referencing the corresponding base revision.
- The exact common Qwen [Apache-2.0 license](third_party/qwen/LICENSE) and [attribution/modification notice](third_party/qwen/README.md) are included for checkpoint packaging. Inference weight bundles use Apache-2.0 and include the repository's MIT source-code license separately; generated-data CC0 declarations do not apply to weights.
- ViZDoom and its bundled scenario assets retain their upstream per-file licenses. They are optional installed dependencies; see `docs/doom-case.md`.
- The Wikispeedia graph and BoolQ auxiliary data retain their source licenses and attribution, recorded by import manifests. They are fetched by data scripts rather than copied into Git.
- Generated geometry, controlled conversations, local game states and local workflow records are marked CC0-1.0 in their provenance. This covers our generated records, not an upstream source or model.

The repository license applies to original code only. Check the manifests and source documentation before redistributing optional data, engines, checkpoints or assets.
