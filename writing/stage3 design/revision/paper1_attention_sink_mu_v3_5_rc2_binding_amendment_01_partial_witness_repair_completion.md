# v3.5-rc2 binding amendment 01 partial-witness repair completion

Date: `2026-07-22`  
Status: `DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`

This receipt closes only the final retained harmful-clean partial-record
verification-artifact gap identified by the directed final closure audit. It
contains synthetic verification evidence only and does not authorize formal
experiment execution or announce final design-freeze acceptance.

## 1. Modified and added files

- `scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/draft202012_subset.py` (new)
- `scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/verify_golden.py`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/partial_harmful_production_shape_input.json` (new)
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/partial_harmful_production_shape_expected.json` (new)
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap_manifest.json`
- `scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/amendment_binding_manifest.json`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/amendment_release_manifest.json`
- `writing/stage3 design/v3_5_rc2_binding_amendment_01/audit_disposition.md`
- `writing/stage3 design/revision/paper1_attention_sink_mu_v3_5_rc2_binding_amendment_01_partial_witness_repair_completion.md` (new)

The base protocol, binding-amendment specification, two-phase component,
retained production estimator and input schema, four existing retained fixed
goldens, and the final closure audit were not modified.

## 2. Pre-repair baseline

Before modification, all 25 entries in `base_rc2_hashes_initial.sha256`
matched. The three verifier exits were 0 with markers:

```text
TWO_PHASE_AMENDMENT_GOLDEN_PASS artifacts=9 prompt_success=9999 vector_success=9988 failure_cases=15
RETAINED_BOOTSTRAP_GOLDEN_PASS
AMENDMENT_STATIC_VERIFICATION_PASS
```

Relevant pre-repair identities were:

| Artifact | Bytes | SHA256 |
|---|---:|---|
| retained verifier | 13,044 | `e797ccc442847991862c4a8707c64a3c4e22ea36bb669bee8834f0ef49646554` |
| retained component manifest | 4,119 | `e685a60cd165d11ec8b9a2b4d9f32ebc145ee89fa7771ba89c951de3169a00ae` |
| aggregate verifier | 35,803 | `6de09728fe72e5f67bdbe6a1b00305a835b06de7e269d64ef5a69209b05e3bf6` |
| aggregate binding manifest | 9,572 | `00d21dd59a370109fd86f97d830d05c6233c15031d0e1b868391e48e59e574b9` |
| release manifest | 7,284 | `1f0ece91bde07ebf551eb2524b62a5c5c6826b00caf664a0cdc540cff4aa8d96` |
| audit disposition | 2,035 | `1aa75c939d6f757d5f21f9deefd8ee893915fb0277ce5f85477d0a9cc78e67f3` |

The three new witness/helper files were absent at baseline. The retained
README and bound schema remained at their recorded component identities.

## 3. Synthetic provenance and bound schema

The outer fixture records exactly:

```text
fixture_schema=v3.5-rc2-amendment-01-partial-harmful-production-shape-input-v1
synthetic_data=true
formal_data_used=false
data_origin=SYNTHETIC_GOLDEN_ONLY
purpose=production-schema partial-record execution witness
```

Its nested `production_schema_payload` uses `block_type=harmful_clean`, schema
version `v3.5-rc2-amendment-01-retained-bootstrap-input-v1`, and
`synthetic_data=false`. The outer marker is the actual provenance. The inner
false value exists only to prove that the same nested payload satisfies the
production input contract and executes through the production entry; it does
not describe formal data.

The verifier loads the unchanged bound schema file directly:

```text
path=writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap_schema.json
physical_sha256=78f0e45f4cb3ca7d455c0d19022f776b1c42fa4c08ae5b69c99129492c2ca47a
subschema_path=#/$defs/harmfulClean
draft=https://json-schema.org/draft/2020-12/schema
```

The standard-library helper resolves internal `$ref` and fail-closed validates
the reachable `type`, `const`, `enum`, `required`, `properties`,
`additionalProperties`, `minItems`, `maxItems`, `items`, `minLength`, and
`minimum` keywords. Unknown or malformed reachable schema structures are
rejected.

Schema-valid result: `PASS`. The same bound path rejected all controls:

| Control | Rejection |
|---|---|
| 49 prompts | `$.prompt_frame / minItems` |
| 51 records | `$.records / maxItems` |
| empty records | `$.records / minItems` |
| inner `synthetic_data=true` | `$.synthetic_data / const` |
| wrong type, missing required, extra property, empty ID, negative position, invalid label | corresponding `type`, `required`, `additionalProperties`, `minLength`, `minimum`, `enum` |

## 4. Production-entry execution witness

After schema validation, the verifier passes the identical nested object to:

```text
analyze_harmful_clean(payload)
fixture_mode=false
```

No alternate estimator or five-prompt truncation is used. The executed result
was:

```text
prompt_count=50
retained_count=3
point_denominator=3
point_profile.broken=0.3333333333333333
point_profile.unsafe=0.3333333333333333
point_profile.refusal=0.3333333333333333
point_profile.safe=0.0
prompt_sample_size_per_replicate=50
replicates_requested=10000
common_successes=9537
failed_replicates=463
failure_reason_family=INVALID_DENOMINATOR:zero_retained_denominator
no_reroll=true
output_canonical_sha256=6beba0e1e12471ab5ca6c90380bcae6ad3955df5514c2ef34731d193ee56013b
```

The 463 failed replicates were only zero-retained-denominator failures. The
fixed RNG, one-based seed serialization, nearest-rank interval, completion
floor, production constants, and failure precedence were unchanged. The
original five-prompt fixture-mode partial witness and every previous fixed
success/failure, RNG, multiplicity, 9,499/9,500, and zero-SD witness remain.

## 5. Expected-receipt independence

`partial_harmful_production_shape_expected.json` is a fixed, independently
maintained receipt. The verifier reads its bytes before production execution,
recomputes the actual receipt in memory, requires canonical equality, and
requires the expected bytes to remain unchanged. No reference or verifier
write path regenerates or writes back this file.

The input fixture SHA256 is
`abc9c8956c3d0fe830e89f73aa4478b2402181b1073cd4454b8db4dedd493caa`;
the expected receipt SHA256 is
`d2e71c95f34e2ce8396e6a9ed613fe754693efe1206b3b79770ca99be244a548`.

## 6. Final manifest identities

| Manifest | Bytes | Physical SHA256 | Canonical self SHA256 |
|---|---:|---|---|
| retained component | 4,942 | `0e163a0fcdcb57a1d08f3b4653fa4025750ff31c5776e8dea6507dd059431d7f` | `a2ff77593606972ca62a217c862b37a3061c3c17a0d6e949fdc1e057a54438e5` |
| aggregate binding | 10,608 | `98d63c66302e8bc05ab5af32ccb7ee64993c598698f6d1e0acfb384cae95d9b8` | `77cf7855ca8d4be5c0ac41336c3992759f8c4c523b38a5caeb8dbe20e8c19d95` |

The release binds this receipt with
`sha256_utf8_excluding_parent_release_identity_block_v1`. It hashes every
receipt byte after replacing only the two 64-hex parent identity values in the
unique block below with fixed 64-zero values. The release also binds the final
physical receipt length. The aggregate verifier rejects malformed, repeated,
unknown, or extra exclusion fields and checks both embedded parent identities
against the final release file. This narrowly excluded parent block avoids a
receipt-to-parent cryptographic cycle without excluding any repair evidence.

PARENT_RELEASE_IDENTITY_BEGIN
release_manifest_physical_sha256=6d7df765f8d7fdd8125ce50b846ee45e9d007cb2e55bb6a50fafb72d71415276
release_manifest_self_sha256=7785adb64d2ca4508c69860b019b996a0c8ef8f8cbd2cdf6aa2927c584823652
PARENT_RELEASE_IDENTITY_END

## 7. Final verifier receipt

All commands use project-local `.codex-temp` for `TEMP` and `TMP`, with
`NX_DAEMON=false` and `PYTHONDONTWRITEBYTECODE=1`.

| Verifier | Complete marker | Exit |
|---|---|---:|
| two-phase component | `TWO_PHASE_AMENDMENT_GOLDEN_PASS artifacts=9 prompt_success=9999 vector_success=9988 failure_cases=15` | 0 |
| retained component | `RETAINED_BOOTSTRAP_GOLDEN_PASS partial_schema_valid=1 partial_prompt_count=50` | 0 |
| aggregate amendment | `AMENDMENT_STATIC_VERIFICATION_PASS` | 0 |

The final aggregate receipt reports 25 unchanged base files, 27 aggregate
binding artifacts, 20 component artifacts, 31 release artifacts, 11 synthetic
fixture JSON files, one bound schema helper, two direct reference modules, and
two golden verifiers.

## 8. Scope and decision boundary

Final invariant values are:

```text
base_files_unchanged=25/25
formal_data_used=false
no_scope_expansion=true
P=50
V=20
human_response_items=720
logical_generation=5580
first_pass_scheduled_judge=5580
new_experiment_blocks=0
```

No protocol text, amendment specification, estimand, retained production
algorithm, RNG, failure precedence, interval method, formal input schema,
checkpoint, prompt sample, response, label, experiment, endpoint, status, or
claim boundary changed. No formal P1, support, generation, judge, or human
experiment was run. The combined specification remains only
`DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`.
