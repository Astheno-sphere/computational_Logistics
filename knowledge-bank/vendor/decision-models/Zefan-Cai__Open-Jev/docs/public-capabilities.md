# Public Jev capability inventory

Source-audit snapshot: 2026-09-19; current local evidence is listed separately
below. This is a source inventory and implementation scope, not a
claim that Open-Jev matches Jev's capability, calibration, speed, or every post
on X. X search is not an exhaustive archive. A readable post proves what its
author said; executable source is stronger evidence for the task contract.
Repository documentation describes the authors' runs, not measurements made by
Open-Jev. Check each local module's tests and reports for actual local results.

## The user's new links

| Link | Verified content | Consequence for Open-Jev |
| --- | --- | --- |
| [achimala/jevinci](https://github.com/achimala/jevinci) | GitHub redirects to [achimala/jev-paint](https://github.com/achimala/jev-paint), a pixel-probability painting app, not a game. Four representations: palette Choice, silhouette Noul, binary RGB Nouls, HSL Choice plus Scores. | Four representations, request batching, an independent mean-color renderer, and geometry controls in [painting.md](painting.md). |
| [Matija Sosic](https://x.com/MatijaSosic/status/2100190746389135772) | The post describes a 45-second explanation of Jev's idea and quotes the launch. The text does not introduce another game or publish a task dataset. | Use the typed-decision concept; no separate verified game to reproduce from this post. The video was not transcribed in this audit. |
| [Harsha Gundala](https://x.com/harshagundal/status/2100044305536889015) | Announces parallel categorical/JSON inference on an M4 Mac, without new training. The linked ecosystem model card is [harshatheg/Qwen-2.5-1B-RLCD](https://huggingface.co/harshatheg/Qwen-2.5-1B-RLCD). Despite its name, its stated underlying model is Qwen2.5-1.5B-Instruct in MLX 4-bit. | Include an untrained model baseline, bounded schema fields, and same-workload autoregressive comparison. The post's 5× and card's 5.6–7× figures are author claims, not our measurements. |

The Harsha card lists fintech fraud routing (4 fields), code-security auditing
(4 fields), a 255-candidate tariff classification, and enterprise support triage
(28 fields). Its Apache-2.0 metadata covers that published project; Qwen weights
retain their upstream terms. Its prefix-prefill/KV-broadcast and candidate-token
scoring differ from Open-Jev's independent candidate-sequence scoring, which
now optionally reuses exact shared token prefixes through a separate
[request-local cache implementation](prefix-caching.md).
Softmax or temperature alone does not demonstrate
empirical calibration. Calling a repository “RLCD” does not disclose TypeSafe's
proprietary RLCD objective.

Post text was read using the public FxTwitter JSON mirror at
`https://api.fxtwitter.com/<account>/status/<id>`; original X URLs above remain
the canonical citations. No video, image, or private query was downloaded or
incorporated into training.

## Official contract and launch demos

The [API](https://docs.typesafe.ai/api) takes `state`, `model`, and a map of
`questions`, and returns `answers`, `model`, and `usage`. The official route is
`POST /v1/systemone`. `state` and question instructions can be text, objects,
or arrays. Choice descriptions may be `null`. Question IDs are bookkeeping and
do not enter the model; Choice names do. Score levels are self-contained
descriptions, with ordered levels mapped back to string-indexed probabilities
and a numerical expectation by software. Noul returns P(yes).

[Current model documentation](https://docs.typesafe.ai/models) says text only;
images, audio, and video require an external conversion to text/structured
fields. Jev does not produce free-form text. The three visible
[launch demos](https://typesafe.ai/blog/introducing-system-one-models-and-jev) are:

1. Customer-context judgments evaluated in parallel. Only the launch question
   name “Churn likelihood level” is directly recovered; the shared playground
   query still requires login. The five public [support fan-out questions](https://docs.typesafe.ai/patterns/fan-out)
   are a related documented example, not a recovered complete launch query.
2. Doom: structured game state to control decisions, with execution in code.
3. Wikiracing: choose a legal outgoing Wikipedia link until the goal is reached.

The four official workflow pages were retrieved with HTTP 200 in this audit;
earlier HTTP 403 notes describe an earlier retrieval, not current availability.
They expose example problems and workflow descriptions, not the full private
training set:

| Official workflow | Inputs | Decisions |
| --- | --- | --- |
| [Customer service](https://evals.typesafe.ai/customer_service) | Conversation, account/ledger, pending proposal, authorization | Potentially multiple SAY, REFUND, FREEZE CARD, SET INTENT, HAND OFF, FLAG FOR REVIEW, CLOSE actions |
| [Security incidents](https://evals.typesafe.ai/security_incidents) | Alert, assets, tickets, registrations, maintenance, permissions | Close, notify, escalate, containment/playbook decisions |
| [Agent trace observability](https://evals.typesafe.ai/agent_trace_observability) | Instructions, messages, tools/results, answer, feedback | No issue, review, filing/routing, escalation |
| [Invoice processing](https://evals.typesafe.ai/invoice_processing) | Invoice, PO, contract, vendor, history, correspondence, delivery, approvals | Pay/schedule/partial pay, request information or approvals, corrections/dispute/fraud/duplicate handling |

Official example records should remain held out when measuring agreement with
that source. No verified general redistribution/training license for the
official eval data was found here. Independent synthetic scenarios can follow
the task form without copying the official examples.

The official [use-case map](https://docs.typesafe.ai/concepts/use-case-map)
also covers classification, detection, rubric scoring, intent/model routing,
semantic search/retrieval/ranking, verification, feature extraction, and
structured extraction. These are compositions of the three primitives, not
additional proprietary output heads. Dynamic candidates, independent fan-out,
confidence gates, hierarchical decisions, and explicit code-owned action sets
are the important reusable interfaces.

## Independently verified game and control projects

The following repositories and READMEs were read directly. Mario, T-Rex, and painting action contracts were additionally inspected at
the implementation-file level. A source-backed adapter can express these
tasks, but completed gameplay requires the environment and a tested policy.

| Project | Model-facing contract | Boundary / source license observed |
| --- | --- | --- |
| [Snake](https://github.com/sorrycc/typesafe-snake) | Legal directions plus code-computed food distance, reachable cells, dead ends → one Choice per tick | Code owns board and deadlines. No repository license detected; implement independently. |
| [Super Mario Bros.](https://github.com/fhshaik/typesafe-mario) | RAM/telemetry JSON → `next_action` Choice, `jump_needed` Noul, `danger` Score | Macros: noop/right/right_jump/right_run/right_run_jump/jump/left. Code owns timing/RAM parser. No repository license detected; no Nintendo ROM redistributed. |
| [T-Rex Runner](https://github.com/joshlarsen/jev-t-rex-runner) | Obstacle kind/group/flight path and motion/speed → maneuver Choice and short/full jump-profile Choice | Browser owns exact jump launch/duck duration/collision geometry. BSD-3-Clause. |
| [Doom / PROMPT FPS](https://github.com/lukaske/jev-doom-agent) | Health/armor/ammo, coordinates, visible monsters/pickups → tactical Choice macro | Chocolate Doom WASM and local motor controller. Chocolate Doom GPL-2.0-or-later; Freedoom BSD content; check per-file notices, not one assumed repository-wide license. |
| [JevScape / RuneScape](https://github.com/Skyvern-AI/jevscape) | Player status, HP/damage, target, XP timing, server message/history → next action, this-tick action, next poll interval | About 50 catalog actions: fish/chop/mine/cook/fight/buy/sell/drop/walk/dialog/eat. Depends on RuneBench/rs-sdk; no top-level license detected. |
| [Pokémon Red](https://github.com/valentynkit/jev-plays-pokemon-red) | RAM-derived snapshot and legal moves → branch/action decisions, battle faint prediction | PyBoy and deterministic route/damage arithmetic. MIT code; user supplies lawful ROM; full game completion is not established by the opening-route demo. |
| [HEIST//ONE](https://github.com/AbdelStark/heist-one) | Per-guard local observations → threat Noul, suspicion Score, tactical-intent Choice, observed-target Choice | Deterministic museum simulation owns visibility/physics/actions. MIT game code and original media; dependencies retain their own licenses. |
| [Jev drone](https://github.com/RomanSlack/jev-drone) | Structured obstacle/target scene → hold_course/gap_left/gap_right/climb/brake/reacquire Choice, risk Score, target-lost Noul | MuJoCo perception and flight controller are code; reflex layer can veto. Repository license must be checked before importing code/assets. This is simulation, not a real aircraft result. |

Mario observation groups include `player`, `trajectory`, `hazard`, `terrain`,
`reaction_timing`, `recent_control`, and `episode`. T-Rex sends
`current_speed`, `speed_mode`, `dinosaur_motion_when_observed`, and
`target_obstacle` (`kind`, `group_size`, `flight_path`), then uses only the
jump-profile result when the maneuver is jump. Timing arithmetic is outside
the model in both projects.

Pinned revisions inspected:

| Repository | Commit |
| --- | --- |
| achimala/jev-paint | `ecf9c48d290e086bde790d6e24b93324667155e9` |
| sorrycc/typesafe-snake | `8bf3f7c261ad35ece3345a02d21ba638ddfaf87f` |
| fhshaik/typesafe-mario | `ca22449ed187118d19326d1f54b01b6636578aa4` |
| joshlarsen/jev-t-rex-runner | `49682008948c8715fd5a2824d33284193d6eab89` |
| lukaske/jev-doom-agent | `318c32a24851444c1170bf083671c38723f3a35a` |
| Skyvern-AI/jevscape | `8fe4d37349fc6a8d03ac1c918302eef254bb56c3` |
| valentynkit/jev-plays-pokemon-red | `cbe5387aeb6c7b3ef6b1f67d4a95e284aee3b0af` |
| AbdelStark/heist-one | `632c9a55a1e5eb2cbf0b9f87db575f0b5eb36e8c` |
| RomanSlack/jev-drone | `cbeb53ce4f17a06ea490ae43effcdad231143610` |

## Other concrete integration surfaces

[Browser Use Jev Ultrafast](https://github.com/browser-use/jev-ultrafast), MIT,
commit `1231850a0bf1a0c0341fe408ef1668dbbfdfac46`, gives Jev a visible DOM element
table and selects an operation (`CLICK`, `TYPE_TEXT`, `SELECT`, `SCROLL_UP`,
`SCROLL_DOWN`, `WAIT`, `DONE`, `BLOCKED`) alongside compatible targets in one
fan-out. Another model writes text when needed. Browser code resolves observed
node IDs, rejects stale targets, and verifies task completion. A typed action
adapter alone is not a completed arbitrary-browser agent.

[PlayJev](https://github.com/OmniJev/PlayJev), Apache-2.0 project at
`2d7a0280841e3244a299c9c640efc8cefc46d476`, is a separate Qwen3.5-0.8B visual
model with ten games (Tetris, Snake, Pacman, racer, Space Invaders, Sokoban,
Infinite Mario, Floppy Bird, Breakout, 2048). It is not TypeSafe Jev: pixel input
is a community extension. Its README supplies a teacher/data/DAgger regeneration
pipeline; environment assets and weights need their own provenance audit before
reuse. Its 43 ms/model-score claims are not Open-Jev measurements.

Community indexes used for discovery:
[Anil-matcha](https://github.com/Anil-matcha/awesome-jev-by-typesafe),
[cobanov](https://github.com/cobanov/awesome-jev), and
[AnotiaWang](https://github.com/AnotiaWang/awesome-jev). They also link household
automation, semantic SQL, dataset filtering, code review, sponsor detection,
MCP/agent tools, and trading gates. These entries are discovery leads; they
were not all independently run or source-audited here. They mostly reuse the
same typed decision boundary with different application executors.

## Release evidence rule

Track four different completion levels: **request builder**, **executable
environment**, **trained policy**, and **measured held-out outcome**. Passing
schema checks proves only the first. A scripted/oracle policy proves the
environment but not the learned policy. A checkpoint answering a request proves
inference but not task success. Report local latency and task quality only from
saved runs, and retain baselines, seeds, model version, and fallback counts.

## Current Open-Jev implementation evidence

The [project website](https://zefan-cai.github.io/open-jev/) is an outcome-selected
showcase of reviewed successful saved examples and explicit interface
walkthroughs; the current catalog owns the displayed counts and coverage.
Failed and unverified videos are excluded from publication, while original
evaluation predictions, failed trajectories and metrics remain unchanged.
The game overview contains complete successful original pilot episodes for
Doom, T-Rex and Wiki. Doom uses native ViZDoom/Freedoom frames from exact replay
of all 11 saved decisions; observations, rewards and terminal flags match the
trajectory. Rendering and replay make no new model inference calls. The
[video documentation](website-and-videos.md) describes provenance, selection
and historical audits. This showcase is not a representative success-rate
measurement, final-model gameplay result or fresh-policy run.

[Prefix caching](prefix-caching.md) now reuses the request's and each question's
shared token prefixes before evaluating candidate suffixes. It preserves
branch-local KV, convolution and recurrent state and is explicitly enabled with
`--prefix-cache`; the default remains uncached. The
[CPU verification](../reports/runtime-checks/prefix-cache-cpu.json) uses tiny
real Qwen hybrid models and LoRA, not the full trained checkpoints. BF16
segmentation differences remain. Real-checkpoint GPU A/B and any resulting
latency claim are pending.

Final-model JF100, workflow, game, browser and drone results remain pending
under the [final-checkpoint evaluation schedule](final-checkpoint-evaluation.md).
Public videos, prepared task contracts and CPU cache verification do not close
those evaluation gaps or provide the missing community executors.

## Additional evaluation and stress sources

The following public project documentation was surveyed on 2026-09-19. Numbers
in those repositories remain author-reported and were not rerun in this audit.
Only task categories and evaluation methods inform the coverage plan; their
benchmark records are not imported into training.

| Source | What it tests | Implication for our coverage |
| --- | --- | --- |
| [Official Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13) | Counting/numbers, date comparison, indirection, irrelevant context, adversarial content, contradictory rubrics, negation/structural consistency | Add explicit reasoning controls and measure invariance separately; continue doing application arithmetic in code where appropriate. |
| [AbdelStark/jev-benchmarks](https://github.com/AbdelStark/jev-benchmarks) | BTZSC classification: AG News, Banking77 subset, emotion; accuracy, Brier, error-budget coverage, paired bootstrap intervals | Our synthetic cases do not substitute for held-out real text classification/calibration tests. Apache-2.0 harness; datasets retain their own terms. |
| [Korean sample check](https://github.com/mahlernim/jev-korean-benchmark) | Belebele reading, PAWS-X paraphrase, Korean/English instruction conditions, sentence-order reversal; separate medical datasets | Matched-language reading/paraphrase and order invariance remain gaps. Different medical exams cannot isolate language effects. No repository license detected. |
| [Janus](https://github.com/FirasSX914/Janus) | Banking77/Web of Science routing studies; gold-label accuracy versus reference-model agreement, selective routing | Learn thresholds on a separate calibration split and report when routing fails to improve utility. MIT harness. |
| [jevcal](https://github.com/abhixhek/jevcal) | Per-question thresholds, held-out accepted accuracy/coverage, row-level escalation; bundled demo is simulated | Do not relabel simulator outputs as Jev results or choose one universal confidence threshold. MIT tool. |
| [typesafe-ai-benchmark](https://github.com/iammrduncan/typesafe-ai-benchmark) | Tickets, guardrails, approvals, scoring, home automation, routing, driving; compact constrained-output comparator | Covers application correctness and stateful outcomes. Its compact-output comparison does not ask the LLM to emit full probabilities, so it addresses a different latency contract from ours. MIT project. |
| [openjev-sglang](https://github.com/ekzhang/openjev-sglang) | API-compatible selected-token scoring, radix caching, batched prefill and systems smoke checks | Useful systems comparison; not evidence of calibrated task quality or TypeSafe RLCD reproduction. No repository license detected. |

The user-selected [jev-frontier-100](https://github.com/softpudding/jev-frontier-100)
is an evaluation target, not a training source. The independent generator in
[reasoning-data.md](reasoning-data.md) covers formal logic, relations, arithmetic,
temporal reasoning, code semantics, algorithms, and evidence integration without
reading or transforming its questions/answers. New controls stay in a separate
corpus and do not mutate an already-running training mixture.

Remaining training/evaluation gaps include realistic multilingual text and
paraphrase, longer contexts with distractors, broad real code, human disagreement
and uncertainty labels, real operational support/financial records, and complete
stateful environments for the community interfaces. Request-builder coverage
must not be presented as trained coverage of those domains.
