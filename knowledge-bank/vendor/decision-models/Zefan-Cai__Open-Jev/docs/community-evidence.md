# Five community reports and what we can test

These five public X posts were read back on 2026-10-02. Exact text, author,
timestamp, retrieval status and text hashes are preserved in
[`reports/community-evidence-20261002`](../reports/community-evidence-20261002/sources.json).
They describe TypeSafe Jev and related experiments. They are not Open-Jev
customer endorsements, and their measurements have not been independently
reproduced by this project.

| Source | Exact excerpt | Implication for Open-Jev |
|---|---|---|
| [@rahulbuildsmore](https://x.com/rahulbuildsmore/status/2100581721515188451) | “Jev decides sentiment, topic, \"bug?\" and churn risk for 1,000 real app reviews” | Evaluate natural text, full workflow latency and label quality together. The reported 4.6 s / $0.023 are the author's results. Dataset licensing needs confirmation before reuse. |
| [@TechNerdings](https://x.com/TechNerdings/status/2101737805932044637) | “#SAST code audit during PRs via a GH workflow” | A useful decision must reach a reviewable artifact. Security recall requires an explicit labeled test; this post supplies no independent accuracy denominator. |
| [@identityTorn](https://x.com/identityTorn/status/2100475121324728615) | “within ~5 pts of recall of our fine-tune at matched precision” | Measure error at a fixed operating point, coverage and human review. The private benchmark cannot establish Open-Jev's recall. |
| [@ajmeese7](https://x.com/ajmeese7/status/2101786516758667265) | “searching through 6TB of old drives to find which files have the most value. This cost $6” | Track completed useful decisions and manual work saved. 6 TB describes the collection, not measured model input volume. |
| [@iamMrDuncan](https://x.com/iamMrDuncan/status/2100467548298899918) | “TypeSafe was way cheaper, and did beat Qwen on performance” | Compare a decision model with a generative/provider baseline on identical data and hardware or billing assumptions. This is an author's comparison, not our reproduction. |

## Chosen application: support routing

The first implementation is [natural support routing](support-routing.md),
using the licensed BANKING77 official data rather than invented users.
BM25 chooses eight intents without using the answer; Open-Jev scores those
and an explicit review option. The workflow freezes a confidence policy on
calibration, measures the held-out official test, and exports a review queue
and final CSV. Candidate recall, routing error, abstention and review
completion are separate measurements.

The [local trial](../examples/support-routing/index.html) calls the actual
checkpoint server and records its identity. Human corrections require an
identified reviewer. An automated end-to-end run is engineering evidence;
an actual user story requires a participating human. External users and
completed human trials remain zero until a saved, consented pilot establishes
otherwise. We do not convert these five posts into our own user testimonials.
