# v3.5-rc2 binding amendment 01 final closure audit

Audit date: `2026-07-22`  
Audit mode: read-only directed closure audit, IEEE TDSC-oriented  
Combined specification: `v3.5-rc2 + v3.5-rc2-binding-amendment-01`  
Formal experiment execution: none  

## 1. Executive verdict

`DESIGN-FREEZE-FAIL`

| Root | Closure | Basis |
|---|---|---|
| `P0-STAT-01` | `CLOSED / PASS` | All 20 required two-phase acceptance items pass. The current verifier executed both complete CI paths and returned exit code 0. |
| `P0-STAT-02` | `NOT CLOSED / FAIL` | One required acceptance item fails: the verifier does not execute a **bound-schema-valid partial-record synthetic case**. Its only partial witness is a 5-prompt, `synthetic_data=true`, fixture-mode payload, while the bound production schema requires 50 prompts and `synthetic_data=false`. |
| Amendment/base regression | `NONE FOUND` | Base 25/25 hashes, component/aggregate/release bindings, frozen scope, estimands, claim boundary, and resource budgets all remain intact. |

The three required verifiers all return 0. That establishes the behavior they
cover, but it does not override the independent acceptance checklist. The
retained verifier calls its partial case only "Schema-shaped" and never applies
Draft 2020-12 validation to that payload. Therefore section 6.4(10) of the final
audit instructions is not satisfied, and the rule "only all items PASS closes
`P0-STAT-02`" requires `DESIGN-FREEZE-FAIL`.

This is the original `P0-STAT-02` closure root remaining incomplete, not a new
experiment-design P0. No new model, sample, endpoint, output, or experiment is
needed to repair it.

## 2. Audit method and evidence boundary

The main auditor read the five required normative/review documents, recursively
reviewed the amendment writing and implementation directories, independently
reviewed the schemas, references, fixed fixtures, component manifests,
aggregate/release manifests, and verifier control flow, and reran all three
required commands from the repository root with project-local temporary
directories. Three internal subagents separately reviewed `P0-STAT-01`,
`P0-STAT-02`, and artifact/scope integrity; the main auditor independently
rechecked the decisive code and constraints.

No audited file was modified. No formal P1, support, generation, judge, or
human experiment was run. The only file created by this audit is this report.

## 3. Current verifier receipts

All commands were run from `D:\llama_prefix` after setting `.codex-temp` as
`TEMP` and `TMP`, `NX_DAEMON=false`, and `PYTHONDONTWRITEBYTECODE=1`.

| Command | Complete success marker | Exit |
|---|---|---:|
| `python -B scripts/stage3_design/v3_5_rc2_binding_amendment_01/two_phase/verify_two_phase_golden.py` | `TWO_PHASE_AMENDMENT_GOLDEN_PASS artifacts=9 prompt_success=9999 vector_success=9988 failure_cases=15` | 0 |
| `python -B scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/verify_golden.py` | `RETAINED_BOOTSTRAP_GOLDEN_PASS` | 0 |
| `python -B scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py` | `AMENDMENT_STATIC_VERIFICATION_PASS` | 0 |

The aggregate JSON additionally reported:

```text
base_files_unchanged=25
binding_artifacts=24
component_artifacts=17
release_artifacts=27
direct_reference_modules=2
golden_verifiers=2
synthetic_fixture_files=9
scope_files_scanned=18
formal_data_used=false
no_scope_expansion=true
logical_generation=5580
first_pass_scheduled_judge=5580
human_items=720
```

## 4. P0-STAT-01 acceptance

Result: `CLOSED / PASS (20/20)`.

