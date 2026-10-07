# Latency comparisons

`scripts/benchmark_generation.py` measures an untrained decision scorer against
the original autoregressive Qwen model on the same GPU. It provides two explicit
output contracts; `full_typed` remains the default. It makes no hosted API
calls and uses cached files only. A missing pinned snapshot fails; there is no
automatic download.

```sh
CUDA_VISIBLE_DEVICES=3 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python scripts/benchmark_generation.py \
  --model Qwen/Qwen3.5-2B \
  --revision 15852e8c16360a2fea060d615a32b45270f8a8fc \
  --request examples/community/drone.json \
  --output-contract full_typed \
  --device cuda:0 --batch-size 32 --repeats 3 \
  --max-input-tokens 4096 --max-new-tokens 2048 \
  --output reports/latency-generation-2b.json
```

The drone request is a small mixed Choice/Noul/Score example. The same command
can take `examples/community/support_28.json` to exercise a larger fan-out.
For this project's authorized cluster run, use MS N1-1 GPUs 0–3 only. The GPU
must be available for the run; the script neither reserves it nor stops
other processes. Run both paths on the same otherwise-idle H100 when making an
H100 comparison. The report records the actual device name. Existing output
files are refused so a new comparison cannot overwrite earlier attempts.

## Two output contracts

| Flag | What the autoregressive model emits | What software computes |
| --- | --- | --- |
| `--output-contract full_typed` (default) | Full typed answers, all probabilities, Choice winner, Score expectation, confidence, and Score legend | Validates the generated fields against the same formulas used by the decision path |
| `--output-contract probabilities` | Only a complete probability mapping for every question and every offered candidate | The shared `jev.api.format_response` computes Choice, Noul, Score, confidence, and legend, just as it does for decision scoring |

For example, the probability contract for the three-question drone request is:

```json
{"probabilities": {
  "maneuver": {"gap_right": 0.6, "brake": 0.2, "hold_course": 0.2},
  "risk": {"0": 0.1, "1": 0.6, "2": 0.3},
  "target_truly_lost": {"false": 1.0, "true": 0.0}
}}
```

Noul includes both `false` and `true`; Score uses the string indices from its
supplied rubric. The model must produce every probability. The root object,
question IDs and candidate IDs must match this contract exactly, with no
derived fields. Numbers must be finite, within [0,1], and each distribution must
sum to one within the shared formatter's `1e-6` floating-point tolerance.
Booleans and numeric strings are rejected. Invalid distributions are not
renormalized into valid ones; the formatter only applies its existing tolerance
to already valid inputs.

To run this separate comparison, select it explicitly and use a new output:

```sh
CUDA_VISIBLE_DEVICES=3 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python scripts/benchmark_generation.py \
  --model Qwen/Qwen3.5-2B \
  --revision 15852e8c16360a2fea060d615a32b45270f8a8fc \
  --request examples/community/drone.json \
  --output-contract probabilities \
  --device cuda:0 --batch-size 32 --repeats 3 \
  --max-input-tokens 4096 --max-new-tokens 2048 \
  --output reports/latency-probability-mapping-2b-NEW-RUN.json
```

This changes the generative output contract and its prompt/token workload.
It removes deterministic arithmetic and rubric-copying work from generation;
it is a new prospective measurement, not repair or rescoring of the original
full-typed output. The report's benchmark name, `output_contract`, configuration,
generation method and scope identify the distinction. Both modes retain the
same original state/questions and deliver the complete final typed answer.
The probability mode also uses a stricter simplex tolerance (`1e-6` instead of
`0.002`) to match the shared formatter without repairing invalid distributions.
Differences between the two contracts therefore cannot be attributed solely to
removing derived-field generation.

## What is held constant

- Identical original model ID, immutable revision, bf16 backbone weights, SDPA
  attention, and one physical GPU. Models load **serially**, with CUDA memory
  released between paths. No LoRA adapter is loaded and decision temperature is
  exactly 1.
