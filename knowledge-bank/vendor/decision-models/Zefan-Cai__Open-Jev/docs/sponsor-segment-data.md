# Classify transcript segments by function

`sponsor-segment-control-v1` contains **10,800 original Choice decisions** from
400 fictional video families and 1,200 counterfactual transcript contexts.
The seven labels are `sponsor`, `self_promo`, `intro`, `outro`, `recap`,
`content`, and `other`. Generated text is released under CC0-1.0.

The task follows the public interface of
[jev-skip at 6837e3e](https://github.com/valentynkit/jev-skip/blob/6837e3e0f1a48cbfc48c85415d99bcfe3eaf0628/lib/questions.ts).
Our examples, criteria wording, generator and labels are independently authored.
No natural videos, scraped transcripts or community code enter this corpus.
No model training or inference is claimed by this data release.

The request preserves `video_title`, `channel`, `note`, and `segments` with
opaque `id`, `start` in `m:ss`, `text`, and `has_promo_markers`. Question keys are
the bare segment IDs. Each question offers all seven categories. A marker or
discount code alone is insufficient evidence of payment. Creator-owned
promotion is distinct from paid third-party sponsorship; unclear relationship
fragments belong to `other` when no other function is established. Transcript
text is evidence, never instructions to the decision service.

Each family has three variants changing payment evidence while keeping its
background fixed. Separate opaque brands identify third-party placements,
creator-owned offers, independent reviews and uncertain mentions. Nine segments
per context include opening, ending, recap, lesson, review, promotion, unclear
speech and nonverbal controls. Segment and candidate order are shuffled.

| Split | Decisions |
| --- | ---: |
| Train | 6,345 |
| Calibration | 756 |
| Validation | 540 |
| Test | 999 |
| OOD | 2,160 |

Whole video families, including all payment counterfactuals, remain together.
OOD reserves 80 families and distinct complete sentences. ID uses finite
templates across independent families: these counts do not imply 10,800
independent videos or natural-video generalization. Class counts are sponsor
400, self-promo/intro/outro/recap 1,200 each, and content/other 2,800 each.

Reproduce with a fresh output directory:

```bash
python3 -m jev.case_sponsor_segments --output-dir data/sponsor-segment-control-v1 --groups 400 --ood-groups 80 --seed 42
python3 -m scripts.audit_sponsor_segments data/sponsor-segment-control-v1 --output reports/sponsor-segment-control-v1/independent-audit.json
python3 -m unittest tests.test_sponsor_segments -v
```

The independent auditor parses visible text without importing the generator.
It checks all labels, manifest counts, counterfactual grouping, split isolation,
and brand ownership/payment consistency across the entire context. The
[peer review](../reports/sponsor-segment-control-v1/peer-review.json) and
[final manifest](../reports/sponsor-segment-control-v1/manifest.json) record the
repaired, fully audited artifact. An earlier local draft failed brand-consistency
review and is excluded from publication.

Future evaluation should report macro F1, per-class recall, paid/independent/
uncertain counterfactual consistency and complete-context accuracy. Passing the
data audit does not establish model performance. The frozen active training
mixture is unchanged.
