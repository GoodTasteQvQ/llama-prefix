# v3.5-rc2 B contract: freeze and execution status

This is the normative B-side merge specification for the v3.5-rc2 protocol. It closes the freeze
timing, judge timing, retained-identity predicate, and support/status mapping without running any
formal experiment. The executable interpretation is `scripts/stage3_rc2/freeze_contract.py`; the
machine-readable source is `freeze_execution_contract.json`; boundary behavior is locked by
`golden/freeze_execution_cases.json` and `v3_5_rc2_hash_manifest.json`.

The source rc1 file is read-only. Its SHA256 at the start of this work was
`f557fb8a06329f92778e9e1eb7ddb2822b05e80bf83784ba1ec243b9343fb85a`.

## Normative lifecycle

The realized execution event log must be an exact prefix of this list:

```text
1  IDENTITIES_AND_E0_VALID
2  MEASUREMENT_SPECIFICATION_FROZEN
3  P1_OUTCOME_VISIBLE
4  MEASUREMENT_RESULT_DOSE_FROZEN
5  JUDGE_DEVELOPMENT_MANUAL_COMPLETE
6  JUDGE_FROZEN
7  FORMAL_SUPPORT_GENERATION_STARTED
8  SUPPORT_EXECUTION_MANIFEST_FROZEN
9  BEHAVIOR_CONFIRMATION_FROZEN
10 FORMAL_CONFIRMATION_GENERATION_STARTED
```

No event may be skipped or reordered. Every freeze/manifest is append-only and content-addressed.
An amendment creates a new protocol version; it cannot replace an rc2 object.

### Pre-outcome measurement specification freeze

Rename rc1 `measurement_freeze.json` to `measurement_specification_freeze.json`. Create it before any
formal P1 forward, norm, complete-case flag, aggregate, exclusion, or result is visible. It binds the
200-prompt frame, identities, rendering/extraction rules, complete-case rule, estimands, exact bootstrap
implementation/count/quantiles/RNG, failure rules, base anchors, and producer identities.

This freeze must not contain `I_p_cc`, successful/excluded IDs, observed numerator/denominator/token
count, `mu`, `median_content_norm`, interval/gate output, `c_A/c_T/c_H`, alpha, or support status. The
freeze therefore specifies how to measure but contains no measurement outcome.

### Post-P1 measurement-result/dose manifest

After P1 terminates, create `measurement_result_dose_manifest.json` exactly once and hash it before
judge freeze or support generation. It references the specification freeze, experiment identity, and
base-anchor self hashes. It contains:

- all 200 scheduled P1 identities and terminal states, with one exclusion reason when excluded;
- ordered harmful/benign complete-case identity lists and hashes;
- exact pooled numerators, denominators, content-token count, realized shares, `mu_all_tw`,
  `mu_content_tw`, and `median_content_norm`, including decimal and binary64 representations;
- the exact numerator-frame identity list/hash and finite content-token count for
  `median_content_norm`;
- bitwise-copied `rho_A/rho_T/rho_H` and `c_k = rho_k * median_content_norm / mu_all_tw` for all
  three anchors, evaluated in that operation order;
- pre-dtype and post-dtype alpha for every used anchor/estimator pair, numeric conversion identity,
  parent/producer hashes, timestamp, and self hash.

Any nonfinite required value, zero required denominator, missing parent, hash mismatch, or formula
mismatch emits `P1_DOSE_NON_ESTIMABLE`, produces no substitute dose, and blocks support. This is not a
support failure and cannot activate a different anchor or execution profile.

### Judge freeze

`D_judge_dev` is the empty formal response set in rc2. Development is manual, document-only rubric
review: zero generation calls and zero automated judge calls. Author/reviewer time and non-call expense
are recorded in `judge_development_ledger.json`; they are a separate cost class and never enter the
formal 5,580 calls. A development model call requires a future protocol version.

Create and hash `judge_freeze.json` after the measurement-result/dose manifest and manual review, but
before the first formal support response is generated or visible. It fixes `Qwen/Qwen3-8B`, immutable
revision/weight/tokenizer/template identities, the harmful/benign rubric templates and priority orders,
runner/runtime/dtype, greedy settings, exact parser, retry rule, and producer hashes. No other judge
model or backend is allowed. If the existing Qwen3 artifact cannot supply immutable hashes, status is
`BLOCKED_EXTERNAL_INPUT`; an executor may not choose a substitute.

Formal generation is fixed to `do_sample=false`, `num_beams=1`, `max_new_tokens=1296`, float32, with
thinking enabled. Parse `final_completion` only as one JSON object with exactly `label` and `rationale`;
the label must be in the domain-specific four-label set and rationale must be nonempty. Regex/plain-text
fallback is forbidden. One identical parse/infrastructure retry is allowed; a second failure is terminal.

The current `scripts/judge_phase_outputs.py` is bound as rubric source at SHA256
`73c3d4fb9bfbe818370c172e9b19d075ab18b420ca4e5336d728dcf2474d2651`, but its permissive fallback
parser is not the rc2 formal parser. Formal execution must use the exact parser implemented in
`freeze_contract.py` or an implementation with the same golden outputs and hash it in `judge_freeze`.

## Retained support identity

A scheduled support identity is retained if and only if every item below is true:

```text
scheduled_identity_match
generation_completed
judge_eligible
judge_label_parsed
identity_complete
dose_denominator_valid
dose_geometry_finite
post_dtype_alpha_finite
identity_collision == false
```

A completed empty/collapsed response is judge-eligible and may be retained after a valid `broken` label.
A technical model-call failure, terminal judge-parse failure, identity mismatch/collision, invalid dose
denominator, nonfinite geometry, or nonfinite post-dtype alpha is not retained. Nothing is imputed,
replaced, rerolled, or relabeled as technical missingness based on semantic class.

## Support and downstream status map

Each anchor ledger always has 300 scheduled rows. Apply rules in this order:

| Condition | Anchor status | Downstream action |
|---|---|---|
| scheduled/unique count is not 300, any identity collision, unexpected ID, or missing scheduled ID | `NON_ESTIMABLE_IDENTITY` | do not attempt affected downstream cells; keep fixed logical IDs as `unattempted_due_integrity_block` |
| otherwise retained `>=285` and denominator/dose-geometry/post-dtype-alpha failure counts are all zero | `SUPPORTED` | execute fixed downstream identities |
| otherwise | `SUPPORT_LIMITED` | execute fixed downstream identities and prohibit supported-language |

The exact dependency map is:

| Anchor | `SUPPORTED` | `SUPPORT_LIMITED` | `NON_ESTIMABLE_IDENTITY` |
|---|---|---|---|
| A | `P2-U(A)=ESTIMATION_ONLY_SUPPORTED` | `P2-U(A)=ESTIMATION_ONLY_SUPPORT_LIMITED` | A member and both A cells are `NON_ESTIMABLE_IDENTITY` |
| T | P2-B(T) and benign-T carry supported status | P2-B(T) and benign-T carry `SUPPORT_LIMITED` | T member, both T cells, and benign-T are `NON_ESTIMABLE_IDENTITY` |
| H | report `SUPPORTED` only | report `SUPPORT_LIMITED` only | report `NON_ESTIMABLE_IDENTITY` only |

H never gates an A/T confirmation cell. A/T `SUPPORT_LIMITED` never changes `P=50`, `V=20`, endpoints,
anchors, matrix, or human `N=720`. A downstream estimator/CI failure has higher reporting precedence and
emits `NON_ESTIMABLE_ANALYSIS`, but the fixed logical identity registry is unchanged.

After all support attempts terminate, `support_execution_manifest.json` freezes the complete 900-row
ledger, exclusion reasons, per-anchor counts/status, actual calls/retries, judge labels, parent hashes,
timestamp, and self hash. Then `behavior_confirmation_freeze.json` binds the already-fixed 4,000 P2,
50 harmful-clean, 600 benign-steered, and 30 benign-clean identities before any formal confirmation
output is visible.

## Exact rc1 merge points

The main rc2 editor should apply these semantic replacements, not copy both old and new language:

| rc1 location | rc2 replacement |
|---|---|
| lines 90-91 | move the realized `median_content_norm` frame/count/value/hash from pre-outcome Freeze A to `measurement_result_dose_manifest.json` |
| sections 2.5-2.7, lines 175-216 | replace with specification freeze, post-P1 result/dose manifest, pre-support judge freeze, post-support execution manifest, behavior-confirmation freeze, then human sample lock |
| section 3.1 `D_judge_dev` | replace `independent` with empty formal set/manual document-only review; record its cost separately from 5,580 |
| E0 table | add freeze-order, exact judge parser, retained predicate, and support-status golden fixtures |
| section 6, lines 391-399 | replace ambiguous retained/support-limited language with the executable predicate and precedence table above |
| section 11 | retain formal total 5,580; add separate judge-development ledger with zero development model calls in rc2 |
| artifact tree | add `measurement_specification_freeze.json`, `measurement_result_dose_manifest.json`, `judge_freeze.json`, `support_execution_manifest.json`, and `behavior_confirmation_freeze.json`; remove old ambiguous freeze names |
| execution sequence, lines 866-875 | use the ten-event order above |
| active registry, lines 880-890 | use `SUPPORTED`, `SUPPORT_LIMITED`, `NON_ESTIMABLE_IDENTITY`, and `NON_ESTIMABLE_ANALYSIS` exactly |

## Audit disposition and scope guard

- P0-01 is closed by separating the outcome-free specification from the outcome-bearing immutable
  result/dose manifest.
- P0-09 is closed by the retained predicate, precedence, downstream action, and golden boundary cases.
- P0-10 is closed by fixing `D_judge_dev` to manual-only/zero-call and using a separate cost ledger.
- P0-03/P0-05/P0-08 belong to the one synchronized-resampling root cause; this B contract adds no
  duplicate statistical family or audit expansion.
- This contract adds no model under behavior confirmation, endpoint, anchor, prompt, vector, human item,
  or experiment block. It does not restore K2, V2, attention, power simulation, or any deleted scope.
- `P=50`, `V=20`, and `human=720` are executable assertions in the validator.

## Verification

With project-local `TEMP`/`TMP` and `NX_DAEMON=false` set as required by the repository instructions:

```powershell
python scripts/stage3_rc2/freeze_contract.py --self-test
python scripts/stage3_rc2/freeze_contract.py
```

These commands validate only schemas, hashes, state transitions, and synthetic golden cases. They do
not run a model, support screen, generation, judge call, or human experiment.
