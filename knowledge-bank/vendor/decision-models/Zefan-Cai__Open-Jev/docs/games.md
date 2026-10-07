# Game decisions and closed-loop evaluation

Open-Jev accepts the same **observed state → typed questions → action** pattern used by public Jev game demos. `jev.games` supplies a reusable loop with changing legal candidates, terminal handling, per-step latency, saved traces and deterministic action replay. It never substitutes a teacher after a model or network error.

| Game | Available here | Boundary |
|---|---|---|
| Snake | Clean-room grid engine; random/model/heuristic rollouts; Choice and collision Noul training data | A local grid version; no browser UI or claim of matching the community game's physics |
| Wikiracing | Actual closed-loop navigation on a supplied directed graph | Fixed graph, title-only input, sampled candidate sets; no live Wikipedia browser |
| Doom | Headless ViZDoom basic scenario; legacy combined Choice or explicitly selected training-aligned three-head control | Optional ViZDoom 1.2.4 and its assets; not a full campaign or image-input agent |
| Mario-style | Original local tile platformer, plus a RAM-derived external adapter with controller Choice, jump Noul, danger Score | The local game has no NES assets, emulator or enemies; playing the original requires an external emulator/ROM and RAM extraction |
| T-Rex-style | Original local box-physics runner, plus the public browser-state adapter with maneuver/jump-profile Choices | Local physics differ from Chrome/source physics; original browser integration and launch timing remain external |
| Tic-tac-toe | Complete local engine and exact minimax data | An extra validation task, not a claim that the linked Jev demos included it |

## Interactive v1.1 game arcade

