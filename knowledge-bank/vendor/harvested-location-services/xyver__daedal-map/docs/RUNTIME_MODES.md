# Runtime And Research Modes

DaedalMap uses "mode" in two ways. Keeping them separate makes local research
setups easier to reason about.

For the shared-versus-mode-specific engineering contract, see
[RUNTIME_UNIFICATION.md](RUNTIME_UNIFICATION.md).

## Deployment modes

Deployment modes decide where the app runs and reads data:

- `INSTALL_MODE=local`, `RUNTIME_MODE=local`: local app and local `DATA_ROOT`.
- `INSTALL_MODE=local`, `RUNTIME_MODE=cloud`: local app using object storage.
- `INSTALL_MODE=cloud`, `RUNTIME_MODE=cloud`: hosted app and hosted data.

See [LOCAL_AND_HOSTED.md](LOCAL_AND_HOSTED.md) for configuration.

## Interaction modes

Interaction modes decide how the same runtime approaches a question.

### Explore

Explore is discovery-first. It starts from the catalog, identifies relevant
packs and sources, and connects results to the map. Use it when you do not yet
know which source contains the answer or are choosing data for a corpus.

### Research

Research is corpus-first. It starts from the active local corpus or installed
artifacts, then reasons within that bounded source set. Use it when a defined
evidence base, reproducibility, and source scope matter.

Explore and Research share the same source contract. Metric definitions, units,
geographic coverage, time coverage, and provenance should mean the same thing
in both.

### Ops

Ops is watch-first. It centers current conditions, active events, alerts, and
operational snapshots. Use it when freshness matters more than broad historical
discovery.

Ops is not the default for a static academic dataset. A historical event
archive can be explored or placed in a Research corpus without becoming a live
operational feed.

### Tutorial

Tutorial is a user-interface teaching aid, not a separate data contract. It
annotates parts of the map while a user learns the other modes.

## Typical academic workflow

1. Prepare sources and build a local catalog.
2. Use Explore to test ordinary-language discovery.
3. Group related sources with a stable `pack_id`.
4. Create a local corpus from relevant packs.
5. Use Research for bounded analysis and record the corpus with the project.
6. Use Ops only when the project genuinely needs live-watch behavior.

## Shared invariants

All modes should agree on canonical `loc_id`, metric definitions, units,
aggregation rules, temporal bounds, provenance, and map geometry.

A mode changes the starting posture, not the meaning of the data. Contradictory
definitions across modes indicate a runtime or metadata problem, not two valid
truths.

Explore and local Research can use user-controlled data and model keys. Hosted
account, billing, admin, and private-control-plane features are not prerequisites
for the public academic workflow.
