# v3.5-rc2 binding amendment 01 partial-witness final closure audit

Audit date: `2026-07-22`  
Audit mode: read-only, single-issue, terminal closure audit  
Combined specification: `v3.5-rc2 + binding-amendment-01`  
Formal experiment execution: none  

## 1. Executive verdict

`DESIGN-FREEZE-PASS / RUN-BLOCKED`

The only remaining closure item under `P0-STAT-02`, namely the absence of a
bound-schema-valid 50-prompt partial harmful-clean synthetic witness, is now
closed. All 24 directed checklist items pass, all three required verifiers
exit `0`, and no direct regression caused by the partial-witness patch was
found.

- `P0-STAT-01` remains `CLOSED / PASS`.
- The sole remaining closure item for `P0-STAT-02` is `CLOSED / PASS`.
- `v3.5-rc2 + binding-amendment-01` is the only frozen baseline.
- A0/I0 continue to impose `RUN-BLOCKED`; they do not negate design freeze.

This audit did not reopen statistical design, historical versions, or paper
enhancement questions. No formal data, model run, generation, judge, or human
experiment was used. Apart from this required report, no file was modified.

## 2. Audit method

Three internal subagents performed the required read-only split:

- A: bound Draft 2020-12 schema path and production-entry execution;
- B: fixed-receipt independence, verifier coverage, and manifest/release binding;
- C: base immutability, scope, resources, provenance, and direct regression.

The main auditor independently read the decisive schema, fixture, receipt,
reference, verifier, manifests, base snapshot, amendment specification, and
scope/resource records. The main auditor then independently reran all three
required commands from `D:\llama_prefix` with `.codex-temp` assigned to
`TEMP`/`TMP`, `NX_DAEMON=false`, and `PYTHONDONTWRITEBYTECODE=1`.

## 3. Verifier receipts

| Verifier | Complete marker | Exit |
|---|---|---:|
| two-phase | `TWO_PHASE_AMENDMENT_GOLDEN_PASS artifacts=9 prompt_success=9999 vector_success=9988 failure_cases=15` | 0 |
| retained | `RETAINED_BOOTSTRAP_GOLDEN_PASS partial_schema_valid=1 partial_prompt_count=50` | 0 |
| aggregate | `AMENDMENT_STATIC_VERIFICATION_PASS` | 0 |

The aggregate JSON receipt additionally reported:

```text
base_files_unchanged=25
binding_artifacts=27
component_artifacts=20
release_artifacts=31
bound_schema_helpers=1
direct_reference_modules=2
golden_verifiers=2
synthetic_fixture_files=11
scope_files_scanned=20
formal_data_used=false
no_scope_expansion=true
logical_generation=5580
first_pass_scheduled_judge=5580
human_items=720
```

The aggregate verifier itself launches both component verifiers and requires
exit `0` plus their current exact markers; see
`scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py:458-493`.

## 4. Directed closure checklist