[Open the game arcade](https://zefan-cai.github.io/open-jev/games/) to choose moves in Snake, tic-tac-toe, the local Box Runner and Tile Platformer, then compare with saved Open-Jev-27B-v1.1 decisions. Each family has four original synthetic CC0 snapshots. All 74 candidate probabilities are retained, together with three model/reference disagreements.

These 16 snapshots come from the completed internal Test/OOD evaluation. They are independent records, not a continuous game or new inference session. The board illustrations reconstruct the supplied state; choosing a move does not run the model or change its saved probabilities. The next case is another recorded state. The selection is illustrative and does not estimate game accuracy or win rate. Snake's reference is a heuristic; tic-tac-toe can have multiple optimal moves. Box Runner and Tile Platformer use the original local simplified rules described below.

[Evidence and source identities](../site/games/evidence.json) · [Exact public source records](../site/games/source-records.jsonl) · [Verification](../site/games/evidence-verification.json)

## Run without a GPU

Run these commands from the repository root with Python 3.10+. The policy is required so baseline results cannot be mistaken for model results.

```bash
python -m jev.game_cli play snake --policy random --seed 42 --episodes 3 --output runs/games/snake-random.json
python -m jev.game_cli play snake --policy teacher --seed 42 --max-steps 100 --output runs/games/snake-teacher.json
python -m jev.game_cli replay runs/games/snake-teacher.json

python -m jev.game_cli play tic_tac_toe --policy teacher --output runs/games/tictactoe-minimax.json
python -m jev.game_cli replay runs/games/tictactoe-minimax.json

python -m jev.game_cli play wikiracing --policy teacher --graph examples/games/wiki-graph.json --source Computer --target Physics --output runs/games/wiki-oracle.json
python -m jev.game_cli replay runs/games/wiki-oracle.json --graph examples/games/wiki-graph.json

python -m jev.game_cli play trex_runner --policy teacher --obstacles 12 --output runs/games/trex-oracle.json
python -m jev.game_cli replay runs/games/trex-oracle.json
python -m jev.game_cli play tile_platformer --policy teacher --output runs/games/platformer-oracle.json
python -m jev.game_cli replay runs/games/platformer-oracle.json
```

`examples/games/wiki-graph.json` is a tiny synthetic integration fixture. For the real frozen Wikispeedia graph, first run the data recipe in [wikiracing-case.md](wikiracing-case.md), then pass `--graph data/wikiracing/graph.json` and actual article endpoints. Candidate sampling uses only the current page, outlinks and seed. Model requests exclude BFS distances, expert paths and the hidden graph. The explicitly selected full-graph oracle has privileged information and can still fail if a necessary outgoing edge is absent from a sampled shortlist.

The Snake teacher uses visible-state BFS and flood fill: avoid immediate collision, prefer reachable food at shorter distance, then prefer more open space. It freezes the remaining body while searching, so it is a heuristic rather than a guarantee of future survival. Wall/self-collision controls remain offered candidates: an accepted direction can be a fatal choice. Only immediate reversal is disallowed by the engine. Tail cells vacate unless food is eaten.

Tic-tac-toe uses one policy for both sides; its self-play result is a consistency test, not a win rate against an independent opponent. Snake `success` means filling the entire board; `food_collected` and `collision` are more informative for bounded episodes. A run ending at `max_steps` is truncated, not a completed game. Wikiracing dead ends stop as `no_legal_actions`.

`trex_runner` executes one encountered obstacle per decision. It simulates axis-aligned boxes in substeps, with a controller that places the chosen jump's apex at the middle of the obstacle crossing. Its combined candidates are `jump_short`, `jump_full`, `duck`, `keep_running`. The separate external adapter retains the source demo's two-question contract. The local teacher simulates the disclosed physics for this one obstacle; future obstacles are absent from the observation. Ten seeded 20-obstacle teacher runs and their replays are checked by tests; these are engine/oracle checks, not learned-model scores.

`tile_platformer` is an original text-state game with gaps, solid columns and a flag. It uses the seven Mario-style macros, one/two-tile horizontal movement, and a disclosed four-tick jump arc. The full terrain is visible, and its BFS teacher searches only this simplified physics. There are no sprites, enemies, momentum, ROMs or NES timing. Five seeded teacher completions and replays are tested. Both local games accept `--policy http` through exactly the same loop as Snake; API compatibility does not imply trained gameplay competence.

## Run a checkpoint through HTTP

Start the Open-Jev model server, then use its inference URL:

```bash
python -m jev.game_cli play snake --policy http --url http://127.0.0.1:8791/v1/inference --seed 42 --max-steps 20 --output runs/games/snake-model.json
python -m jev.game_cli replay runs/games/snake-model.json
```

The request is `POST {"state": ..., "questions": {"action": {"type": "choice", "instructions": ..., "criteria": {"legal_action": null}}}}`. The response must contain `answers.action` with `type`, a legal `choice`, and a normalized probability for every offered action. An illegal move, incomplete response, timeout or server error fails the run. If authentication is configured, the client reads `OPEN_JEV_API_KEY`, or the environment variable named by `--api-key-env`; credentials never enter traces.

Every recorded step contains the visible request, typed answer, selected action, resulting observation/reward, terminal flag and measured decision latency. Replay re-executes recorded actions and checks transitions and final outcomes without querying a model. Replay reproducibility demonstrates engine consistency, not model quality. The fake HTTP server in the unit tests intentionally picks a losing move to verify that the loop obeys the model instead of calling an oracle.

### Compare a real service with separate baselines

```bash
python -m scripts.evaluate_game_service \
  --endpoint http://127.0.0.1:8791/v1/inference \
  --seeds 42,43,44 --max-steps 40 \
  --expected-model Qwen/Qwen3.5-2B \
  --output-dir runs/game-eval-2b
```

This runs Snake, the local T-Rex runner, the local tile platformer and the tiny Wiki example graph. Each policy starts from the same freshly reset game/seed: learned HTTP, seeded random, and the separately selected teacher. Add `--include-doom` for optional ViZDoom, or narrow the list with `--games snake trex_runner`. Use a fresh output directory for every checkpoint/run. The script never loads a checkpoint itself or calls a teacher after a model failure.

`configuration.json` records the protocol; `trajectories/` holds every completed or failed episode, including partial transitions, pending requests and returned response JSON; `report.json` is updated after each attempt. Response JSON is parsed and reserialized inside a string so malformed values can be retained for diagnosis; it is not a byte-for-byte HTTP capture. Accepted model methods are the actual LoRA decision head or pretrained Yes-minus-No scorer. Missing/mismatched model metadata, illegal actions, bad probabilities, HTTP errors, or a model/calibration/artifact identity change invalidate that episode. The command exits nonzero if any episode failed. Failed episodes never contribute native successes, reward means or latency means; their error counts and partial diagnostics remain visible.

Reports keep each game's native result (food, obstacles cleared, progress, path or Doom engine reward), terminal/truncated/dead-end/error counts, paired initial-state hashes and verified service identity. Model decision latency measures the HTTP round trip; random/teacher timing measures local code. Environment transition/observation latency is recorded separately. Teacher agreement is not reported as action accuracy or treated as a win label.

These short seeded runs measure integration and bounded behavior, not official-game competence or a guaranteed training holdout. In particular, default seeds 42–44 overlap seeds used by our starter data generators, and the Wiki fixture is intentionally tiny. Choosing new seeds alone does not guarantee an unseen terrain or observation. Native success-rate fields state their valid-outcome denominator, alongside all attempted/error counts; Doom has no invented success threshold.

## Mario and T-Rex external adapters

Generate ready-to-submit request JSON from the checked-in **synthetic** observation examples:

```bash
python -m jev.game_cli request mario examples/games/mario-state.json --output runs/games/mario-request.json
python -m jev.game_cli request trex examples/games/trex-state.json --output runs/games/trex-request.json
curl --fail-with-body http://127.0.0.1:8791/v1/inference -H 'Content-Type: application/json' --data-binary @runs/games/mario-request.json
```

For live integration, call `mario_request(snapshot, legal_actions)` or `trex_request(browser_state)`, send the result with `HTTPPolicy.infer`, and apply the returned macros in your own engine. Mario supports `noop`, `right`, `right_jump`, `right_run`, `right_run_jump`, `jump`, `left`. Supply the subset available on that turn. Dead or stage-cleared episodes are rejected. The supplied state may include `level`, `player`, `terrain`, `trajectory`, `hazard`, `reaction_timing`, `recent_control` and `episode`; the adapter consumes prepared observations, not raw RAM bytes.

T-Rex consumes the public browser's `speed`, `speedMode`, `dinosaurMotion` and `obstacle.{kind,group,flightPath}` shape. It returns questions named `maneuver` (`jump`, `duck`, `keep_running`) and `jump_profile` (`short`, `full`). Cacti must be ground hazards. A short jump is appropriate only for one small cactus under the stated policy. The observation's current motion is transient; deciding a future maneuver does not imply applying it immediately. Exact launch timing and geometry remain the external controller's job.

## Doom optional runtime

Install `vizdoom==1.2.4` in an isolated environment. The existing adapter loads the bundled basic scenario/Freedoom assets without a display:

```bash
python -m jev.game_cli play doom_basic --policy teacher --seed 42 --max-steps 100 --output runs/games/doom-teacher.json
python -m jev.game_cli replay runs/games/doom-teacher.json
```

Replace `--policy teacher` with `--policy http` to use a checkpoint. The default
`--doom-decision-mode combined-v1` preserves the original six-option combined
movement/attack Choice, existing trace configuration, and historical evaluation
form. Its representation differs from the frozen `jev.case_doom` source dataset.

Select `typed-v1` explicitly to use the training-aligned movement Choice, attack
Noul and alignment Score:

```bash
python -m jev.game_cli play doom_basic --policy http \
  --doom-decision-mode typed-v1 --seed 42 --max-steps 100 \
  --output runs/games/doom-typed-http.json
python -m jev.game_cli replay runs/games/doom-typed-http.json
python -m scripts.evaluate_game_service --games doom_basic \
  --doom-decision-mode typed-v1 --seeds 42,43,44 --max-steps 40 \
  --expected-model Qwen/Qwen3.5-2B --output-dir runs/game-eval-doom-typed-2b
```

The typed request uses exactly the frozen training state, question strings, and
option descriptions, with question IDs `movement`, `attack`, and `alignment`.
The movement labels remain `Strafe left`, `Strafe right`, and `Hold lateral
movement`; the five alignment grades remain unchanged. This produces nine
scoring sequences per request: three movement candidates, one Noul prompt, and
five alignment candidates. No teacher labels or extra protocol fields enter
model state, and the frozen training data and `case_doom.py` remain unchanged.

The model's movement and `attack.noul >= 0.5` determine the exact
`[MOVE_LEFT, MOVE_RIGHT, ATTACK]` buttons. Alignment is recorded as a model
judgment and never gates attack or substitutes another action. Every head must
be valid: finite numeric probabilities, an offered maximizing movement, a
consistent expected Score, the two correct confidence values, and the original
Score legend. A malformed head invalidates the decision; the teacher is used
only by the separately selected teacher baseline.

Typed traces preserve the raw three-head `answer`, decoded `control_decision`
(including threshold, probability, alignment and intended buttons), and
`executed_buttons` actually sent to the engine. The HTTP evaluator also retains
the parsed raw response JSON on failures. Replay checks the decision-to-action
mapping and executed buttons, as well as the normal observation/reward checks.
Its trace protocol is `vizdoom-basic-typed-v1`; configuration records
`doom_decision_mode`, so results remain distinguishable from combined-action
runs. Random and teacher baselines answer the same three questions.

Contract tests compare runtime candidate prompts against all 9,093 frozen Doom
source rows across splits (6,354 belong to train)
and exercise HTTP validation, threshold behavior, actual button dispatch to a
CPU test double, and replay tamper detection. The optional real-engine test
requires local ViZDoom; it was unavailable for this implementation check.
No new model rollout or Doom score is claimed. The model still sees numeric
state derived from visible targets, not screenshots or hidden objects. See
[doom-case.md](doom-case.md) for the unchanged engine/data protocol.

## Data and checks

```bash
python -m jev.game_cli build-data snake --episodes 100 --max-steps 80 --seed 42 --output-dir data/games-snake
python -m jev.data validate data/games-snake
python -m jev.game_cli build-data tic_tac_toe --seed 42 --output-dir data/games-tictactoe
python -m jev.data validate data/games-tictactoe
python -m jev.game_cli build-data all --episodes 100 --max-steps 80 --seed 42 --output-dir data/games-v1
python -m jev.data validate data/games-v1
python -m unittest tests.test_games -v
```

The Snake generator alternates random and heuristic rollouts, deduplicates exact visible states and assigns identical board states to one split. Training/held-out ID boards are 6×6; OOD boards are 8×8. Each retained state has one heuristic Choice and three exact one-step collision Noul questions. The split is by board state rather than episode: nearby states from the same trajectory may cross ID splits. This is a state-generalization test, not independent-episode or policy-generalization evidence. Labels never depend on the RNG's future food.

Tic-tac-toe enumerates all 5,478 reachable boards and labels every nonterminal board with at least two available squares using exact minimax. All rotations/reflections of one board share a group and split. Terminal boards and forced final moves are omitted from training because the existing training schema requires two candidates; runtime handles both correctly. There is no tic-tac-toe OOD claim. Uniform targets over tied actions express a teacher policy, not a model's calibrated chance of winning.

Generated records use the existing typed schema and CC0 provenance for our generated data. `metadata.family=policy` fits the current shared validator; `source` and `metadata.case_name` identify each game. No official demo or benchmark examples are used as training data.

The recorded combined build above contains **23,182 records / 5,314 groups**: 18,884 Snake records and 4,298 tic-tac-toe records. Splits are 15,772 train / 946 calibration / 1,136 validation / 1,864 test / 3,464 OOD. The checked-in [manifest](../reports/data-manifests/games.json) records hashes. `all` remains frozen to those two data generators. All `*-state.json`, the tiny Wiki graph, and `*-request.json` fixtures in `examples/games` are synthetic examples, not captured official gameplay. Only `*-request.json` files are inference-ready requests.

### Separate local control-game starter data

```bash
python -m jev.game_cli build-control-data --episodes 100 --max-steps 40 --seed 42 --output-dir data/control-games-v1
python -m jev.data validate data/control-games-v1
```

This independent dataset leaves `data/games-v1` unchanged. It runs 100 seeded episodes **per game**, alternating teacher and random behavior, capped at 40 decisions. Each observed state is labeled by the deterministic local teacher even when the behavior policy chooses a random transition. The training `state`, `question`, `kind` and `options` come directly from `compile_request(**game_request(runtime))`; no alternate training prompt or artificial episode identifier is inserted into model input. Teacher labels, episode/seed details and runtime configuration are kept in metadata only.

The default build yields **1,733 distinct Choice records / 117 groups**: 1,697 platformer states and 36 T-Rex states. Splits are 1,374 train / 97 calibration / 56 validation / 206 test. T-Rex has only four speeds and nine obstacle configurations in this local runtime, so deduplication retains its 36 possible observations rather than inflating its size through seed repetitions. Only four T-Rex states land in test; that is too small for a broad gameplay-performance claim.

All positions on an identical platformer terrain layout share a split, including repeated layouts generated by different seeds. T-Rex groups identical complete observations. Rotations/reflections are not used: gravity and the right-hand flag make them different tasks in these runtimes. There is **no OOD claim or OOD data**; the empty `ood.jsonl` is provided for schema compatibility. Future harder speed/geometry variants would need a separately specified runtime and held-out protocol.

Platformer labels use deterministic BFS over the full terrain and discrete physics already visible in the request. T-Rex labels simulate the current obstacle and follow the stated maneuver preference; future obstacle generation and RNG state are not consulted. These data train the original local simulators, not the source NES/browser games. The [control manifest](../reports/data-manifests/control-games.json) records configuration and split hashes. Tests reconstruct the runtime from each sampled record, check prompt equality and legal teacher targets, enforce layout split isolation, and verify that changing provenance or future RNG state does not change model input or the current teacher decision.

## Public references

These are behavioral references, not incorporated source code. The game engine, loop and adapter prompts in this repository are independently written.

- [Snake community demo](https://github.com/sorrycc/typesafe-snake): direction decisions using board state and derived safety features. No repository license was identified; its code is not copied here.
- [Mario policy/state](https://github.com/fhshaik/typesafe-mario/tree/ca22449ed187118d19326d1f54b01b6636578aa4/src/typesafe_mario): controller macros plus jump and danger decisions. No repository license was identified; prompts are independently worded and its emulator code is not incorporated.
- [T-Rex decision service](https://github.com/joshlarsen/jev-t-rex-runner/blob/49682008948c8715fd5a2824d33284193d6eab89/server/decision-service.mjs): BSD-3-Clause repository documenting the browser-state contract and maneuver/jump-profile decisions. No game assets are copied.
- [Original Jev launch](https://typesafe.ai/blog/introducing-system-one-models-and-jev): Doom text-state control and Wikiracing.
- [ViZDoom](https://github.com/Farama-Foundation/ViZDoom/tree/1.2.4/scenarios) and [Wikispeedia](https://snap.stanford.edu/data/wikispeedia.html): existing optional engine/data dependencies, with details in their case documents.

The linked `achimala/jevinci` repository redirects to a painting demo, not a game; its integration is documented separately in [painting.md](painting.md).
