# Source-inspired workflow controls

Open-Jev includes executable local task forms for all four [TypeSafe workflow evaluations](https://evals.typesafe.ai/). Each exposes a normal `{state, questions}` inference request. These are **independently authored, simplified policies and synthetic records**, not reproductions of the complete proprietary workflows or their evaluation scores.

The official HTML pages were read on 2026-09-19. Their displayed example cases, reference outcomes and model predictions are not training data here. No official example was copied into the generator. Keep those examples held out if they are later imported with appropriate provenance.

| Workflow | Included task form | Decision shape | What remains outside this implementation |
|---|---|---|---|
| [Customer Service](https://evals.typesafe.ai/customer_service) | Conversation, customer record, account ledger, pending proposal, exact consent and claim checks; SAY / REFUND / FREEZE CARD / SET INTENT / CANCEL / HAND OFF / FLAG FOR REVIEW / CLOSE | Multiple actions, including the empty set | Official 11-way triage, conditional consent/fraud/money/retention questions, every speech template, redaction, dispute creation and full multi-turn account simulator |
| [Security Incidents](https://evals.typesafe.ai/security_incidents) | Alert/asset/maintenance, event evidence, standing authorization; 17 dispositions covering the displayed close/queue and five containment playbook groups | One final disposition, or abstention | Official uncertainty thresholds and evidence rubrics, all detector types, full production incident integration |
| [Agent Trace Observability](https://evals.typesafe.ai/agent_trace_observability) | Instructions, conversation, tool arguments/results, permissions evaluated at call time, final answer, feedback; seven dispositions including COUNT ONLY from the chart | One final disposition, or abstention | Open-ended semantic task completion, subjective satisfaction, detailed causal fault localization, issue/on-call integrations |
| [Invoice Processing](https://evals.typesafe.ai/invoice_processing) | Invoice, vendor registry, purchase order, contract, delivery, past invoices and approval facts; nine displayed output families plus explicit local HOLD | Multiple actions | Full seven-round document reading, arbitrary line-item interpretation, tax/retention/contract accounting and all official reviewer routes |

Customer SET INTENT means recording a recognized request. CANCEL is separate and appears in the official detailed chart. The invoice names SHORT PAY, ROUTE FOR APPROVAL, HOLD FOR DOCUMENTS, REQUEST CORRECTED INVOICE, DISPUTE LINES, FRAUD REVIEW and DUPLICATE follow the displayed output families. HOLD is a local explicit decision when no payment can be released.

## Learned inference and policy fixtures are different

`workflow_request(name, state)` creates target-free input for `compile_request`, `jev.predict`, and the local HTTP server. Each candidate action is a separate Noul question. For security/agent traces, `select_actions` takes the highest probability above the threshold because their final outcomes are exclusive. Customer and invoice decisions retain all candidates above threshold. Exactly 0.5 abstains. Independent probabilities need not sum to one across actions.

`policy_fixture_actions`, `policy_fixture_probabilities`, and `policy_fixture_response` are deterministic **oracles for this local synthetic policy**. They do not call a model. The customer parser deliberately recognizes only the generator's controlled wording. It is not a natural-language support agent. The offline fixture demo labels itself `policy_fixture_oracle`; its success establishes wiring/rule consistency, never model accuracy.

These workflow records were not part of the earlier three-model pilot. A saved checkpoint can accept their task form, but that does not establish task quality. Evaluate actual learned predictions on held-out cases, per action and per complete action set, before claiming a model supports a business scenario reliably.

## Build the data

```bash
python -m jev.case_workflows build --output-dir data/workflows-v1 --groups-per-workflow 250 --seed 42
```

This generates 1,000 parent groups: 250 for each workflow. Each has three related cases: observed facts, missing authorization, and conflicting account/resource/payment facts. Each case fans out to one Noul row per action. All related cases and their questions stay in one split.

The output contains `train.jsonl`, `calibration.jsonl`, `validation.jsonl`, `test.jsonl`, `ood.jsonl`, `workflow_cases.jsonl`, and a checksum manifest. Standard split files have only the established training schema. Workflow files additionally carry `case_id`, `reference_actions`, and `targets`; use only their `state` and `questions` fields for inference. The input renderer ignores all label/provenance metadata. The validator checks IDs, target normalization, cross-split input duplication, entities, templates, and parent groups.

OOD reserves different customer utterances and numerical ranges with disjoint entities. It is a controlled synthetic shift, not evidence of real customer/security/invoice generalization. Counterfactual variants make escalation and hold labels frequent; inspect the manifest's positive counts and report per-action recall instead of only overall binary accuracy. Some variants intentionally have identical observable inputs/labels within their group.

## Run examples

Four checked-in files under `examples/workflows/` are complete requests suitable for real inference:

```bash
python -m jev.server --checkpoint runs/2b-pilot-v1/checkpoint --max-length 4096
python -m jev.case_workflows demo --workflow customer_service --request examples/workflows/customer_service.json --checkpoint runs/2b-pilot-v1/checkpoint
```

The workflow demo uses a 4,096-token input limit by default (`--max-length` overrides it). Older checkpoints may save shorter pilot limits; set an appropriate explicit limit when serving these richer requests. Inputs exceeding the configured limit fail instead of being truncated.

To run an explicitly deterministic, dependency-free fixture:

```bash
python -m jev.case_workflows demo --workflow customer_service --policy-fixture
python -m jev.case_workflows demo --workflow security_incidents --scenario 12 --policy-fixture
python -m jev.case_workflows demo --workflow agent_trace_observability --scenario 5 --policy-fixture
python -m jev.case_workflows demo --workflow invoice_processing --scenario 2 --policy-fixture
```

Pure functions can be used by a UI or client:

```python
from jev.workflows import workflow_request, select_actions, gate_actions

request = workflow_request("customer_service", state)
response = predictor.predict(request)  # An actual learned predictor supplied by the caller.
proposed = select_actions("customer_service", response)
decision = gate_actions("customer_service", state, proposed)
```

`gate_actions` returns `proposed_actions`, `allowed_actions`, `blocked_actions` with reasons, and `executed: false`. It never sends messages, issues refunds, changes accounts, contains hosts, or pays invoices. It does not add alternative actions automatically; blocked proposals remain visible for evaluation. The gate checks factual eligibility and authorization, not every semantic prediction. Production approval/identity records must be provided by a trusted authenticated service; arbitrary caller-supplied JSON is not authorization.

Customer approvals must bind the exact account, operation, object, amount where relevant, current proposal ID and latest customer message ID. Account mutations also require the correct identity and current account/ledger status. Security containment requires an in-date grant for the exact action and asset and honors playbook precedence. Invoice payment gates recompute integer amounts, reject duplicate payments and unverified payment accounts, and enforce approval scope, amount and dates.

## Evaluate saved learned predictions

A prediction file contains one JSON object per case, with `case_id`, `predictor_kind: "learned"`, and the typed `response` returned by inference. Select the corresponding held-out cases into a cases JSONL file first; IDs must match exactly and duplicates are rejected.

```bash
python -m jev.case_workflows evaluate --cases heldout_cases.jsonl --predictions learned_predictions.jsonl
python -m unittest tests.test_workflows -v
```

The evaluator reports raw action-set exact match and micro-F1, post-gate exact match, and blocked-action counts, overall and by workflow. The raw prediction is scored separately so a software gate cannot conceal a model's authorization failures. It rejects files marked as fixture/oracle predictions. That marker is an audit declaration, not cryptographic proof that inference occurred; retain checkpoint IDs and inference logs with reported results.

## Evaluate a running learned HTTP service

```bash
PYTHONPATH=. python scripts/evaluate_workflow_service.py \
  --cases data/workflows-v1/workflow_cases.jsonl \
  --split test ood --per-workflow 12 \
  --endpoint http://127.0.0.1:8791/v1/systemone \
  --expected-model Qwen/Qwen3.5-2B --expected-method lora_decision_head \
  --output-dir reports/workflow-service/2b-run1
```

The default evaluates 96 cases: 12 per workflow per split. It selects one variant per parent group, using identifier hashes without consulting labels. Case order is fixed across models for the same dataset/seed. Selection rejects parent groups or identical inputs that cross splits, and requires enough independent parents in each requested slice.

The run saves `selection.json`, exact `selected_cases.jsonl`, every received `responses.jsonl` entry, accepted `predictions.jsonl`, and `report.json` with raw/post-gate metrics overall, by workflow and by split. IDs plus state, question and request SHA-256 digests bind responses to the client's saved input. Returned model, inference method and calibration temperature must remain identical throughout the run. When the server provides checkpoint, base-revision and code-commit provenance, these are also checked for consistency. The optional `--checkpoint-id` is a caller-supplied label, not a verified artifact hash.

A malformed response, changed model/checkpoint, timeout or model failure stops the run. Completed predictions and the rejected raw response remain available; `failure.json` identifies the case, and no final quality report is emitted. Use a fresh output directory for each invocation. The script never substitutes policy-fixture answers for a failed model request.