- Identical state, complete question definitions, candidates, and final
  output information: typed answers, all probabilities, winning Choice, Score
  expectation, legend, and derived confidence. The exact request and its file
  and payload SHA-256 are saved.
- One excluded warmup per path, followed by at least three measured repeats.
  Autoregressive sampling and thinking are disabled. Generation has a finite
  output-token limit. Neither path silently truncates an oversized input.

The execution mechanisms differ. Open-Jev evaluates each candidate as a
separate Yes-minus-No decision sequence and normalizes candidate logits in
software. The original model generates the selected contract token by token.
In `full_typed` it must also generate the deterministic derived fields; in
`probabilities` the shared formatter supplies those fields after strict
probability validation. Each comparison measures two ways to deliver the final
output, without assuming equal probability quality or equal calibration.

Harsha's [post](https://x.com/harshagundal/status/2100044305536889015) and
[MLX model card](https://huggingface.co/harshatheg/Qwen-2.5-1B-RLCD) describe
prefix-prefill/KV-broadcast and restricted candidate-token scoring on another
Qwen model and another device. Open-Jev's independent-candidate method is
different. No 5× speedup is assumed or inherited from that source.

## Timing and validity

Timing begins before request/prompt construction and tokenization, and ends
after synchronized GPU inference, decoding/formatting, serialization, and output
validation. It excludes model loading and the one warmup. There is no HTTP or
external network in this comparison. Both paths record their **actual encoded
input tokens**; repeated state across decision candidates is counted repeatedly.
Generative output tokens and complete raw generation text/token IDs are saved.
The decision path generates zero tokens; serialized response size is separately
recorded. Zero generated tokens does not mean zero compute.

Validation separates parse, coverage, schema, and runtime failures. A generated
code fence is a parse failure; missing questions, probabilities, or typed fields
required by the selected contract are coverage failures. In `full_typed`, invalid
numbers, non-normalized distributions, wrong argmax, inconsistent
Score/confidence, and wrong legends fail schema validation; its unchanged
tolerance of 0.002 permits rounded JSON numbers. The `probabilities` contract
uses the stricter `1e-6` simplex tolerance described above. Both reject duplicate
JSON keys and nonfinite JSON constants. There is no JSON repair or
retry, and an invalid generation's raw output and elapsed time remain in the
report.

The initial 2B and 9B full-typed drone runs each had three valid decision trials
and zero valid generation trials. Their generated distributions were complete,
finite and normalized, but generated derived fields disagreed with them:

| Retained run | Generated field | Value implied by its own probabilities |
| --- | --- | --- |
| 2B | Maneuver confidence 0.5 | 0.25 |
| 2B | Risk confidence 0.333 | 0 |
| 9B | Maneuver confidence 0.667 | 0.4 |
| 9B | Risk Score 1.3 | 1.2 |

Each model repeated the same greedy JSON three times without hitting its output
limit. This diagnoses the full-typed failures; it does not make those attempts
valid under that contract. Their original failure counts and null ratios remain.
The probability contract is evaluated only in separately saved new runs; it
must not be selected automatically after a full-typed failure.

Both three-model comparisons are now retained: [full typed output](../reports/generation-full-typed-n1/README.md)
and [probabilities with shared postprocessing](../reports/generation-probabilities-n1/README.md).
The latter has three valid timed outputs per path and model on this one drone
request. Its descriptive latency ratios do not establish equal decision
accuracy or performance on larger workloads.

The report includes all-attempt and valid-attempt medians. A descriptive
generation/decision latency ratio is published **only when every timed attempt
in both paths is valid**. Otherwise the ratio is null, with failure counts.
Even a valid-output latency ratio is not an accuracy result: both paths may
make incorrect decisions on the same input.

Runtime versions, CUDA version, GPU name, repository commit, and source-file
hashes are recorded. The fixed load order is also recorded; three repetitions
are a small experiment, not a production latency distribution. For a release
claim, retain the generated report and inspect the raw outputs and failure
counts alongside the timing.

`scripts/benchmark_api.py` measures a separate question: serial requests versus
one fan-out on the same loaded Open-Jev service. It is not a generative baseline.