| # | Status | Evidence |
|---:|---|---|
| 1 | PASS | Current source is 61,277 bytes, SHA256 `de740ce4a63218eddf189b55ced9f7bd4c554d615c770da8c3c02a117e2faec3`; component manifest lines 34, 40-44, aggregate manifest line 75, and release manifest line 72 agree. |
| 2 | PASS | Bound schema uses Draft 2020-12 `prefixItems` plus `items:false` at `two_phase_input.schema.json:29-38`; reference executes `prefixItems`, `allOf`, and `items:false` at `two_phase_reference.py:149-213`. |
| 3 | PASS | The valid ordered two-member fixture passes schema and semantic validation and reaches both full CI implementations; `verify_two_phase_golden.py:289-305`. |
| 4 | PASS | Third-member, reversed-member, and wrong-type witnesses are fixed at `schema_negative_input.json:5-8` and checked at `verify_two_phase_golden.py:113-178`. |
| 5 | PASS | `validate_input` calls the bound schema before semantic and cross-frame validation; no fixture bypass exists; `two_phase_reference.py:679-718`. |
| 6 | PASS | Prompt-category strata are consumed in canonical order, each with frame-size replacement draws; `two_phase_reference.py:778-783`. |
| 7 | PASS | Non-census phase-two strata consume exactly `n_h-1` SRSWOR Rao-Wu draws and apply the fixed `g_hi` formula; `two_phase_reference.py:785-804`. |
| 8 | PASS | Census consumes zero draws; `n_h=0`, `n_h=1<N_h`, invalid pi, and empty arm have fixed first failures; `two_phase_reference.py:582-628,727-765,785-804`, `failure_expected.json:5-19`. |
| 9 | PASS | Vector-aware sensitivity draws the exact 20-vector frame and executes the same simultaneous family; `two_phase_reference.py:806-812,954-1040`. |
| 10 | PASS | Prompt and vector multiplicities multiply judge weights; residual weights additionally multiply `1/pi` and Rao-Wu `g_hi`; `two_phase_reference.py:862-881`. |
| 11 | PASS | Exact canonical serialization, block IDs, sync IDs, frame hashes, one-based seed payload, counter endian/order, and draw order are fixed at `two_phase_reference.py:276-358,394-439,778-854`. |
| 12 | PASS | `member` and `member_id` are forbidden in shared sync objects; one draw plan is shared before fixed-order member evaluation; `two_phase_reference.py:276-281,963-979`. |
| 13 | PASS | Every successful replicate recomputes matched judge rates, Hajek residuals, clipping, and RD; `two_phase_reference.py:862-901`. |
| 14 | PASS | Common-set Bessel SE, fixed-scale studentization, `K_b`, nearest-rank `q_max`, and simultaneous endpoints are uniquely computed; `two_phase_reference.py:981-1011`. |
| 15 | PASS | Production constants remain 9,999 replicates and 9,500 common successes; `two_phase_reference.py:25-27`, component manifest lines 9-21. |
| 16 | PASS | Replicates are never rerolled; a member failure discards the replicate jointly and no memberwise/marginal fallback is evaluated; `two_phase_reference.py:963-998`. |
| 17 | PASS | No reference/verifier write API targets expected files. Fixed expected identities remain `efcc9972...f9821` and `0304e69f...17cf6`; repair completion lines 92-100 and current manifests agree. |
| 18 | PASS | Current success/failure outputs are compared by canonical byte equality with the fixed expected files; `verify_two_phase_golden.py:292-297`. |
| 19 | PASS | Current execution reports prompt common successes `9,999` and vector-aware common successes `9,988`; `success_expected.json:34-41,75-82` and the live marker agree. |
| 20 | PASS | The verifier exercises 9,499 fail, 9,500 pass, census, vector, RNG bytes/rejection, multiplicity, shared stream, clipping, schema-negative cases, and all 15 fixed failures; `verify_two_phase_golden.py:232-301`. |

No residual `P0-STAT-01` ambiguity, fallback, or repair-induced regression was
found.

## 5. P0-STAT-02 acceptance

Result: `NOT CLOSED / FAIL`. The only failing root is section 5.4 item 10 below.

### 5.1 Identity and core statistics

| # | Status | Evidence |
|---:|---|---|
| 1 | PASS | Current retained source is 46,975 bytes, SHA256 `90ea4091c1799926efc166b1e69d54c0b9b37fdc3c35af47146109f590d46dc6`; component manifest lines 32-34/51, aggregate line 73, and release line 70 agree. |
| 2 | PASS | Executable production entries are `analyze_k1`, `analyze_harmful_clean`, and `analyze_benign_broken`; `retained_bootstrap.py:376,547,639`. |
| 3 | PASS | K1 fixes prompt/vector frames, complete coordinates, sample sizes, and product multiplicity; `retained_bootstrap.py:380-387,429-488`. |
| 4 | PASS | K1 prompt/vector draws occur before the cell loop and are reused by all four cells; `retained_bootstrap.py:472-503`, verifier lines 239-248. |
| 5 | PASS | Harmful clean draws the complete frozen prompt-frame size with replacement; `retained_bootstrap.py:553-556,594-605`. |
| 6 | PASS | Benign computes each prompt's 20-vector average before prompt resampling; `retained_bootstrap.py:704-737`, verifier lines 249-252. |
| 7 | PASS | Block IDs, exact canonical sync identities, frame hashes, and order checks are fixed; `retained_bootstrap.py:28-30,120-182,424-452,574-587,697-712`. |
| 8 | PASS | Each block fixes 10,000 replicates and 9,500 common successes; `retained_bootstrap.py:24-26,303-350`. |
| 9 | PASS | Only nearest-rank percentile 95% intervals are emitted; `retained_bootstrap.py:221-230,324-343`. |
| 10 | PASS | Zero bootstrap SD yields only a point-degenerate flagged interval; `retained_bootstrap.py:327-333`, expected lines 98-104. |
| 11 | PASS | Output declares `descriptive_or_ci_only_no_test`; no p-value, rejection, significance, or confirmation output exists; `retained_bootstrap.py:354-363`, retained README lines 116-122. |

