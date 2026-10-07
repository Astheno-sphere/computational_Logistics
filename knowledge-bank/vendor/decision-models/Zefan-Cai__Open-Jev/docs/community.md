# Community adapter interfaces

`jev.community` turns externally supplied observations and legal action sets
into System One requests. Its postprocessors validate typed answers and return
proposals. **It contains no browser executor, RuneScape/Pokémon emulator,
HEIST simulation, or drone controller.** These forms have not received dedicated
training or full-game evaluation. They extend the supported request surfaces;
they do not establish parity with the source demos.

## Examples

```sh
python -m jev.community --write-examples examples/community
python -m unittest discover -s tests -p 'test_community.py'
python scripts/check_demo_requests.py --examples examples/community \
  --endpoint http://127.0.0.1:8791/v1/systemone --output reports/community-smoke.jsonl
```

The last command makes local model requests and checks response contracts, not
semantic correctness. The committed requests are independently authored local
examples. No source project's benchmark records, ROMs, art, or credentials are
included.

| Example | Questions | External dependency |
| --- | --- | --- |
| `browser.json` | Operation, compatible observed targets, dropdown options, finite text candidates | A DOM observer, revisioned snapshots, executor, independent outcome verification |
| `runescape.json` | Next catalog action, immediate tick action, next poll interval | RuneBench/rs-sdk environment and action catalog executor |
| `pokemon.json` | Legal emulator action; conditional opponent-faint Noul for each battle candidate | PyBoy, lawfully supplied ROM, RAM parser, battle truth for scoring forecasts |
| `heist.json` | Threat Noul, suspicion Score, legal intent Choice, observed-target Choice | Authoritative game simulation, one guard's local observation, legal-intent executor |
| `drone.json` | Permitted maneuver Choice, collision-risk Score, target-lost Noul | Simulator perception, geometric flight controller, independent collision reflex |
| `fraud_4.json` | Four locally defined fraud/routing judgments | Reviewed payment facts and policy; this module never transacts |
| `code_security_4.json` | Four locally defined code-review judgments | Source text and application context; this module never executes the snippet |
| `tariff_255.json` | One 255-option Choice over synthetic catalog groups | Interface-scale control only; labels are not official tariff codes |
| `support_28.json` | Five Choices, four Scores, nineteen Nouls | Local support-ticket example; not the original Harsha test record |

## Observed DOM and finite text

```python
from jev.client import Client
from jev.community import browser_request, browser_proposal

snapshot = {
    "snapshot_id": "dom-revision-17",
    "url": "http://catalog.invalid/",
    "visible_text": "Product search",
    "elements": [
        {"id": "search-box", "label": "Product search", "actions": ["TYPE_TEXT"]},
        {"id": "search-button", "label": "Search", "actions": ["CLICK"]},
    ],
}
request = browser_request("Search for green tea", snapshot,
                          {"search-box": {"tea": "green tea", "coffee": "coffee"}})
response = Client().ask(**request)
proposal = browser_proposal(request, response, current_snapshot_id="dom-revision-17")
```

The caller's observer must issue a new `snapshot_id` when the DOM revision,
element identity, or relevant form state changes. Postprocessing requires an
explicit current ID and rejects a stale one. Targets are original observed
element IDs, never generated CSS selectors, coordinates, or JavaScript. The
executor still has to check visibility, occlusion, and identity immediately
before any action. `DONE` is a model proposal, not proof that the goal succeeded.

Only elements advertising `TYPE_TEXT` and supplied finite text candidates are
eligible for typing. No text candidates means the adapter does not offer that
operation. The selected text is retrieved from the caller's mapping verbatim;
there is no hidden generative-model fallback. Dropdown options similarly come
from the observation. Speculative questions are independent; only answers for
the selected operation and target contribute to the returned proposal.

## Game/control observations

- **RuneScape:** supply `observation_id`, a supported player status, nonnegative
  hitpoints, the current catalog action or `None`, and recent events. Supply
  legal catalog actions and a subset of `do_nothing`, `close_dialog`, `eat_food`,
  `restart_current`. Poll choices are distinct positive integer tick counts.
  The caller handles deadlines and checks whether an action is still legal.
- **Pokémon:** supply `observation_id`, phase (`battle`, `overworld`, `menu`),
  player facts, recent events, and an observed legal action catalog. Battles
  additionally require opponent facts. Each candidate gets its own conditional
  faint forecast, so the forecast returned with the chosen action is about that
  action. Actual faint outcomes must come from subsequent RAM observations;
  predictions are not labels.
- **HEIST:** each request sees one guard's `local_evidence`, `guard_id`, and
  observation revision. Hidden world state and other guards' observations are
  not supplied. Intent candidates and entity IDs are caller-owned; `none` is
  the explicit no-target option.
- **Drone:** supply target visibility/time unseen, measured obstacles, flight
  altitude, and a subset of the six documented tactical maneuvers. `climb` is
  accepted only with `climb_clearance_verified=True` from the simulator. The
  proposal contains no motor commands. A real flight-control system is outside
  this adapter.

All postprocessors require every requested answer, matching types, finite
normalized distributions over exactly the offered candidates, a maximizing
Choice, and a Score consistent with its distribution. Missing or malformed
responses raise errors; no scripted policy silently substitutes for a model.

## Sources and attribution

These task forms were independently implemented from the following public
interfaces; no upstream code was copied:

| Source | Inspected revision | License/boundary |
| --- | --- | --- |
| [Browser Use Jev Ultrafast](https://github.com/browser-use/jev-ultrafast) | `1231850a0bf1a0c0341fe408ef1668dbbfdfac46` | MIT. Original uses a separate text model for typing; our bounded adapter uses supplied strings. |
| [Skyvern JevScape](https://github.com/Skyvern-AI/jevscape) | `8fe4d37349fc6a8d03ac1c918302eef254bb56c3` | No top-level license detected; no code/assets redistributed. |
| [Pokémon Red](https://github.com/valentynkit/jev-plays-pokemon-red) | `cbe5387aeb6c7b3ef6b1f67d4a95e284aee3b0af` | MIT code, separately supplied ROM. Conditional per-candidate fan-out is our formulation. |
| [HEIST//ONE](https://github.com/AbdelStark/heist-one) | `632c9a55a1e5eb2cbf0b9f87db575f0b5eb36e8c` | MIT project; no original media included. |
| [Jev drone](https://github.com/RomanSlack/jev-drone) | `cbeb53ce4f17a06ea490ae43effcdad231143610` | Simulation interface only; no source or simulator assets included. |
| [Harsha post](https://x.com/harshagundal/status/2100044305536889015) and [model card](https://huggingface.co/harshatheg/Qwen-2.5-1B-RLCD) | Read 2026-09-19 | Apache-2.0 metadata; the four workload sizes motivate our own examples. We do not reproduce the original records or claimed latency numbers. |

See [public-capabilities.md](public-capabilities.md) for the larger source audit
and the distinction between a request interface, executable environment,
trained policy, and measured held-out task success.
