# Paper 1 Stage 3 P1 harmful selection report

## Verdict

**P1-HARMFUL-SELECTION-CANDIDATE-PASS**

This is a nonformal, pre-outcome candidate binding package. It is not a formal prompt freeze, `FORMAL_INPUT`, `RUN-READY` declaration, lifecycle event, model/judge run, or experimental result.

## Source identity

- Repository: `Libr-AI/do-not-answer`
- Revision: `460703484df354958a5e1cd7378a38fcb94a2f3e` (verified commit)
- Commit tree: `e23f78c25dcc6e92e0dc23b395a71d243d892d44`
- Source path: `datasets/Instruction/do_not_answer_en.csv`
- Git blob OID: `402fe774e8f81a18cbe6956e49d4ec287887a771`
- Raw bytes: `329395`
- Raw SHA-256: `06acfa39a06a1b33d1f264ce41b4f7a95812010c594fb733ae4717ee0a4544fc`
- Dataset license: `CC-BY-NC-SA-4.0`

The commit tree path resolves to the stated blob OID, and `git hash-object --no-filters` over the fixed raw bytes reproduces that OID. The pinned README assigns CC BY-NC-SA 4.0 to repository datasets.

## Selection

The strict `risk_area == "Malicious Uses"` pool contains 243 rows before the fixed exclusions `540, 612, 667, 757`, and 239 eligible rows afterward. Eligible stratum capacities are 130, 70, and 39. Hamilton allocation of 100 gives the fixed quotas 55, 29, and 16.

Canonical record identity and selection-rank hashes were recomputed from exact UTF-8 question bytes. The provisional quota selection contained 100 rows. Pre-outcome duplicate/leakage review conservatively excluded 12 source IDs and replaced each with the next record in the precomputed same-stratum rank order. The complete 239-row ranking and all 12 mappings are preserved in `selection_trace.json`.

Final frame SHA-256 (canonical ordered record-identity list): `afcb3bcfe3042bf37189fc9718b53389ce0145e43b75efc3364e250e86552410`.

## Duplicate and leakage review

- Source-wide normalized exact duplicate groups: one (`433/434`), outside the fixed eligible pool.
- Final selected internal normalized exact duplicates: 0.
- Final selected-to-JBB normalized exact overlaps: 0.
- Approximate review: word-token Jaccard and normalized character 5-gram Jaccard generated review candidates; conservative rule review produced the documented 12 exclusions.
- The replacement frame was rescanned. All remaining high-threshold and expanded conservative candidates were judged to have distinct core behavior, target, or artifact.

This process does not claim a model-level semantic nonduplication guarantee.

## Independent audits

Auditor A, B, and C independently audited the actual core files. All three returned `PASS` with `findings=[]`. A covered source/Git/blob/license/attribution, B covered quota/hash/selection/frame order, and C covered duplicate/leakage/replacement/protocol boundaries.

All JSON artifacts use explicit schemas, strict UTF-8, finite JSON values only, and a canonical self hash computed after removing the top-level `self_sha256`. `checksums.sha256` binds all other package files and excludes itself to avoid self-reference. The main repository Git status matches the task-start baseline; the package remains only under `.codex-temp`.

## Boundary

```text
formal_inputs = []
formal_experiment_run = false
repository_modified = false
candidate_only = true
```

Stop here for experiment-lead review. Do not move this package into the formal `data/` directory without a separate authorized binding step.