### 5.2 Canonical digest and success golden

| # | Status | Evidence |
|---:|---|---|
| 1 | PASS | K1, harmful-clean, benign-broken, and zero-SD digests are fixed at `success_golden_expected.json:39,77,89,99`. |
| 2 | PASS | Each digest is `SHA256(UTF8(canonical_json(full analyzer output)))`, computed in the same run; `retained_bootstrap.py:73-85,842-878`. |
| 3 | PASS | The current success projection equals the fixed expected canonical JSON; verifier lines 140-158 and current marker. |
| 4 | PASS | Expected files are read only; no reference or verifier write path exists. Their physical hashes remain `d9eae2cd...25940` and `e795e84f...b1e9`. |
| 5 | PASS | The verifier independently reruns all four full analyzers and hashes them using its own canonical helper; `verify_golden.py:25-40,160-177`. |

Observed fixed full-output digests:

| Output | SHA256 |
|---|---|
| K1 | `67cdb361b2c0782cacbcbfaebe44291af1a04330578359b4b4b896cee23e4f1e` |
| harmful clean | `d355f23ea9c37e8a8ead29129f0d24f8b3df4dacf26f78a05c8d445f7413148f` |
| benign broken | `8f14e7ef96dad68ca9ea14ce89b9567ab9625aa914bb6ab236589b8df1adc129` |
| zero SD | `b58797fc89c56e001696a652d1431e79e905393da1ca123bdeb3d99b42b91558` |

### 5.3 Invalid-denominator witness

| # | Status | Evidence |
|---:|---|---|
| 1 | PASS | Formal harmful records remain nonempty: production schema `minItems=1` at `retained_bootstrap_schema.json:102-107`; formal/reference entry rejects an empty list at `retained_bootstrap.py:557-561`. |
| 2 | PASS | Formal header/frame/identity/order precedence was not rewritten to force denominator failure; `retained_bootstrap.py:547-588`. |
| 3 | PASS | The synthetic failure-contract unit witness directly calls `_profile_point([], HARMFUL_LABELS)` and is explicitly not a formal input; `retained_bootstrap.py:935-937`. |
| 4 | PASS | The helper returns exactly `INVALID_DENOMINATOR / profile denominator is zero`; `retained_bootstrap.py:366-370`. |
| 5 | PASS | The fixed failure expected line 8 is unchanged and current canonical failure equality passes; verifier lines 157-158, 280-283. |

### 5.4 Harmful-clean partial-record missingness

| # | Status | Evidence |
|---:|---|---|
| 1 | PASS | Production schema fixes a 50-prompt frame and permits 1..50 retained records; `retained_bootstrap_schema.json:93-107`. |
| 2 | PASS | Records are a duplicate-free canonical subset of the frozen frame; complete coverage is not required; `retained_bootstrap.py:570-587`, retained README lines 42-45. |
| 3 | PASS | Missing prompts enter neither numerator nor denominator; only retained rows are weighted; `retained_bootstrap.py:603-612`. |
| 4 | PASS | The point denominator is exactly `len(records)`; `retained_bootstrap.py:366-373,588`. |
| 5 | PASS | Every replicate still draws exactly the complete prompt-frame size; `retained_bootstrap.py:599-605`. |
| 6 | PASS | A zero replicate denominator records a common failure and continues without reroll; `retained_bootstrap.py:606-609`. |
| 7 | PASS | The common-success floor remains 9,500; `retained_bootstrap.py:303-322`. |
| 8 | PASS | Out-of-frame rows, row/coordinate collisions, and noncanonical subset order continue to fail; `retained_bootstrap.py:570-587`, verifier lines 209-218/269-278. |
| 9 | PASS | Empty formal records remain `INPUT_SCHEMA_INVALID`; `retained_bootstrap.py:557-561`, verifier lines 220-227. |
| 10 | **FAIL** | The only executed partial witness (`verify_golden.py:179-182`) truncates the existing fixture to three records but retains `synthetic_data=true` and a five-prompt frame. The bound schema requires `synthetic_data const:false` at `retained_bootstrap_schema.json:98-100` and exactly 50 prompts at line 101. The verifier calls only `analyze_harmful_clean(..., fixture_mode=True)` and never performs Draft 2020-12 schema validation on this partial payload. Its own comment says only `Schema-shaped`. |

