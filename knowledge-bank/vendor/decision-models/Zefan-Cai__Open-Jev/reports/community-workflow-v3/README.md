# Community workflow v3 preparation

Original approval and CMS prose controls; no external examples, API calls or GPU
work. Data and protocol are described in
[community-workflow-v3.md](../../docs/community-workflow-v3.md).

The default corpus contains 8,280 decisions: 2,880 approval and 5,400 CMS; 360
source scenarios, 2,520 related contexts, and 20 authored rule cards. The 4,968
training decisions use six cards per source. Calibration, validation, test and
OOD each contain 828 decisions from their own whole cards.

After removing cosmetic paragraph order/wrappers, the audit retains 180 semantic
scenarios per source and all 2,520 semantic contexts. CMS has 390 distinct
authoritative truth states. Its 1,080 editorial Choices contain 840 review,
220 apply-tags and 20 untagged outcomes; the 77.8% review rate reflects deliberately
difficult controls rather than estimated production prevalence.

`manifest.json` binds the prepared split files and generator. The
`visible-input-audit.json` report records label reconstruction and shortcut checks.
`validation.json` records the focused CPU tests and independent source review.
The portable `audit_visible_records.py` independently evaluates the visible prose
without importing the generator. `independent-audit.json` records all 8,280 rows,
zero target mismatches, the rule families inferred from visible policy, semantic
counts, and the full manifest/generator/split hashes. Its phrase vocabulary comes
from bound AST literals; its evidence and label logic are implemented separately.

These are controlled synthetic prose examples and correlated counterfactuals,
not independently collected documents or human evaluation labels. No trained
capability or benchmark improvement is claimed.
