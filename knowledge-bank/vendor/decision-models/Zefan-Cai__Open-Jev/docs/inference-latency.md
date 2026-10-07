# Measuring Open-Jev inference latency

The September 20 H100 run measured the released 2B checkpoint and Jev 1.13.0
from the same client, with 20 measured calls after three warmups per workload
and path. All 880 Open-Jev timed calls and 220 Jev timed calls returned valid
responses. Representative P50/P95 values, in milliseconds:

| Workload | Open-Jev-2B local HTTP, cache off | Jev remote HTTPS |
| --- | ---: | ---: |
| Drone, three typed questions | 38.3 / 41.4 | 312.2 / 361.8 |
| Customer service, eight Boolean questions | 85.0 / 133.9 | 295.3 / 330.4 |
| 128 state tokens, two candidates | 35.9 / 36.3 | 286.0 / 361.4 |
| 1,024 state tokens, 32 candidates | 1,015.9 / 1,369.7 | 301.4 / 361.2 |

These compare two deployments: local HTTP on one H100 versus remote HTTPS,
including fresh connection setup. Jev's server hardware is undisclosed. They
do not establish a hardware-matched model speedup or equal decision quality.
The complete [2B report](../reports/inference-latency/public/2b-h100-20260920/report.json)
and [Jev report](../reports/inference-latency/public/jev-api-20260920/report.json)
include all eleven workloads; each directory also includes the original request
text and individual responses/times. Public copies redact machine identifiers
and internal paths while preserving the measured values.

The experimental cached path failed the predeclared probability tolerance on
nine workloads; the maximum difference was `0.005703`, with no selected-decision
changes. It remains off by default, and failed comparisons have no cached speed
ratio. The large-candidate uncached slowdown is retained in the table and raw
records.

`scripts/benchmark_inference_latency.py` measures the released **2B LoRA adapter,
decision head and calibration**, loaded on its pinned Qwen base. It measures a
warm model through the Python Predictor and through a real loopback HTTP server.
The latter includes JSON encoding, a fresh TCP connection, server handling,
inference, decoding and response validation. The Python timing includes request
compilation, tokenization, synchronized inference and typed response formatting;
it is not a CUDA-kernel-only measurement. Model loading is reported separately.

Run on an exclusively allocated GPU, after obtaining it through the local
scheduler. This command does not reserve GPUs or stop other work:

```bash
CUDA_VISIBLE_DEVICES=0 python -m scripts.benchmark_inference_latency \
  --checkpoint /path/to/Open-Jev-2B/checkpoint \
  --request examples/community/drone.json \
  --request examples/workflows/customer_service.json \
  --contexts 128 512 1024 --candidates 2 8 32 \
  --batch-size 32 --warmup 3 --repetitions 20 \
  --output reports/inference-latency/2b-NEW-RUN
```

The synthetic matrix varies shared **state tokens**, rather than total prompt
length, and candidate count. Each workload records its actual token counts for
every complete candidate input. The two demo requests retain their original
state and question definitions. No input is silently truncated. Pass
`--prepare-only` with `CUDA_VISIBLE_DEVICES=''` to produce requests using only the
CPU tokenizer; pass `--requests path/to/requests.json` to replay exactly those
requests on a GPU or hosted service.

Every workload receives three excluded warmup iterations and twenty measured
iterations of four paths: cached/uncached Predictor and cached/uncached local
HTTP. Their order rotates to reduce order bias. CUDA synchronizes before and
after inference. Concurrency is one; cache state is confined to the current
request. There is no cross-request result reuse. Warmups, errors, responses and
individual times are retained in `samples.jsonl`. Timing percentiles use linear
interpolation at `(n - 1) × q`, computed on successful measured attempts. Both
all-attempt percentiles and error counts are reported; P95 from twenty requests
is descriptive, not a production tail-latency estimate.

Cached and uncached answers must match question/candidate IDs, usage and selected
decisions, with maximum probability error at most `1e-4`. Raw timing is retained
even when parity fails; the cached speed ratio is then null. Prefix caching stays
experimental and off by default. The report records actual runtime versions,
GPU, parameter dtypes, attention implementation, source hashes, checkpoint
identity, calibration and load time.

A hosted Jev API measurement must use the same state/questions and record the
client location, endpoint, model/version, HTTP errors and network conditions.
Its end-to-end latency includes external networking and service scheduling.
Do not compare it to Python compute as if it were an equivalent deployment, or
infer equal accuracy from latency. Vendor claims, authentication errors and
unmeasured values must remain separate from successful inference measurements.

`report.json` contains summaries and parity checks; `requests.json` and
`samples.jsonl` preserve the evidence. The CLI refuses an existing output
directory and returns nonzero for request, runtime, parity or budget failures.
Its elapsed budget is checked between iterations; a cluster coordinator must
also impose a hard subprocess timeout.

The measured run uses one H100 80 GB GPU for released 2B inference. Cluster process management is outside this public benchmark command.