| # | Status | Decisive file/line and execution evidence |
|---:|---|---|
| 1 | PASS | The outer fixture sets `synthetic_data=true`, `formal_data_used=false`, and `data_origin=SYNTHETIC_GOLDEN_ONLY`: `writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/partial_harmful_production_shape_input.json:2-6`. The verifier enforces the exact provenance at `retained_bootstrap/verify_golden.py:292-310`. |
| 2 | PASS | The inner object contains only the schema header, 50 clearly synthetic prompt IDs, and three clearly synthetic retained-row IDs: input fixture lines `7-66`. The verifier enforces both ID prefixes at `verify_golden.py:312-324`; no prompt text, response, result, or formal label/result object is present. |
| 3 | PASS | Inner `synthetic_data=false` is explicitly the production-schema execution-mode field, not provenance: repair completion `paper1_attention_sink_mu_v3_5_rc2_binding_amendment_01_partial_witness_repair_completion.md:65-70`; retained README lines `23-28`. |
| 4 | PASS | The verifier binds `SCHEMA_PATH` directly to the current `retained_bootstrap_schema.json` and loads it at runtime: `verify_golden.py:20-32,326-328`. |
| 5 | PASS | The exact pointer is fixed as `#/$defs/harmfulClean` at `verify_golden.py:30` and used at lines `153-177`; the bound document declares Draft 2020-12 at `retained_bootstrap_schema.json:2`. |
| 6 | PASS | The helper validates reachable internal `$ref`, `type`, `const`, `enum`, `required`, `properties`, `additionalProperties`, array bounds/items, string bounds, and numeric `minimum`: `draft202012_subset.py:16-33,63-146,149-218`. The reachable bound structures are at `retained_bootstrap_schema.json:19-27,37,83-107`. |
| 7 | PASS | Unknown and malformed reachable schema structures fail closed in `draft202012_subset.py:89-146`; the verifier injects and rejects an unknown keyword and malformed `required` at `verify_golden.py:231-247`. Both live controls passed. |
| 8 | PASS | The identical nested payload passes the current bound subschema at `verify_golden.py:167-177,312-328`. Live retained marker reports `partial_schema_valid=1`; bound schema SHA256 is `78f0e45f4cb3ca7d455c0d19022f776b1c42fa4c08ae5b69c99129492c2ca47a`. |
| 9 | PASS | The payload has canonical positions `0..49` and three canonically ordered retained rows: input fixture lines `11-67`. Schema bounds are 50 prompts and 1..50 records at `retained_bootstrap_schema.json:93-107`; semantic canonical-order enforcement is at `retained_bootstrap.py:553-587`. |
| 10 | PASS | The same schema path rejects 49 prompts, 51 records, empty records, and inner `synthetic_data=true` with `minItems`, `maxItems`, `minItems`, and `const`, respectively: `verify_golden.py:153-164,181-229`. Six additional type/required/property/string/numeric/enum controls also pass, for 10 rejected instance controls total. |
| 11 | PASS | After schema validation, the exact object is passed to `reference.analyze_harmful_clean(payload)` without `fixture_mode=True`: `verify_golden.py:326-340`. The production default is `fixture_mode=False`: `retained_bootstrap.py:547-555`. |
| 12 | PASS | The production receipt reports draw size 50, denominator 3, and points `{broken:1/3, unsafe:1/3, refusal:1/3, safe:0}`: `verify_golden.py:339-351`; fixed receipt `partial_harmful_production_shape_expected.json:17-31`. Live execution reproduced all values. |
| 13 | PASS | Production constants remain 10,000/9,500 at `retained_bootstrap.py:21-26`; RNG and rejection rules at lines `120-218`; nearest-rank CI at `221-230`; completion/CI at `303-350`; zero-denominator replicate failure continues without reroll at `599-612`. Live witness produced 9,537 successes and 463 zero-denominator failures. |
| 14 | PASS | Actual and fixed expected receipts are canonically equal: `verify_golden.py:35-42,376-377`. The current expected receipt fixes schema, production call, output, and digest at `partial_harmful_production_shape_expected.json:7-34`. |
| 15 | PASS | Expected bytes are read before production execution and checked unchanged afterward: `verify_golden.py:330-340,378-380`. Its SHA256 remained `d2e71c95f34e2ce8396e6a9ed613fe754693efe1206b3b79770ca99be244a548` before retained execution, after retained execution, and after aggregate execution; no tested source contains a write-back path. |
| 16 | PASS | Retained verification is behavioral, not an existence/keyword check: positive bound validation, 10 negative controls, two schema-definition fail-closed controls, production execution, constant/output assertions, and receipt equality are at `verify_golden.py:153-249,292-382`; main calls this path before emitting PASS at lines `531-539`. |
| 17 | PASS | Helper, updated verifier, new input, and new expected receipt are all in the retained component manifest at `retained_bootstrap_manifest.json:52-61`. The verifier requires the exact artifact set and checks every physical hash at `verify_golden.py:62-102`. |
| 18 | PASS | Aggregate binding entries include the new chain at `amendment_binding_manifest.json:75-86`; release entries include it at `amendment_release_manifest.json:56-75`. Canonical self-hash and exact inventory/hash/length validation are at `verify_amendment.py:167-170,251-307,332-406`. Live aggregate counts were `27/20/31`. |
| 19 | PASS | Aggregate independently re-executes bound validation, key negative controls, production entry, and receipt comparison at `verify_amendment.py:556-642`, then invokes the updated retained verifier at lines `458-493`. Missing/path/hash/length or marker mismatch raises and exits `1`: lines `251-306,476-479,878-886`. |
| 20 | PASS | Original two-phase success/failure canonical equality remains enforced at `verify_amendment.py:517-538`; retained fixed success/failure equality at `541-553`; retained and two-phase count/statistic/RNG invariants at `644-780`. Current two-phase and retained markers both passed with exit `0`; no fixed golden or statistical result regressed. |
| 21 | PASS | The base snapshot contains 25 entries and independently recomputed `25 matched / 0 missing / 0 mismatch`. Aggregate fail-closed base validation is at `verify_amendment.py:173-196,357-365`. Snapshot physical SHA256 is `62cdc07760c709799a2a1cce17177df1fabe838a3f0d5054d853bd6d839a722d`. |
| 22 | PASS | Component, binding, release, and verifier contract retain `formal_data_used=false` and `no_scope_expansion=true`: component manifest lines `6-7`, binding lines `7-8`, release lines `7-8`, contract lines `20-21`. Aggregate returned the same values and verifies all fixture provenance at `verify_amendment.py:783-790`. |
| 23 | PASS | Release fixes `P=50`, `V=20`, human `720`, and generation/judge `5,580/5,580`: `amendment_release_manifest.json:9-24`. Base values remain at `paper1_attention_sink_mu_experiment_design_v3_5_rc2.md:43,866-876,914`; aggregate reparses and checks the budget at `verify_amendment.py:824-857`. |
| 24 | PASS | The amendment expressly adds no model, prompt/vector/anchor, endpoint, response cell, human item, formal output, claim, p-value, or test: amendment specification lines `276-302`. Release fixes `new_experiment_blocks=0` at line `13`; aggregate scans 20 scope files and rejects active K2/V2/model-based/stochastic/restored-scope registrations at `verify_amendment.py:793-820`. |

