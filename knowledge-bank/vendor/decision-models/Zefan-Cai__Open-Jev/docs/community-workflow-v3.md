# Original approval and CMS controls

`community-workflow-v3` adds **8,280 original synthetic decisions** across two
task sources. It is a supplement for policy/evidence reasoning, not collected
user data, a replacement for human-labeled corpora, or a measured model result.

| Source | Decisions | Source scenarios | Related contexts | Views per context |
| --- | ---: | ---: | ---: | --- |
| Approval | 2,880 | 180 | 1,440 | Three-way Choice and one permission Noul |
| CMS tags | 5,400 | 180 | 1,080 | Three-way editorial Choice and four independent tag Nouls |
| Total | 8,280 | 360 | 2,520 | 2,520 Choice and 5,760 Noul decisions |

Each source has ten authored rule cards. Six cards are training-only; one each
is reserved for calibration, validation, test and OOD. Every scenario, paraphrase
and counterfactual belonging to a card stays in that split. The default mixture
contains 4,968 training decisions and 828 in each other split. OOD means new
authored cards within the same controlled reporting grammar, not demonstrated
transfer to arbitrary new domains.

The row sources are `community-workflow-v3/approval` and
`community-workflow-v3/cms`. The usual data contract carries `state`, `question`,
`kind` and `options` to the model. IDs, split assignments, provenance and targets
remain outside the model input. State values are prose strings; there are no
gold flags, boolean fact tables or precomputed rule outcomes inside them.

## Task definitions

Approval state contains a policy, the requested operation and an operations log.
The policy defines the exact operation, two required confirmations, a quantitative
limit and the scope of an emergency exception. A verified exception waives only
the first confirmation. It cannot waive the second confirmation or the limit.
The model chooses **permit, deny or review**; the Noul asks whether action is
permitted now.

The policy explicitly defines evidence handling: applicant assertions and quoted,
archived or hypothetical log entries cannot establish authorization. A known
requirement with uncontradicted explicit counterevidence causes denial; missing or conflicting required evidence
causes review unless a separate known failure already requires denial. An
instruction not to perform the covered operation causes denial. An out-of-scope operation
requires review. These are visible task rules, not assumptions made by the labeler.

Each scenario has eight views of its context: supported, denied requirement,
missing requirement, documented exception, claimed exception, negated request,
conflicting evidence and an exceeded quantitative limit. Topics cover restarts,
credential rotation, test fixtures, deployments, support exports, reader access,
pricing publication, settlement retries, archival and shipment cancellation.
No command is executed.

CMS state contains four independent tag definitions and an original short article.
The four Nouls ask whether each tag is supported; more than one may be true.
The editorial Choice distinguishes applying supported tags, leaving an article
untagged when all tags are ruled out, and requesting review for unresolved evidence.
Quoted claims, archive snippets, hypotheses and mere tag-name mentions do not
establish applicability. A withdrawn announcement rules its positive claim out.
Current affirmative and negative claims conflict; paragraph order does not imply
which is newer. The task deliberately distinguishes unknown from explicit denial,
even though both yield `no` to “is this tag justified now?”

CMS counterfactuals preserve neighboring topics while changing one claim to a
negation, quotation, absence, withdrawal or contradiction. Other tag claims vary
across 18 distinct combinations: eight affirmative/negative combinations and ten
combinations containing missing or contradictory evidence. Cards cover software, city notices, universities,
retail, arts, libraries, science, developer documentation, workplace policy and
environment notices. They are ten controlled editorial settings, not ten newly
collected external datasets.

## Validation and limits

The visible-input oracle parses the documented reporting forms and policy text.
It never reads a target, metadata, scenario index or latent generator flag.
All stored labels are checked against this visible-input reconstruction.
Hand-specified counterfactual tests check exception scope, missing evidence,
authorization claims, negation, multiple tags, quotations and contradictions.
Candidate permutations must permute the target; changing IDs/metadata must not.

The separate [portable auditor](../reports/community-workflow-v3/audit_visible_records.py)
does not import or execute the generator or either of its label functions. It
reads only the declared phrase vocabulary as Python AST literals, then independently
parses evidence, computes decisions, infers the rule family from visible policy,
checks its split, and counts normalized semantic scenarios. Its
[frozen report](../reports/community-workflow-v3/independent-audit.json) covers all
8,280 records with zero target mismatches and binds the generator, manifest and
all five split hashes. The shared vocabulary remains a limitation; this is an
independent implementation of the controlled contract, not human annotation.

The release audit also checks prose-only state, whole-card/scenario splits,
duplicate contexts, file checksums, paragraph-order invariance and whether each
fixed question/candidate contract has multiple observed answers. This detects
some shortcuts; it does not prove that no linguistic shortcut exists. The oracle
recognizes a finite authored grammar, so it is not an independent general-language
semantic judge. Related contexts and task views are correlated observations.

Normalization removes paragraph order, reporting wrappers and display names while
retaining the rule, quantitative constraints and evidence channel. Each source has
180 distinct semantic scenarios; approval has 1,440 normalized contexts and CMS
has 1,080. CMS has only 390 distinct authoritative truth states: missing evidence
and conflicting evidence are different contexts that both resolve to unknown.
These separate counts prevent formatting changes from inflating semantic coverage.

The harder secondary-tag contexts change the CMS editorial label distribution:
840/1,080 choices request review (77.8%), 220 apply tags, and 20 leave the article
untagged. Approval has 360 permits, 720 denials and 360 reviews. The builder records
this imbalance; it does not claim balanced natural prevalence. Generation is
bounded to 18 scenarios per card to avoid cycling through the same semantic cases.

Sources are entirely original code-authored text, released as **CC0-1.0 data**.
The generator makes no network/model calls and reads no external examples,
JevBench items, benchmark questions/gold, private commands or customer documents.
Community research motivates the task categories only; no post text is copied
into training. See [the source review](community-research-broadening-20260921.md)
for the separate real-data and licensing gaps.

Generate into a new directory and verify locally:

```bash
python -m jev.community_workflow_v3 --output-dir data/community-workflow-v3
python -m unittest discover -s tests -p test_community_workflow_v3.py -q
python reports/community-workflow-v3/audit_visible_records.py --data-dir data/community-workflow-v3
```

The builder refuses nonempty or symlinked output directories. Its manifest binds
all five split files and the generator source hash. Prepared data live under the
ignored `data/` directory; the tracked
[report](../reports/community-workflow-v3/README.md) records counts and validation.
Data preparation does not change the existing training iteration or demonstrate
improved Jev/Open-Jev/GPT quality.
