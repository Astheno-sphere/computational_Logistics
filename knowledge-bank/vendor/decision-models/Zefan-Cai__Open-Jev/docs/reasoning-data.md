# Independent reasoning controls

`jev.case_reasoning` generates exact-label training controls for seven task
families. It does not load, read, transform, or sample JF100 questions or answers.
The generator's formulas, entity names, graphs, programs, event schedules, and
evidence records are independently produced from a fixed random seed.

```sh
python -m jev.case_reasoning --groups 2500 --seed 76109 \
  --output-dir data/reasoning-control-v1
python -m jev.data validate data/reasoning-control-v1
python -m unittest discover -s tests -p 'test_case_reasoning.py'
```

The [local CPU rebuild](../reports/runtime-checks/reasoning-release-rebuild-20260920.json)
using this recorded seed reproduced all five split hashes and the native
manifest. The original frozen corpus was unchanged.

Each scene produces three records: a Choice over the task's answer space, a
Noul checking a proposed answer, and an ordinal auxiliary question. Candidate
order is shuffled; all records of a scene remain in one split. Targets are hard
one-hot labels from exact programmatic oracles. They are not fabricated soft
uncertainty labels, and no teacher model is used.

| Domain | Main task / oracle | OOD change |
| --- | --- | --- |
| Formal logic | Evaluate a generated Boolean expression; recursive truth semantics | Deeper trees; XOR and implication |
| Relations | Direct, indirect, or unreachable directed path; BFS | Larger graphs with different density |
| Arithmetic | Integer expression; restricted AST evaluator | Floor division, modulo, abs/min/max, larger magnitudes |
| Temporal | Earliest/latest absolute instant; timezone-aware datetime comparison | Leap-day boundary, non-hour offsets, more events |
| Code semantics | Final integer variable after branches and a loop; small AST interpreter | Modulo conditions, longer input lists |
| Algorithms | Filter, sort, and index an integer list; deterministic list operations | New divisors, descending sort, larger lists |
| Evidence integration | Resolve authoritative, non-retracted latest evidence; explicit policy | Two-hop entity aliases |

Ordinal auxiliaries ask for explicit counts or the sign of an exact result.
They use meaningful ordered bins; Score expectations are not treated as exact
arithmetic interpolation. Noul verification questions contain a candidate answer
only in their own instructions, so the main Choice does not receive that hint.
Programs are interpreted through a restricted AST; no `eval`, `exec`, imports,
file operations, or general Python execution are involved.

Ten percent of scenes are reserved as OOD before group-hash train/calibration/
validation/test assignment. Every family has separate ID/OOD template IDs. The
validator checks schema, complete provenance, hard-target validity, group and
duplicate-input separation, and disjoint OOD template identities. `record_id` and
generated names are independent hashes, not encodings of answer labels.

Generated data are CC0-1.0. Their provenance cites the official
[Jev jaggedness guide](https://docs.typesafe.ai/model-jaggedness/jev-1.13) only
as motivation for task families. No documentation example or external benchmark
record was copied into this corpus.

This is a **separate expansion corpus**. Existing training mixtures and active
jobs are not modified automatically. JF100 and other declared evaluations remain
held out. Procedure-generated tests measure these controlled operations; they do
not establish general reasoning, multilingual quality, medical competence,
long-context reliability, or robustness to arbitrary code.
