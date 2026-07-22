# Binding amendment 01 audit disposition

Status: `DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`

This table disposes only the two `TRUE_P0` roots in the archived v3.5-rc2
closure audit. A passing row means the amendment's synthetic executable binding
verified; it does not announce final design-freeze acceptance.

| Audit root | Executable implementation | Normative specification | Synthetic fixtures | Binding | Verification result |
|---|---|---|---|---|---|
| `P0-STAT-01` | `scripts/stage3_design/v3_5_rc2_binding_amendment_01/two_phase/two_phase_reference.py` | amendment section 4; `two_phase/README.md`; `two_phase/two_phase_input.schema.json` | `two_phase/fixtures/success_input.json`, `success_expected.json`, `failure_input.json`, `failure_expected.json`, `schema_negative_input.json` | `two_phase/two_phase_binding_manifest.json`; aggregate binding/release manifests | `PASS`: fixed success/failure equality, Draft 2020-12 tuple-schema witnesses, component verifier, and aggregate verifier passed with exit code 0 |
| `P0-STAT-02` | `scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap.py` | amendment section 5; `retained_bootstrap/README.md`; `retained_bootstrap/retained_bootstrap_schema.json` | existing fixed success/failure goldens plus `partial_harmful_production_shape_input.json` and its fixed expected receipt | `retained_bootstrap/retained_bootstrap_manifest.json`; aggregate binding/release manifests | `PASS`: fixed goldens remain equal; the bound `#/$defs/harmfulClean` path accepted the 50-prompt/3-record synthetic payload, rejected the schema-negative controls, and the production entry executed without fixture mode; component and aggregate verifiers returned 0 |

## Directed partial-witness receipt

The added witness has outer `synthetic_data=true`, `formal_data_used=false`,
and `data_origin=SYNTHETIC_GOLDEN_ONLY`. Its nested production-schema payload
has `synthetic_data=false` only because that exact payload is validated against
the bound production subschema and passed to `analyze_harmful_clean(payload)`.
It is not formal experiment data.

The production entry used the full 50-prompt frame, 3 retained records, point
denominator 3, and draw size 50. The point profile was `broken=unsafe=refusal=1/3`
and `safe=0`. Of 10,000 fixed replicates, 9,537 were common-successful and 463
failed only because the retained denominator was zero; none was rerolled. The
fixed expected receipt matched canonical output SHA256
`6beba0e1e12471ab5ca6c90380bcae6ad3955df5514c2ef34731d193ee56013b`.
The same bound-schema helper rejected 49 prompts, 51 records, empty records,
and inner `synthetic_data=true`, together with six additional keyword controls.

## Non-P0 disposition

The archived audit's A0 items remain execution prerequisites and remain
`RUN-BLOCKED`. I0 items remain implementation-readiness work outside this
amendment. P1/P2 observations remain publication or fidelity risks and are not
promoted into design changes. No new issue, output, interval, claim, sample,
endpoint, or execution block is registered here.
