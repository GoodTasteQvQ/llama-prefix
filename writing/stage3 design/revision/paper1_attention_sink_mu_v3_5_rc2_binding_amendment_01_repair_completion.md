# v3.5-rc2 binding amendment 01 repair completion

Date: `2026-07-22`  
Status: `DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`

This report closes only the directed implementation and binding repairs for
`P0-STAT-01` and `P0-STAT-02`. It contains synthetic verification evidence and
no formal experiment data or result.

## 1. Modified files

- `scripts/stage3_design/v3_5_rc2_binding_amendment_01/two_phase/two_phase_reference.py`
- `scripts/stage3_design/v3_5_rc2_binding_amendment_01/two_phase/verify_two_phase_golden.py`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/two_phase/README.md`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/two_phase/fixtures/schema_negative_input.json` (new, synthetic)
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/two_phase/two_phase_binding_manifest.json`
- `scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap.py`
- `scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/verify_golden.py`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/README.md`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap_schema.json`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap_manifest.json`
- `scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/amendment_binding_manifest.json`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/amendment_release_manifest.json`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/audit_disposition.md`
- `writing/stage3 design/revision/paper1_attention_sink_mu_v3_5_rc2_binding_amendment_01_repair_completion.md` (new)

The base protocol, rc1-to-rc2 semantic diff, archived closure audit, all 25
base snapshot files, and all fixed success/failure expected files were not
modified.

## 2. Root-cause closure

### P0-STAT-01

Before repair, the valid success fixture failed before CI execution with
`SCHEMA_INVALID:$.members:items`. The schema walker did not execute
`prefixItems`, interpreted `items:false` as an invalid schema, and therefore
could not validate the two ordered member positions.

After repair, each present array position is validated against its matching
`prefixItems[index]`. The referenced `memberA` and `memberT` schemas execute
their `allOf` branches; `$ref`, `minItems`, `maxItems`, `uniqueItems`, ordinary
`items` schemas, and semantic/cross-frame validation remain active.
`items:false` now rejects only an additional position. Direct synthetic
witnesses observed:

- third member: `SCHEMA_VALIDATION / $.members:maxItems`;
- reversed members: `SCHEMA_VALIDATION / $.members[0].member_id:const`;
- wrong member type: `SCHEMA_VALIDATION / $.members[0]:type`.

The unchanged fixed success output compared canonically equal. Prompt common
successes were `9,999`; vector-aware common successes were `9,988`. The
unchanged fixed failure output also compared canonically equal, including the
`9,499/9,500`, census, shared-stream, RNG-byte, multiplicity, clipping,
support, failure-precedence, and fallback-prohibition witnesses.

### P0-STAT-02

Before repair, `evaluate_success_fixture` omitted the four fixed
`canonical_output_sha256` fields and returned fields outside the fixed
projection. The invalid-denominator mutation called the formal entry point
with empty records and correctly hit formal schema/coverage validation before
the denominator helper. The harmful-clean reference also contradicted the
documented missingness contract by requiring one retained row for every frozen
prompt.

After repair, the fixed success projection is exact and each digest is computed
from the full analyzer output produced in the same run:

| Analyzer output | Canonical SHA256 |
|---|---|
| K1 | `67cdb361b2c0782cacbcbfaebe44291af1a04330578359b4b4b896cee23e4f1e` |
| harmful clean | `d355f23ea9c37e8a8ead29129f0d24f8b3df4dacf26f78a05c8d445f7413148f` |
| benign broken | `8f14e7ef96dad68ca9ea14ce89b9567ab9625aa914bb6ab236589b8df1adc129` |
| zero SD | `b58797fc89c56e001696a652d1431e79e905393da1ca123bdeb3d99b42b91558` |

The verifier independently recomputed all four digests from full analyzer
outputs and matched them. The invalid-denominator witness now calls
`_profile_point([], HARMFUL_LABELS)` as an internal synthetic unit test and
returns exactly `INVALID_DENOMINATOR / profile denominator is zero`; empty
formal records remain schema-invalid with `records minItems=1`.

A schema-shaped synthetic harmful-clean case retained 3 ordered rows from a
5-prompt frozen frame. Its point denominator was 3, with class points
`1/3,1/3,1/3,0`; every replicate still drew 5 prompts from the full frame.
The run produced `9,880` common successes and `120` zero-denominator failures,
with no reroll. Reordering the retained subset failed with
`FRAME_ORDER_INVALID`. This demonstrates the frozen missing-prompt semantics
without changing the formal `P=50` frame or production schema.

## 3. Golden independence and parameters

The implementation did not regenerate any fixed expected output. Their
physical identities remained:

- two-phase success expected: `efcc9972c59f88d10f1373cd4a18213bbc8d701d1d90e0c4cd3ae91e847f9821`;
- two-phase failure expected: `0304e69f2b67b17dee5db2959d9037b070876f6bf47b522d962db4431a617cf6`;
- retained success expected: `d9eae2cd0c5782bbbd4727a4e08953ef2f2b8797a36499f5e9748b8cd9725940`;
- retained failure expected: `e795e84ff2d14a08363f9bddfd713a4055b9a9ea6cce0cdf1ba285ccc2eeb1e9`.

Fixture-mode inputs did not change production defaults. Two-phase remains
`9,999` replicates with `9,500` required common successes. Retained blocks
remain `10,000` replicates with `9,500` required common successes.

## 4. Verification evidence

After component identities, aggregate identity, release identity, and the
post-gate audit disposition were bound, the pre-report-lock verification run
returned:

```text
TWO_PHASE_AMENDMENT_GOLDEN_PASS artifacts=9 prompt_success=9999 vector_success=9988 failure_cases=15
exit_code=0
RETAINED_BOOTSTRAP_GOLDEN_PASS
exit_code=0
AMENDMENT_STATIC_VERIFICATION_PASS
exit_code=0
```

The aggregate report in that run recorded `base_files_unchanged=25`,
`binding_artifacts=24`, `component_artifacts=17`, `release_artifacts=26`,
`synthetic_fixture_files=9`, `formal_data_used=false`, and
`no_scope_expansion=true`. A final identical three-verifier run is required
after this report is added to the release inventory; its result is the final
external verification receipt for this report-bound release.

## 5. Immutable base and scope

The 25 entries in `base_rc2_hashes_initial.sha256` were recomputed before
implementation work, at source lock, and at the disposition gate. Every pass
matched `25/25`; base hash changes were zero.

The following invariants remain exact:

```text
formal_data_used=false
no_scope_expansion=true
P=50
V=20
human_response_items=720
logical_generation=5580
first_pass_scheduled_judge=5580
new_experiment_blocks=0
```

All prohibited restoration flags remain false:

```text
model_based_rd_ci=false
power_simulation=false
coverage_simulation=false
prompt_vector_selector=false
K2=false
V2=false
attention_block=false
rendering_2x2=false
stochastic_decoding=false
phase_confirmation=false
p_value_or_global_test=false
```

No formal P1, support, generation, judge, or human experiment was run. No real
experiment labels or results entered a fixture.

## 6. Final source and binding identities

| Artifact | Bytes | Physical SHA256 | Canonical self SHA256 |
|---|---:|---|---|
| amendment specification | 16,084 | `b76bd7e35d2d26ecc04172243e0218f8f44d092549aa21af344e5bf802799c14` | n/a |
| two-phase reference | 61,277 | `de740ce4a63218eddf189b55ced9f7bd4c554d615c770da8c3c02a117e2faec3` | n/a |
| two-phase verifier | 15,415 | `4baa4c3c1d6a4f179ccb066c02a031a0b61d77409ceeebf8cf873a9806c1ee5f` | n/a |
| retained reference | 46,975 | `90ea4091c1799926efc166b1e69d54c0b9b37fdc3c35af47146109f590d46dc6` | n/a |
| retained verifier | 13,044 | `e797ccc442847991862c4a8707c64a3c4e22ea36bb669bee8834f0ef49646554` | n/a |
| aggregate verifier | 35,803 | `6de09728fe72e5f67bdbe6a1b00305a835b06de7e269d64ef5a69209b05e3bf6` | n/a |
| two-phase component manifest | 5,600 | `4bbca707cd23cfa8c7d9b1b01869e268925b2fb13309bd631dcce36e69d88248` | `e1a18122029fac7faf176ac20fa11b59585f1c492a636f6c6fa23cfc31234fa2` |
| retained component manifest | 4,119 | `e685a60cd165d11ec8b9a2b4d9f32ebc145ee89fa7771ba89c951de3169a00ae` | `b62dd2c144406179a9af7ea6596a9dcec00e248a534c602979af3a9dbb95e1bc` |
| aggregate binding manifest | 9,572 | `00d21dd59a370109fd86f97d830d05c6233c15031d0e1b868391e48e59e574b9` | `1a317da159b2dfc9ff97c422ce40ff2587c0a00f2de9ba6897f9e3114286af1e` |

The release manifest is the parent that binds this report by physical SHA256
and length. Embedding that parent's final physical or self hash in this child
would create a cryptographic cycle, so its final identity is deliberately
recorded only in the final verifier/handoff receipt after report binding.

## 7. Decision boundary

The amendment remains `DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`. This repair does
not announce final design-freeze acceptance. The only permitted next step is
one independent, read-only, targeted closure audit of these two repaired roots.
