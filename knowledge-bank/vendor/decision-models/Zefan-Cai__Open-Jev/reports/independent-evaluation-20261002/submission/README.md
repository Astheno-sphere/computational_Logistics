# Open-Jev-27B-v1.1 independent evaluator handoff

Prepared input only. No new public or sealed result has been produced.

On a Linux NVIDIA host with sufficient BF16 27B memory, run `bash install-and-serve.sh`.
This pins loader `1c4347841ce942b8009d9187735fe5686adbbb1b`, model package `28cf73067d5b337860bbef3c85b8b82ba8730956` and base
`Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`. Base weights download on the first model load.
The checkpoint checksum and a clean loader checkout are verified before inference.
`runtime.json` records allowlisted package versions and GPU inventory; it does
not contain credentials or infer a hardware performance result.

The service is loopback-only. In another terminal, check readiness and submit
the released example request:

```bash
curl --fail http://127.0.0.1:8791/health
curl --fail http://127.0.0.1:8791/v1/systemone \
  -H 'Content-Type: application/json' --data-binary @loader/configs/example-request.json
```

For the historical 231-public protocol only, run `bash reproduce-public.sh`
after the server is ready. The original 72, easy 48 and hard 111 counts remain
separate from newer JevBench versions. No warmups or retries, concurrency one,
uncached native probabilities. `16384` is the requested token limit;
the saved training limit is 4,096. A larger evaluation limit is an explicit
override and does not establish equivalent quality at longer contexts.
Public input/raw-response files remain local: upstream source licensing is
not uniform. Publish only the aggregate and this submission/runtime manifest.

For a fresh independent sealed evaluation, the evaluator runs its own frozen
suite against `/v1/systemone`. The v1.5.4 reference had 904 open + 720 sealed
tasks; these are planning context, not results. Record actual denominators,
attempted/failed/missing requests, primitive metrics, calibration, abstentions,
request settings, checkpoint identity, measured hardware/time and estimated
cost separately. A raw probability interval and abstention policy must be
reported alongside raw accuracy. No private questions or labels are requested.
All sealed results remain pending until the independent evaluator supplies
an aggregate and reproducible manifest.