Independent main-auditor diagnostics reproduced the mismatch:

```text
PARTIAL_WITNESS_SYNTHETIC_DATA True
SCHEMA_SYNTHETIC_CONST False
PARTIAL_WITNESS_PROMPT_COUNT 5
SCHEMA_PROMPT_COUNT 50 50
BOUND_SCHEMA_VALID_BY_FIXED_CONSTRAINTS False
```

An in-memory 50-prompt/3-record production-shaped control then executed the
same analyzer successfully with point denominator 3, draw size 50, 9,550
common successes, and 450 zero-denominator failed replicates. This confirms
that the retained estimator implements the intended missingness target. The
failure is the required schema-valid executable witness and binding, not the
estimator or RNG.

### 5.5 Retained goldens

| Coverage | Status | Evidence |
|---|---|---|
| Fixed success/failure canonical equality | PASS | `verify_golden.py:140-158` |
| RNG bytes, rejection, block/sync identity | PASS | `verify_golden.py:239-257`; fixed success expected lines 4-35 |
| K1 product multiplicity and shared four-cell draws | PASS | `verify_golden.py:239-248` |
| 9,499 fail / 9,500 pass | PASS | `verify_golden.py:264-268`; failure expected lines 9-10 |
| Degenerate zero-SD interval | PASS | `verify_golden.py:258-263`; success expected lines 98-104 |
| Partial-record behavior in fixture mode | PASS | `verify_golden.py:179-218` |
| Required schema-valid partial-record synthetic coverage | **FAIL** | Same minimal root as section 5.4(10) |

Because every retained acceptance subsection must pass, `P0-STAT-02` remains
open despite the verifier's current PASS marker.

## 6. Amendment integrity

| Integrity item | Status | Current evidence |
|---|---|---|
| Base rc2 snapshot | PASS | Independent SHA256: 25/25 match, 0 missing/mismatch; snapshot physical SHA256 `62cdc07760c709799a2a1cce17177df1fabe838a3f0d5054d853bd6d839a722d`; verifier `verify_amendment.py:144-167`. |
| Two-phase component manifest | PASS | Physical `4bbca707...8248`, 5,600 bytes; self `e1a18122...4fa2`; 9/9 artifact hash/length matches. |
| Retained component manifest | PASS | Physical `e685a60c...00ae`, 4,119 bytes; self `b62dd2c1...e1bc`; 8/8 artifact hash/length matches. |
| Aggregate binding manifest | PASS | Physical `00d21dd5...74b9`, 9,572 bytes; self `1a317da1...af1e`; 24/24 exact inventory, 7/7 transitive dependencies. |
| Release manifest | PASS | Physical `1f0ece91...8d96`, 7,284 bytes; self `0e32aa55...cc6b`; 27/27 exact inventory. |
| Repair completion registration | PASS | Release manifest line 48 binds report SHA256 `1bf484e4...5b30`, length 9,342. No unbound normative amendment artifact was found. |
| Fixed expected goldens | PASS | Two-phase `efcc9972...f9821` / `0304e69f...17cf6`; retained `d9eae2cd...25940` / `e795e84f...b1e9`; all current physical hashes match their manifests. |
| Manifest mismatch fail-closed | PASS | Artifact mismatch raises at `verify_amendment.py:185-192`; main returns 1 at lines 691-699. An in-memory negative injection returned exit 1 with `manifest artifact hash mismatch`. |
| Verifier authenticity | PASS | Aggregate imports references, directly executes success/failure analyzers and canonical comparisons, checks coverage/RNG, then subprocess-runs component verifiers; `verify_amendment.py:320-399,402-592`. |
| Fixture vs production defaults | PASS with closure gap | Fixture mode does not change 9,999/9,500 or 10,000/9,500. It permits reduced synthetic frames. The missing schema-valid partial witness is separately recorded as the sole P0 failure. |
| `audit_disposition.md` gate | PASS as a receipt, not final verdict | Its two rows record executable-binding verifier PASS only and explicitly do not announce final design-freeze acceptance; current three verifier exits are all 0. |
| Formal-data/scope flags | PASS | Component, aggregate, release, and verifier contract agree on `formal_data_used=false`, `no_scope_expansion=true`; all nine fixture JSON files have top-level `synthetic_data=true`. |

## 7. Scope and resources

