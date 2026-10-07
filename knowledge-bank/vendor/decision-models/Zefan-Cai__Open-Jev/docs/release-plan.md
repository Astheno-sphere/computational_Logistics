# Two-day open-source preparation

User target: September 21, 2026, America/Los_Angeles. Development repository:
https://github.com/Zefan-Cai/Open-Jev-Dev . The repository is currently private.

## Scope and acceptance

1. Source-backed coverage of the launch demos, the user's three new links, four
   official workflows and verified community task families. Keep unknown claims
   marked unknown; X is not an exhaustive capability catalog.
2. Runnable local API, Python client, browser task lab, four painting modes,
   game loops/replay, workflow data/actions, cookbook and community adapters.
   Requests must execute on actual requested Qwen checkpoints, with no hidden
   oracle fallback. External executors are explicitly listed.
3. Reproducible data manifests, train/calibration/test isolation and exact model
   revisions. The 2B/9B release-v2 runs and fresh 27B browser/drone expansion run
   must record raw baseline/trained predictions, calibration, checkpoint reload
   and held-out metrics; their different training mixtures remain explicit.
4. Report per-workflow complete action-set metrics, game closed-loop outcomes,
   geometry accuracy and same-workload latency. Failures/regressions stay visible.
   API-valid responses alone do not pass a task-quality claim.
5. Clean installation/test instructions, license/provenance, model cards and
   reviewed artifacts. Publish measured support levels, rather than calling all
   models production-ready. Public release must not include credentials,
   private official examples, ROMs or unsupported benchmark claims.

## Work sequence

- First day: source inventory, repository migration, task forms, local environments,
  data generation, server and independent implementation tests.
- Second day: train/evaluate all three sizes, audit task-level failures, fix the
  binding bottlenecks, reproduce launch commands and prepare release artifacts.

The durable current status is `state/auto_research/progress.json`; run metadata
and evidence, rather than this plan, determine completion. Large-model Wiki
regression is a known unresolved issue. Full commercial workflow simulations
and complete executors for every third-party game are not implemented.
Their status must remain explicit if the first release ships without them.

[Request-local prefix caching](prefix-caching.md) is implemented behind
`--prefix-cache` and remains off by default. It reuses shared context/question
tokens and forks independent attention, convolution and recurrent state for
candidate suffixes. Verification so far uses tiny real hybrid models on CPU;
BF16 differences remain, and real-checkpoint GPU parity/latency A/B is pending.
Do not infer a GPU speedup or change the pinned final-evaluation mode from the
CPU token-reuse results.

The [website showcase](https://zefan-cai.github.io/open-jev/) selects reviewed
successful saved examples and explicit interface walkthroughs. Its game
overview includes complete pilot episodes for native ViZDoom/Freedoom, T-Rex
and Wiki, replayed without fresh inference. Failed or unverified videos are
excluded from publication; original predictions, failed trajectories and
metrics remain in the evaluation reports. The
[video documentation](website-and-videos.md) describes curation and separates
current assets from historical deployment audits. Selection by outcome is not
a success-rate estimate and does not establish gameplay quality for the later
final checkpoints.

The latest user-directed [four-card schedule](four-gpu-handoff.md) supersedes
the extra 2B expansion pilot: finish 2B/9B, evaluate their full held-out data on
four cards, then train a fresh expanded-data 27B on those four cards. Its
supervisor and recorded status own the transition; do not launch competing jobs.

Use the offline [checkpoint packager](checkpoint-package.md) after a selected
run completes. It prepares an inference bundle with its own model/data identity,
verified saved metrics, model card and licenses. Packaging does not publish the
bundle or replace full held-out and task-level evaluation. The 2B/9B release-v2
runs and new 27B browser/drone expansion use different training mixtures; label
that difference in any comparison.

The [final-checkpoint evaluation commands](final-checkpoint-evaluation.md)
reuse the existing service suite after the four-card training phase releases
the GPUs. They distinguish the full 2B/9B data evaluation from sampled workflow,
browser/drone and game checks, and the pinned JF100 holdout.
The remaining final-suite gates are completed 27B calibration, checkpoint reload
and process cleanup, its full 40,281-row expansion evaluation, and then the
serial final-checkpoint task suite. Published pilot replays and CPU cache tests
do not satisfy those gates; keep their results and labels separate.
