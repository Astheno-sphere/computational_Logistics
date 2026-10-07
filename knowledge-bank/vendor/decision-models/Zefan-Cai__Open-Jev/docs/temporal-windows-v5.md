# Original temporal-window controls v5

The completed 2B v4 pilot left numeric candidate accuracy at 30.0% on its
synthetic test and reduced it from 35.0% to 30.0% on controlled OOD. Timeline
OOD accuracy also fell from 58.3% to 54.2%. On the separate frozen public
development sample, temporal/numeric Choice stayed 0/3 and Noul stayed 0/3.
These are small development samples, not general population estimates.

An audit of all 560 original v4 timeline rows found no request before delivery
or exactly at delivery; all delivery timestamps used UTC. Their four-row
groups covered the upper deadline and exception route. V5 fills this specific
lower-bound and time-representation gap. V4 data, reports, checkpoints and
release weights remain frozen.

## Authored controls and independent validation

Each original scenario has four counterfactuals: one second before, exactly
at, and one second after an inclusive boundary, followed by a request after
the deadline with an approved exception. Groups alternate between the delivery
boundary and deadline boundary. Three rows are Choice and one is Noul; the
verification row rotates among the four positions. Choice option order is
shuffled, and Noul true/false proposals are balanced over complete eight-group
blocks. Case IDs are opaque, and hidden split, variant and target metadata
does not enter model prompts.

Delivery and request strings use different explicit fixed UTC offsets. The
controls include month and year crossings. Controlled OOD uses different
offsets and durations, reworded policy text, and dates around February 29
in four leap years. Seeded year/minute/second variation keeps the temporal
facts distinct across groups; changing only case IDs cannot pass the audit.
It remains the same closed-interval workflow, not a new domain. These
are fixed-offset instants; daylight-saving transitions and business calendars
are outside the scope.

The generator computes labels using aware `datetime` interval comparisons.
The independent auditor does not import the generator or its oracle. It parses
the visible timestamp fields, converts validated calendar components into
integer epoch seconds, subtracts explicit offsets and checks
`0 <= request_seconds - delivery_seconds <= hours * 3600`. An approved
exception yields review. Noul proposals are read from the visible question
and checked against metadata. The audit validates the two authored policy
wordings, not arbitrary natural-language policy semantics.

Hand-calculated tests verify equivalent instants across offsets, inclusive
lower and upper boundaries, the second immediately outside each boundary,
leap-day crossing, and exception precedence. Corrupted labels, mismatched
visible proposals, incomplete counterfactual groups and changed split hashes
are rejected.

## Frozen small preparation, October 2, 2026

```bash
python -m scripts.build_temporal_windows_v5 \
  --output data/temporal-windows-v5-20261002-r1
python -m scripts.audit_temporal_windows_v5 \
  --dataset data/temporal-windows-v5-20261002-r1 \
  --output reports/temporal-windows-v5-20261002/audit.json
python -m unittest tests.test_temporal_windows_v5
```

The default freezes 256 rows in 64 complete groups: 128 train rows and 32 each
for calibration, validation, test and OOD. There are 192 Choice and 64 Noul
rows. Every split covers both boundary sides, different displayed offsets,
month/year crossings and exception overrides. OOD also covers leap day.
Groups, cases and model inputs are disjoint across splits. Dataset creation
and report creation refuse to overwrite their paths. The CLI audit output's
parent directory must already exist; choose fresh output paths when replaying
the committed preparation.

The [copied manifest](../reports/temporal-windows-v5-20261002/manifest.json)
records exact generator settings and hashes for all five split files. The
[independent audit](../reports/temporal-windows-v5-20261002/audit.json) pins
the manifest, generator and validator hashes and records boundary/offset
coverage. The raw original CC0 data stays in the ignored `data/` directory
and can be rebuilt from the pinned source and settings. No public benchmark
question, scenario, answer, or sealed material enters either implementation.

## Fixed pilot and next evaluation decision

One predeclared 64-step pilot completed on MS N1-1 GPU5 in 185.15 seconds,
starting from the exact released 2B package. It consumed 256 examples by cycling
128 distinct original training rows, with 32 separate calibration rows. The
[raw report and independent CPU replay](../reports/temporal-windows-v5-20261002/ms-2b-fixed-pilot/README.md)
retain both weight states at both temperatures, all subgroup results, the
original v4 regression rows and process-cleanup receipts.

V5 test argmax accuracy rose from 15/32 to 24/32 and controlled OOD from 17/32
to 25/32. These aggregate gains hide worse exclusion-boundary decisions:
before-delivery and after-deadline rows together fell from 2/8 to 0/8 on test
and from 5/8 to 1/8 on OOD. Interior, inclusive boundaries and exceptions
improved. The original v4 regression test fell from 86/128 to 83/128 and OOD
from 83/128 to 81/128 in this runtime. The checkpoint is diagnostic evidence;
it has not replaced any released weights and does not solve temporal comparison.

All twelve outside-window Choice rows in the saved test/OOD journals selected
`accept` after adaptation, although their gold action was `reject`. Further
development should investigate that approval pattern before defining another
independent original control set or training schedule.
The new test/OOD rows are now observed development evidence, not reusable
blind tests. Calibration must still be fitted only on calibration, with
weight and temperature effects reported separately. The original numeric
controls also lack negative/zero balances and ledger-order variation; v5 did
not address that gap. Production code should compute exact dates and amounts
directly. There is no official JevBench or natural-request improvement claim.

The [predeclared pilot plan](../reports/temporal-windows-v5-20261002/pilot-plan.json)
froze one 64-step adaptation from the released 2B, 128 training rows, 32
calibration rows and 32 each Test/OOD, before model evaluation. It also requires
the earlier frozen v4 groups as regression controls and both weight states at
both temperatures before any v5 model evaluation. No checkpoint, schedule,
temperature threshold or test/OOD selection was retuned after the result.