| Boundary | Frozen value | Audit result |
|---|---|---|
| Execution profile | compact single-GPU, Qwen-only behavior | PASS, unchanged |
| P1 | 100 harmful + 100 benign | PASS, unchanged |
| P2 | `P=50`, `V=20`, A/T, estimation-only | PASS, unchanged |
| K1 | reuse of four P2 cells | PASS, zero new generation/judge identities |
| Benign candidate support | 30 prompts, 20 vectors for T-steered rows | PASS, unchanged |
| Human validation | 720 response items; 1,440 primary assignments; upper bound 2,160 | PASS, unchanged |
| Logical generation | 5,580 | PASS, unchanged |
| First-pass scheduled judge | 5,580 | PASS, unchanged |
| Two-phase resampling | 9,999 per prompt/vector block, 9,500 common-success floor | PASS, existing CPU post-processing |
| Retained resampling | 10,000 per block, 9,500 common-success floor | PASS, existing CPU post-processing |
| GPU generation vs CPU statistics | Separate resource classes | PASS; bootstrap work does not add logical generation, judge, or human samples |
| Prohibited restoration | model-based RD/CI, power/coverage, selector, K2, V2, attention, rendering 2x2, stochastic decoding, phase confirmation | PASS; all remain absent/false |
| Claims | no P2 p-value, global test, rejection, significance, confirmation, or prospective power claim | PASS, unchanged |

The amendment does not change an estimand, missingness target, endpoint,
identity family, or evidence-to-claim boundary. The partial-record witness gap
is a verification/binding defect inside the registered repair and does not
justify scope expansion.

## 8. Non-P0 disposition

| Class | Finding | Disposition |
|---|---|---|
| A0 | Real checkpoint/tokenizer/template, prompt-frame, base-anchor, and vector identities are not materialized. | `RUN-BLOCKED`; not a design-freeze failure. |
| A0 | The required result root and nine checked `protocol/*.json` identity/runtime/freeze artifacts are absent, including `experiment_identity_manifest.json`, `base_anchor_manifest.json`, `measurement_specification_freeze.json`, `measurement_result_dose_manifest.json`, `judge_freeze.json`, `support_execution_manifest.json`, `behavior_confirmation_freeze.json`, `inference_backend_manifest.json`, and `human_validation_sample_freeze.json`. | `RUN-BLOCKED`; not repair-induced. |
| I0 | Remaining execution-specific E0 fixtures and production pipeline integration are not verified ready. | `RUN-BLOCKED`; implementation-fidelity work after design closure. |
| P1/P2 | Archived publication/fidelity observations, including the auxiliary judge-error diagnostic wording, are not caused by this repair and do not control a retained formal estimate/status/claim. | Do not promote or reopen in this directed audit. |
| DUPLICATE | Historical PASS text and `audit_disposition.md` verifier receipts. | Do not use as substitutes for current execution or for the missing schema-valid partial witness. |
| SCOPE_REINTRODUCTION | Restore model-based inference, selector/simulation, K2/V2, attention/rendering/stochastic blocks, phase confirmation, more models/samples, or a testing gate. | Rejected. |

No separate new `TRUE_P0` was registered. The sole failure is deduplicated into
the original `P0-STAT-02` closure criterion.

## 9. Minimal final action

Do not run the formal experiment and do not start another open design review.

The only permitted repair is to add and bind one genuinely schema-valid
partial harmful-clean synthetic witness that:

1. uses the complete 50-prompt frozen-frame shape and 1..50 ordered retained records;
2. is explicitly synthetic without being presented as valid formal data;
3. is validated by an explicit bound Draft 2020-12 schema path (for example, a
   narrowly bound synthetic-fixture schema/overlay that preserves all
   production structural constraints); and
4. is then passed to `analyze_harmful_clean`, with point denominator, full-frame
   draw size, zero-denominator replicate handling, and common-success count
   asserted.

The repair must not relax production `records.minItems=1`, redefine empty
formal records, change failure precedence, alter RNG/estimand/10,000/9,500,
rewrite existing fixed expected goldens, or change any scope/resource/claim
boundary. The new witness/schema/verifier changes must be added to component,
aggregate, and release bindings and all self hashes refreshed only after the
component golden remains green.

After that minimal repair, rerun the same three verifier commands and repeat
only this directed closure check. If every item then passes, stop all protocol
and amendment version iteration, declare the combined specification the sole
frozen baseline, and proceed only to E0, runtime manifests, and
implementation-fidelity audit. Until the user chooses whether to apply this
repair, the current verdict remains `DESIGN-FREEZE-FAIL`.
