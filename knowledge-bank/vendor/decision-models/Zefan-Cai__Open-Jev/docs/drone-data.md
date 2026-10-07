# Synthetic drone snapshot controls

`jev.case_drone` supplies independently authored, deterministic supervision for
the existing `jev.community.drone_request` adapter. It covers the permitted
maneuver Choice, three-level collision-risk Score, and target-loss-evidence
Noul. All rules, thresholds, measurements, goals, and legal maneuvers used by
the teacher are visible in the model input.

This is a **snapshot control corpus**, not simulator trajectories or aircraft
flight data. The labels describe a disclosed geometric heuristic and an
observation-evidence rule. They do not establish collision probabilities,
physical target-loss truth, connected flight paths, or a trained flight policy.
The build uses no GPU inference, external task records, source simulator assets,
or JF100 items. It remains separate from `release-v2` and `browser-v1`.

## Reproduce

```bash
python -m jev.case_drone --output-dir data/drone-control-v1 --groups 500 --ood-groups 100 --seed 42
python -m jev.data validate data/drone-control-v1
python -m unittest discover -s tests -p test_drone_data.py -v
```

The destination must be empty or absent. Generated data stay in the ignored
`data/` directory. The checked-in [manifest](../reports/data-manifests/drone.json)
contains source-file hashes, split-file hashes, the full-case hash, supervision
counts, and exact generation settings. Generated numerical observations and
labels carry `CC0-1.0` provenance; upstream simulator code or media are not
redistributed.

## Build counts

Seed 42 generates **500 independent parent scenes**, including **100 OOD
parents**. Each parent retains 17–18 requests after removing duplicates that
differ only in observation revision ID: **8,583 requests** and **25,249 supervised
records** across all splits. ID/order augmentations are counterfactual variants within those
500 parents, not additional independent scenes.

| Split | Parents | Requests | Supervised records |
| --- | ---: | ---: | ---: |
| Train | 311 | 5,335 | 15,694 |
| Calibration | 25 | 433 | 1,274 |
| Validation | 23 | 395 | 1,162 |
| Test | 41 | 703 | 2,068 |
| OOD | 100 | 1,717 | 5,051 |

The corpus contains 8,083 Choice rows, 8,583 Score rows, and 8,583 Noul rows.
All three questions have defined references. For 500 requests the only permitted
maneuver is `brake`; their runtime Choice is retained in `cases.jsonl`, but its
training row is omitted and counted because the training schema requires at
least two options. No competing actions are invented.

| Maneuver reference | Requests |
| --- | ---: |
| `hold_course` | 2,084 |
| `brake` | 3,084 |
| `gap_left` | 1,083 |
| `gap_right` | 1,083 |
| `climb` | 666 |
| `reacquire` | 583 |

Risk grades 0/1/2 have 2,834 / 5,081 / 668 requests. Target-loss-evidence
references are true in 1,996 requests and false in 6,587. These are deterministic
one-hot policy labels, not empirically calibrated probabilities.

## Observable state and exact contract

The adapter receives the original observation, including:

- `flight`: speed, diameter, altitude, ceiling, measured upward clearance, and
  the independent `climb_clearance_verified` flag.
- `obstacles`: measured surface distance, lateral offset, width, top altitude,
  obstacle forward speed, and left/right gap widths. IDs are opaque and shuffled.
- `target`: current visibility, time unseen, and timestamped detection/region
  visibility history.
- `goal`: `follow_target` or `continue_route`, plus an explicit left/right
  preference used only to break equally wide safe-gap ties.
- `control_policy`: the full `CONTROL_RULES` text and numeric thresholds.
- `permitted_maneuvers`: the exact action catalog also passed to the adapter,
  visible to each independently scored candidate.