Result: `24/24 PASS`.

## 5. Witness and receipt identity

| Artifact | Bytes | Physical SHA256 |
|---|---:|---|
| partial input | 4,647 | `abc9c8956c3d0fe830e89f73aa4478b2402181b1073cd4454b8db4dedd493caa` |
| fixed expected receipt | 1,194 | `d2e71c95f34e2ce8396e6a9ed613fe754693efe1206b3b79770ca99be244a548` |
| retained component manifest | 4,942 | `0e163a0fcdcb57a1d08f3b4653fa4025750ff31c5776e8dea6507dd059431d7f` |
| aggregate binding manifest | 10,608 | `98d63c66302e8bc05ab5af32ccb7ee64993c598698f6d1e0acfb384cae95d9b8` |
| release manifest | 8,270 | `6d7df765f8d7fdd8125ce50b846ee45e9d007cb2e55bb6a50fafb72d71415276` |

Canonical self hashes:

```text
retained component  a2ff77593606972ca62a217c862b37a3061c3c17a0d6e949fdc1e057a54438e5
aggregate binding   77cf7855ca8d4be5c0ac41336c3992759f8c4c523b38a5caeb8dbe20e8c19d95
release manifest    7785adb64d2ca4508c69860b019b996a0c8ef8f8cbd2cdf6aa2927c584823652
```

The executed production witness was:

```text
bound_schema_path=#/$defs/harmfulClean
prompt_count=50
retained_count=3
draw_size=50
point_denominator=3
point_profile={broken:1/3, unsafe:1/3, refusal:1/3, safe:0}
replicates_requested=10000
replicates_required=9500
replicates_successful=9537
replicates_failed=463
failure_reason_family=INVALID_DENOMINATOR:zero_retained_denominator
no_reroll=true
output_canonical_sha256=6beba0e1e12471ab5ca6c90380bcae6ad3955df5514c2ef34731d193ee56013b
```

## 6. Base, scope, and resource disposition

| Boundary | Frozen value | Result |
|---|---:|---|
| base snapshot | 25/25 unchanged | PASS |
| formal data | not used | PASS |
| scope expansion | none | PASS |
| P / V | 50 / 20 | PASS |
| human response items | 720 | PASS |
| logical generation | 5,580 | PASS |
| first-pass scheduled judge | 5,580 | PASS |
| new experiment blocks | 0 | PASS |
| new model/sample/endpoint/test/claim | none | PASS |

No patch-induced regression was found in the original two-phase marker, fixed
retained goldens, bootstrap/RNG/CI rules, statistical outputs, base artifacts,
scope, provenance, or resource accounting.

## 7. Final disposition and only action

`P0-STAT-01` remains closed. The only remaining `P0-STAT-02` closure item is
closed by the bound-schema-valid 50-prompt partial harmful-clean synthetic
witness, its fixed independent receipt, and the current passing component and
aggregate verification chain.

The combined specification `v3.5-rc2 + binding-amendment-01` is therefore the
only frozen baseline. Stop all protocol and amendment version iteration
immediately. Subsequent work is limited to E0, real identity/runtime manifests,
and implementation-fidelity audit. A0/I0 remain `RUN-BLOCKED` only and must not
be used to reverse the design-freeze verdict.
