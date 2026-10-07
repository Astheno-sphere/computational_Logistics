# Serial model evaluation on N1-1 GPU 3

`scripts/run_service_suite.py` evaluates the 2B, 9B, and 27B checkpoints one at
a time on **MS N1-1 physical GPU 3**, while GPUs 0–2 remain available for the
separate training jobs. It creates no remote job and never stops an unrelated
process. The repository's `state/auto_research/resource_policy.json` is binding:
the actual host and `--expected-hostname` must both match its saved N1-1
hostname, and the selected card must be its evaluation GPU, outside its
training set. A command-line hostname cannot override the policy. The policy
path, hash, and allocation are retained in the manifest.

```sh
python scripts/run_service_suite.py \
  --expected-hostname kwade5342000001 --gpu 3 \
  --checkpoint-root ../runs \
  --checkpoint-template '{tag}-pilot-v1/checkpoint' \
  --frontier-source ../evals/jev-frontier-100 \
  --workflow-cases data/workflows-v1/workflow_cases.jsonl \
  --output-root ../eval-results/pilot-suite-NEW-RUN \
  --include-doom --include-latency
```

Run from the checkout root with the project's installed runtime. Relative input
and output paths resolve from that working directory. Choose a fresh output
root: an existing one is refused, and checkpoints/old runs are never modified.
`--include-doom` requires ViZDoom to be installed; omitting it explicitly excludes
Doom. No mock environment replaces a missing dependency. The default game
evaluation uses the repository's small fixed Wiki graph, not full Wikipedia.

For each checkpoint, the launcher performs a GPU/port preflight, then starts its
own `jev.server` child on port 8791 with `CUDA_VISIBLE_DEVICES` set to physical
GPU 3's UUID (avoiding differences in CUDA device ordering), logical
`cuda:0`, 4096 maximum input length, and candidate batch size 16. It waits at
most ten minutes for that child's readiness log and matching `/health`, then
verifies the model, scorer method, base revision, checkpoint hash, temperature,
code commit, and maximum length through an actual inference response. It also
checks that the server PID appears on physical GPU 3.

The checkpoint service limits are configurable with `--max-length` and
`--batch-size`; their defaults remain 4096 and 16. Inputs above the length limit
return HTTP 422 without truncation. A later run with a larger context capacity,
for example `--max-length 16384 --batch-size 1`, must use a fresh output root
and retain the original run's failures. The new length is included in service
identity checks and both settings appear in the manifest and server command.
GPU memory feasibility still needs verification; a smaller candidate batch can
reduce memory use. These flags do not change the optional latency benchmark's
separate limits.

The four measurements run sequentially against that service:

1. All committed JSON request examples: interface/schema coverage.
2. Twelve parent cases per workflow per split, test and OOD: **96 cases** against
   independently generated workflow labels.
3. Frozen JF100: **100 items × 3 option rotations = 300 trials**, held out only.
4. Paired game runs with seeds **10001, 10002, 10003**, maximum **40 steps**, and
   explicit learned, random, and teacher policies.

All four run by default. `--measurements` selects one or more of
`demo_requests`, `workflows`, `frontier_100`, `games`, `browser`, and `drone`;
the original four stages retain the order above, followed by any selected
browser and drone stages. The two snapshot stages are opt-in and each uses
20 held-out parents per test/OOD split with up to three variants per parent.
They measure snapshot judgments, without a browser or flight executor; see
[browser evaluation](browser-eval.md) and [drone evaluation](drone-eval.md).
Only selected stages require their input files or optional
dependencies. `--include-latency` remains an independent optional final stage.

`--models 2b` can evaluate one completed checkpoint without waiting for the
other sizes. The snapshot inputs are selected with `--browser-cases` and
`--drone-cases`. Each stage binds the checkpoint hash and exact base revision.
For Doom, `--include-doom --doom-decision-mode typed-v1` uses the separate
movement, attack, and alignment questions used by its training source. The
default remains `combined-v1`; results from these two contracts must be kept
separate in fresh output directories.

The initial 2B pilot at the 4096-token limit returned **12 HTTP 422 failures
out of 300 Frontier trials**: six reported 6167 encoded tokens, and six reported
9813. These remain failures in the original 300-trial result; the server did
not truncate them. A later context-capacity comparison runs the complete
300-trial Frontier evaluation again for each checkpoint in a separate output
directory. It does not retry only the failed trials or replace the original
score. For example:

```sh
python scripts/run_service_suite.py \
  --expected-hostname kwade5342000001 --gpu 3 \
  --checkpoint-root ../runs \
  --frontier-source ../evals/jev-frontier-100 \
  --output-root ../eval-results/pilot-frontier-context16k-NEW-RUN \
  --max-length 16384 --batch-size 1 --measurements frontier_100
```

Every measurement gets its own output path and console log. Exit codes are
recorded; a semantic/schema failure does not skip the other measurements. The
service is probed after each measurement. If the model is unavailable or its
identity changes, the suite stops instead of switching models or using a
fallback. Each measurement has a one-hour default timeout, configurable with
`--measurement-timeout`.
Timeouts are recorded as exit code 124 and interruptions as 130, alongside the
actual child exit code. The child PID is saved as soon as it starts.

The launcher always terminates and reaps its own server before loading the next
model. GPU preflight requires no compute process, at most 512 MiB allocated, and
at most 5% utilization; it waits up to 30 seconds for release and otherwise
fails without killing another process. A local advisory lock also prevents two
copies of this suite from racing onto GPU 3. It is not a cluster reservation;
other users still need to respect the allocation.

With `--include-latency`, all three servers finish and stop first, then the
separate cached no-training-versus-generation benchmark runs on the same card.
Its default request is the mixed drone example; use `--latency-request` for
another committed request. See [latency.md](latency.md) for that comparison's
validity rules. No network model download is allowed by the suite.

`manifest.json` is updated atomically with the current phase, child PIDs,
checkpoint identities, code commit, GPU checks, measurement commands, exit
codes, and timestamps. Interrupted or failed runs retain earlier artifacts.
SIGINT/SIGTERM cleanup only affects children created by this launcher.
Completion means measurements finished, not that any model met a capability or
release-quality threshold.