`records_from_cases` rebuilds `drone_request`, verifies question and candidate
ordering, and uses `compile_request` without changing its questions or options.
Gold answers map through the compiled `answer_keys`; Score metadata records
ordered values `[0, 1, 2]`. The full `cases.jsonl` additionally retains a
recomputable derivation trace for each obstacle, required gap/climb geometry,
and qualifying target-history times. These derivations, references, split/group
IDs, family tags, and provenance remain outside candidate prompts.

JSON cases preserve request mapping order. Tests and the full build audit
reconstruct persisted requests, labels, and compiled model prompts, rather than
checking only in-memory examples.

## Disclosed reference policy

Obstacles extend upward from the ground. Course intersection uses the observed
lateral offset/width and altitude relative to drone radius and a margin. For
each intersecting obstacle, the policy computes:

```text
closing = max(0, drone_speed - obstacle_speed)
stopping_distance = closing * reaction_time + closing² / (2 * deceleration) + margin
TTC = measured_surface_distance / closing    # infinite when closing is zero
required_gap_width = drone_diameter + 2 * margin
```

These equations define the synthetic task's relative-motion model. The scene
risk is the maximum observed obstacle grade: 2 for stopping-distance or
imminent-TTC violations; otherwise 1 for caution TTC or nearby tight gaps;
otherwise 0. The exact inequalities and course-intersection tests are included
in every model input.

The generated policy thresholds are margin 0.2 m, reaction time 0.25 s,
deceleration 3 m/s², imminent/caution TTC 1/4 s, tight-clearance range 3 m,
target-loss grace 3 s, evidence window 30 s, and two distinct failed scans.
They define this corpus and do not represent aircraft configuration advice.

At risk 2, the reference chooses `brake`. At risk 1, a side gap must satisfy the
width requirement at **every risk-positive obstacle**, and the maneuver must
be permitted. The wider minimum gap wins; the goal breaks exact ties. If
neither side is usable, `climb` requires all of: explicit permission, verified
clearance, enough measured upward clearance, and sufficient ceiling allowance
above the highest relevant obstacle plus drone radius and margin. Otherwise
the reference brakes.

At risk 0, a follow-target goal with supported loss evidence chooses permitted
`reacquire`; other goals use permitted `hold_course`, falling back to `brake`.
This corpus always includes `brake` in the legal catalog. The general adapter
allows other nonempty subsets, which are outside this generator's declared
fallback policy.

The Noul answers **whether observations support loss under the stated evidence
rule**. It is true only when the target is currently unseen, the grace period
has elapsed, and at least two distinct recent scans fully exposed the search
region without detecting the target. Any positive detection in that same
window overrides those negatives. Duplicate timestamps, occluded scans, old
scans, and an elapsed timer alone do not establish this evidence. No hidden
target position or later observation is consulted.

## Counterfactuals, OOD, and remaining gaps

Variants change obstacle distances, left/right gaps, action availability,
verified climb clearance, height/clearance limits, and target visibility
evidence. Paired side-goal variants keep all measured facts and the observation
ID identical while changing only goal preference. Follow-target versus
continue-route variants preserve the geometry and evidence while changing the
navigation objective. ID, obstacle order, legal-action order, and history order
are also perturbed without changing the semantic decision.

All variants of a parent stay in one split. ID scenes contain one blocking
barrier and an off-course distractor. OOD scenes contain two blocking barriers,
an off-course distractor, and an obstacle below the flight altitude. OOD also
uses higher speeds (4–7 versus 0.8–2.5 m/s), larger body and obstacle widths,
higher altitude, and longer unseen histories. Brief-occlusion controls remain
below the same grace threshold in both distributions. These are new parameter
and geometry compositions of the same disclosed rules, not unseen real-world
perception tasks.

No actions are executed during generation. There are no episode rewards,
collision outcomes, reflex interventions, or model accuracy measurements to
report. The adapter returns tactical proposals; a simulator, perception system,
controller, independent collision reflex, and closed-loop outcome evaluation
remain separate work described in [training coverage gaps](training-coverage-gaps.md).
