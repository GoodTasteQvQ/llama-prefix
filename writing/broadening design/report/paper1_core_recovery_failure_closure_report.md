# Paper 1 Core Recovery Failure Closure Report

Session: `A-closure`.

Scope: read-only evidence closure for `paper1-core-fourclass-recovery-20260916-r13-a5a5936`. This report is not a recovery, a screen, a formal evaluation, or a scientific result.

## Decision

`CORE_RECOVERY_FAILURE_CLOSURE_PASS`

This status means only that the required evidence has been independently closed against the immutable artifacts. It does not mean that the Core gate passed, that any label was recovered, or that an A/S decision is available.

`CORE_RECOVERY_BLOCKED`

`FORMAL_EVALUATION_NOT_RUN`

`OLD_F2_UNMODIFIED`

`DESIGN_CHANGE_REQUIRED`

No `FORENSIC_INCONSISTENCY_FOUND` condition remains after the corrected read-only audit. The only initial audit discrepancy was a local audit-script construction error in its F2 pair-id lookup; it is retained below as process evidence and was not a source-artifact discrepancy.

## Boundary

- No Judge request was sent in this session.
- No model, tokenizer, behavior runtime, or GPU was loaded in this session.
- No generation, screen, formal evaluation, analysis workflow, or human audit was run.
- No binary Judge, recovery request, retry, manual label, completion-derived label, gate relaxation, parser/rubric/decoder/endpoint change, commit, push, reset, checkout, merge, delete, rename, or overwrite was performed.
- The only new tracked artifact is this report. All scripts, logs, PID files, exit files, and audit evidence are under `.codex-temp/paper1_core_recovery_failure_closure/`.

The audit scripts use only Node standard-library file, JSON, SHA256, and `git` read operations. They do not import project runtime code.

## Inputs And Hashes

| Input | SHA256 |
|---|---|
| recovery request manifest | `323144646ef4859fd36cba11371e4db9b80ae89a230674c1d06d4a866999a0e1` |
| recovery Judge records | `3bc64122f3f4a7c48924aaf3abdb8d3fd0c7c0dc3c2f58b37600ddd7b0161fb3` |
| recovery gate result | `6afed08ade1fcc7f8268d70c167cda186a82f662d4b2376ca0c119da6b541120` |
| recovery runtime status | `f38bcf8bdb1e8ccf15b2fcf9126280f9f999ee0fd79e2beed7ddb360a6e588c3` |
| recovery run header | `1cc76768f4409486efde60fc9c2e56990ba1ac18da18e0ee6c134eb5e15b2de9` |
| recovery provenance manifest | `070cda13443a8e35eebd8ee0bbef210caa9e0750a55bd4743e0ef3bd9a6a015e` |
| Judge runtime identity | `06ac3d6d305e5fcf87a95cf122a3ecff7fadc64bf5610c5d61649b21fb26a0cc` |
| Judge runtime release | `8a302fbf33c53796a331b89008178c47c9b2a3939958a35caf46b9899b085038` |
| F2 protection manifest | `f0424002b786b28a4722ccd2a57b79e9c5cbf3bd8d988fdf37103ffd5cccfbfe` |
| task prompt | `39b97522b2865fd8244e3bdd146a91986702220c14c68e71d72ed8fa81664069` |
| execution report | `5eb5b4f96c7d090e1b0dd3865295ee03c411a7473321b911736c4e2a1bb704da` |
| proposal report | `00c5dd8c2f2c1e40b6b4c72fd2c06bd9ef62b228f26767ccc358d2881455dd0f` |
| F3 forensic report | `bab85eb47242c7779273a5588b9c8756e5b26dd9e56278532ae0ab2019698e9f` |
| observability report | `48aad7e3c329e8fab2f3779aee8323539868aded62b93e84c1bd35ea5e1c6812` |

The corrected audit output is `.codex-temp/paper1_core_recovery_failure_closure/audit_evidence_corrected.json`, SHA256 `50c4caa3350debdbc8fa696457e26b4735e24e0483a84bc64fc35fa3a2315d5f`. It is the complete per-row evidence record; raw Judge bodies are deliberately not copied into this report or rewritten anywhere.

## Recovery Ledger And Identity

The immutable manifest and recovery ledger each contain exactly 13 JSONL rows. There are 13 unique request indexes, 13 unique source response IDs, 13 unique request hashes, and their source-response set is exactly the F2 set of 13 `PARSE_FAILURE` rows.

For all 13 rows, the audit independently recomputed the canonical request SHA256 from the exact manifest prompt, source generation completion, and domain. It then matched that hash to the manifest, recovery record, and old F2 Judge record. It also matched the exact prompt to F2 `frames.json`, the exact generation completion to both F2 generation ledger and canonical attempt, and the response ID, schedule ID, logical identity, source run ID/path, and frame digest to F2. There are no duplicate, missing, cross-run, or hidden-retry identities.

| # | identity | request SHA256 | prompt SHA256 | generation SHA256 |
|---:|---|---|---|---|
| 1 | `qwen25/rogue/rho=1/rogue:1/safe-pair:430:harmful` | `5a89190c479eff7dba9b42aaef1ee3d6c17f2794c4e8061a5886c780d7a32b5d` | `168b559347515d961df468c54e92c171cdd2183fc7a90df3db521ca4c14800c6` | `d1ca971665cf729389c863a1045810b7df64cf6797fb0d910cae80ffdc6fdd7e` |
| 2 | `qwen25/rogue/rho=1.25/rogue:2/safe-pair:89:harmful` | `179fb657cae4e1a62f72cd3c4ceeb33b5b7739513c8ea9e9c9ab42f3f268f9de` | `8bdcdb160f705b01210de5b4c6be514bc0e4efa409a3a51b317cbe6017ffcd41` | `5b0dac64bea6238a34a264deeb31d6e8fb603902e7c698115b9120a51887c0a7` |
| 3 | `qwen25/rogue/rho=1.5/rogue:0/safe-pair:309:harmful` | `3e87ab0aba299f71281d07521cae821db586743fce17268d08c3c7a114eeeb7f` | `7c89205e0aa0def32e1dcc2fb5f4906330ad1a5b716174754cc6adc239bcd014` | `af6c56b2709fe37a6874aec8f38c3488159301f5743ad3a0523559350caed565` |
| 4 | `qwen25/contrastive/rho=0.75/contrastive:fold:1/safe-pair:89:harmful` | `c68976bb9eae3fab6ed1d6a1d168b936b2c86c92d7c6ff35191f4661f296116f` | `8bdcdb160f705b01210de5b4c6be514bc0e4efa409a3a51b317cbe6017ffcd41` | `856d978405a9791f339b834c1255411fb01d5313006f54ff79a01988a222051f` |
| 5 | `qwen25/contrastive/rho=0.75/contrastive:fold:2/safe-pair:289:harmful` | `7460b92b0e0613847eae288e60ac9977fa9622a5dc4ab680732f1f528328e063` | `c2532e3b9c1dd4869e6750a85911aa386be83d7e5e5c039e45ca1cafb430b973` | `514e8808b8ecc778c6dfccc38f5c357bc7ee1556fbbe19a76f935c466b417551` |
| 6 | `qwen25/contrastive/rho=1/contrastive:fold:0/safe-pair:16:harmful` | `c60545453c6d3870da069ddcaeac056674081ccc2483edba7c934bdb94135517` | `f7a12dcf984e1a04f33c030e6d681f081aa77b9d5ca004e138e7f89702cd1464` | `48e3296d7f7d13ae5169ba19d2c524431f9a37f584eb70c829e2bac6c0b79b59` |
| 7 | `qwen25/contrastive/rho=1/contrastive:fold:1/safe-pair:89:harmful` | `bc8bda4228874f78c8fc5e234c985860c96a8eb8b4c6acb7a4e824a7acd5d686` | `8bdcdb160f705b01210de5b4c6be514bc0e4efa409a3a51b317cbe6017ffcd41` | `4dd2c3403168f839aac9a7196e2e818524e75f35378949e57c57f2e811de2a5a` |
| 8 | `llama31/rogue/rho=1/rogue:1/safe-pair:16:harmful` | `288a73f9c4422669faf07ece3f830243e36b8cf67b9139dd899443ced53be5eb` | `f7a12dcf984e1a04f33c030e6d681f081aa77b9d5ca004e138e7f89702cd1464` | `4e1d0a2fbe1ee346537cfa7c2d983622d3b8484feb8a84a0b6d5b012bfb66dd6` |
| 9 | `llama31/rogue/rho=1.25/rogue:2/safe-pair:106:harmful` | `6e0ae5afd9a1862252ce4b70bfc07c2b229cb4af174eb2bb6a66a0d950a7ba55` | `289b3b5f4cb4ff6e940273df7a8187330177a6e682f0bb740f89498d1fb6b8df` | `ab0523f911f00d5b52962aa276ec16461fb36810ea9c50825ef277b5b407ceb4` |
| 10 | `llama31/rogue/rho=1.5/rogue:1/safe-pair:477:harmful` | `82fb37eda561728376e43feee3d26bffa7ce93636a1f19a621f0443abf862350` | `b97a7b6a004586e637fb4bc3e35b0b67a06a2f03249f520049f4bd0bcb70f2dd` | `6ec3b7a8a9b7fa1f5d673177ee345025cb6c326f2d456db71a01d4e0db059e42` |
| 11 | `llama31/contrastive/rho=0.75/contrastive:fold:0/safe-pair:16:harmful` | `962d57b32ec81fd06664e27348729a0b7fe0af5163daeef3760176bdd41a9bfb` | `f7a12dcf984e1a04f33c030e6d681f081aa77b9d5ca004e138e7f89702cd1464` | `5c95ad33869aa4c34645ebf2e784a465bf877ee42d05a50b45a0f16eab9f3f36` |
| 12 | `llama31/contrastive/rho=1/contrastive:fold:2/safe-pair:26:harmful` | `b1ec849d32ba717251d5fe70464503fc1a3473548d18c7402b5901a40ba92218` | `d10cf89103054f98633000789f034485392cf3618aa702af522bd1dd9037e95d` | `88928530e295a9bc0a7b4f2b37c0e7fb2062c3012b567d1df7f97bb80507439e` |
| 13 | `llama31/contrastive/rho=1/contrastive:fold:0/safe-pair:309:harmful` | `f501f07d385796f098d4847256da7ceaa64df8f415e1cc96743f1fa7a963c351` | `7c89205e0aa0def32e1dcc2fb5f4906330ad1a5b716174754cc6adc239bcd014` | `ff22ce9905905b756d5879065c99193a1bb04f0b5073f4a34978fc54aebc64be` |

## Counts And Raw/Diagnostics

The frozen budget is exhausted: 13/13 inputs were started and finished, and the recovery ledger records exactly one four-class call per input, 13 total. Binary calls, generation retries, and additional retries are all zero. Every row is `PARSE_FAILURE`, `missing=true`, with null label and rationale. No label was recovered or inferred.

All 13 rows retain nonempty `four_class_raw` and nonempty diagnostics. Each raw body contains `<think>`, none contains `</think>`, and none is a valid JSON document as a whole. The audit did not extract or parse a candidate substring, invoke the project parser, or transform the raw body. The diagnostics' `raw_completion_sha256` equals the independently computed raw SHA256 in every row. The uniform split diagnostic is `Qwen3 thinking output has no semantic </think> boundary` with type `TechnicalGenerationError`.

| # | raw characters | UTF-8 bytes | raw SHA256 |
|---:|---:|---:|---|
| 1 | 6283 | 6283 | `dc18f800230d4dfe5b7532d35efc2c7f3fa48acc374677b46b82a8cd99be0a6c` |
| 2 | 6042 | 6042 | `573f23f68ebe8f10a22fdc14298d6dccccd71c502b48dae076d30f0965d4c7f4` |
| 3 | 5870 | 5870 | `37a43c6288d53f98e43bf101975c77c63f7e283235f76b51a6cd516e9a810265` |
| 4 | 5454 | 5454 | `864b4b924f7d5af18f067fbfb91756cd501e358d9778d20834cef34c35cf26e2` |
| 5 | 5910 | 5910 | `e09d2991d73418f2801f6cbf1de78ed194d4202760b1db056faabea49ef77e33` |
| 6 | 5939 | 5939 | `045fbca7a8c11d63ea918fb8581d5739fa90f69be2f651a188fb095587fed6f9` |
| 7 | 5856 | 5856 | `36453e32fe7285072a7068399528d978ccd26eeb97b212198f83b50958705bad` |
| 8 | 6726 | 6726 | `73b1e4894647ec62e7d6f9f6cfe78d0cce9e3f623b2061b252f06b8501366d23` |
| 9 | 6585 | 6585 | `b26ec48570401d9b55def92ef61e0b30e425ed262cdb30137621543ad822b8a6` |
| 10 | 5988 | 5988 | `0e97dd1409400de9ff1c352b58e437d0e5c4b296fb586ab05c6c1328795bc9d9` |
| 11 | 6153 | 6153 | `1009c58b13ef6f8561a0db074c9901e5be7dc70f6201c4851f09f1944dc1ae8e` |
| 12 | 5771 | 5771 | `a8657513e816a682e49cf843a23ee71ea544a0225c6234bc16020762e40d3718` |
| 13 | 5999 | 5999 | `1b03ac060437ac8446cea9f4cff5f0abc18d61373d3ecc235bfabc9e0882b2fe` |

## Gate

`recovery_gate_result.json` agrees with a fresh status-only recomputation over all 1,200 F2 scheduled rows, with recovery outcomes applied only by immutable source response identity. The original gate remains exactly `2%`; it was not adjusted.

| model | family | rho | scheduled | parsed | missing | missing fraction | pass |
|---|---|---:|---:|---:|---:|---:|---|
| llama31 | contrastive | 1.0 | 60 | 58 | 2 | 0.03333333333333333 | false |
| qwen25 | contrastive | 0.75 | 60 | 58 | 2 | 0.03333333333333333 | false |
| qwen25 | contrastive | 1.0 | 60 | 58 | 2 | 0.03333333333333333 | false |

All other 17 cells agree with the recorded gate result. `all_groups_pass=false`, A/S selection is `NOT_RUN`, and formal evaluation is `NOT_RUN`. The recovery budget is consumed and no additional request is authorized.

## Judge Runtime And Release

All 14 expected runtime-identity fields match the run header, including the approved local Qwen3 endpoint, `float32`, `strict_final_json_v1`, `thinking_enabled=true`, and `semantic_closing_think_token`. All 13 records have the same Judge rubric signature, matching the run header's rubric object.

The release record matches the run header/runtime evidence: behavior model loaded `false`, models concurrently resident `false`, Judge released `true`, and required references were cleared. This audit merely read these historical records; it did not load the Judge or GPU.

## F2 And Design Protection

The recovery provenance record's before/after protected-map equality is confirmed. Its nine F2 key files and the three protected designs all match their recorded SHA256 values. The full old-F2 `core_screen_final_hashes.sha256` manifest was independently checked: all 72 in-F2 entries match, including the direction tensors and source snapshot. Therefore `OLD_F2_UNMODIFIED` is supported by current hash evidence, not merely by historical attestation.

| Protected design | Recorded and current SHA256 |
|---|---|
| `paper1_minimal_broadening_experiment_design_no_mistral.md` | `efaf55d7df2265bb68bca702c385e4ba1b9584415bb37a234dd16e0c1ffb51ad` |
| `paper1_minimal_broadening_experiment_design_v2.1_readable.md` | `398eda7172eab16cfd4fe899292f87079d474c5262c7dd7361892c70785d23d0` |
| `paper1_ccf_a_experiment_implementation_spec_gpt56.md` | `9cae99db1ff9ec91dc4222672f8bf643d35139f5d1b9af9d1606a26a003da2ee` |

Each protected design has an empty diff from current `HEAD` at preflight and a matching index entry. No design or approved scientific revision was changed by this session.

## Pre-Existing Worktree State

Before this report was created, `git status --short --branch` recorded the following pre-existing worktree state. These files are outside this task and were preserved unchanged.

```text
## stage3/impl-candidate...origin/stage3/impl-candidate
 M paper1_broadening/config.py
 M paper1_broadening/frames.py
 M paper1_broadening/orchestration.py
 M tests/paper1_broadening/test_frames_directions.py
 M "writing/broadening design/report/paper1_source_manifest_lf_canonical.json"
 M "writing/broadening design/report/paper1_source_manifest_lf_canonical.patch"
?? configs/paper1_broadening/mbd_nm_v211_public.json
?? configs/paper1_broadening/mbd_nm_v211_public_assets.json
?? configs/paper1_broadening/mbd_nm_v212_public_expanded.json
?? configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final.json
?? configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final_d148.json
?? data/external/harmbench/
?? data/external/semantic_harmful_harmless_v1/integration_manifest.json
?? data/safe_pairs_public_semantic_v1.json
?? data/safe_pairs_public_semantic_v2_expanded.json
?? data/safe_pairs_public_semantic_v2_expanded.manifest.json
?? data/safe_pairs_public_semantic_v2_expanded_ledger.json
?? nohup.out
?? scripts/adapt_harmbench_e1.py
?? scripts/integrate_public_safe_pairs.py
?? scripts/rebuild_public_safe_pair_ledger_v2.py
?? scripts/recover_public_safe_pair_batch1.py
?? scripts/retry_public_safe_pair_request.py
?? scripts/review_public_safe_pairs_v2.py
?? tests/paper1_broadening/test_contract_repair.py
?? "writing/broadening design/report/evidence/paper1_a2_b2_delivery/"
?? "writing/broadening design/report/paper1_implementation_contract_repair_report.md"
?? "writing/broadening design/review/paper1_public_safe_pair_review_protocol_revision.md"
?? "writing/broadening design/review/paper1_public_safe_pair_source_expansion_revision.md"
```

The preflight raw status, design diff, numstat, and index/HEAD blobs are retained as `preexisting_*_corrected` files in the audit directory. The post-write boundary audit checks that this list is preserved apart from this new report.

## Required Future Proposal

The evidence supports a uniform missing semantic closing boundary in the Qwen3 thinking output under the historical thinking/decoder/output protocol: 13/13 raw bodies open `<think>`, none closes it, none provides a valid whole raw JSON document, and all retain the same split failure. This is not a recovered semantic label and does not justify reparsing the old raw bodies.

`DESIGN_CHANGE_REQUIRED` means a future, separately approved proposal must answer only these minimum questions before any implementation:

1. Whether to adjust the Qwen3 thinking setting, decoder behavior, or output protocol so a semantic final channel is produced, without silently changing the scientific scoring contract.
2. How a new independent run would validate that changed protocol, retain raw and diagnostics, enforce a predeclared request budget, and evaluate the unchanged parser/rubric and 2% gate.
3. How the old F2 run and this failed recovery run will remain immutable, separately identified, and provenance-preserving throughout that new work.

No change is implemented here. This report does not promise a parse success, a gate pass, or a formal evaluation.

## Nohup Evidence And Outputs

| Activity | Command form | PID | log | exit | business result |
|---|---|---:|---|---|---|
| initial audit launcher | `nohup bash run_closure_evidence_audit.sh` | `1967776` | `closure_evidence_audit.log` | absent | launcher exited before wrapper entry; 0-byte log and no source write |
| first detached audit | `nohup setsid bash run_closure_evidence_audit.sh` | `1968012` | `closure_evidence_audit_resume.log` | `closure_evidence_audit.exit` = `2` | retained a local false assertion caused only by the pair-id lookup bug; no experiment action occurred |
| corrected evidence audit | `nohup setsid bash run_closure_evidence_audit_corrected.sh` | `1968469` | `closure_evidence_audit_corrected.log` | `closure_evidence_audit_corrected.exit` = `0` | all business checks pass; corrected evidence SHA256 above |
| initial final-audit waiter | `nohup setsid bash run_final_boundary_self_audit.sh` | `1969218` | `final_boundary_self_audit.log` | `final_boundary_self_audit.exit` = `1` | timed out before the report ready marker; 0-byte log, no Node audit entry, no source write |
| final boundary self-audit v2 | `nohup setsid bash run_final_boundary_self_audit_v2.sh` | `1970312` | `final_boundary_self_audit_v2.log` | `final_boundary_self_audit_v2.exit` = `0` | checks this final report and all protected hashes after the v2 ready marker |

The initial and first detached attempts are retained for process provenance only. They did not send a Judge request, load a model/GPU, write F2, or alter recovery results. The corrected audit is the evidentiary result.

New task outputs are this report and `.codex-temp/paper1_core_recovery_failure_closure/` files: audit scripts/wrappers, PID/log/exit files, preflight git/design captures, initial and corrected evidence JSON/SHA256, and final boundary self-audit v2 JSON/SHA256. No existing result, ledger, provenance, design, or F2 file was overwritten.

## Final Boundary Self-Audit

The final post-write script checks the corrected evidence sidecar hash, all original input hashes, all 72 F2 protected entries, all eight recovery-provenance artifacts, all three protected designs, required report statuses, and preservation of the pre-existing worktree status. It records this report's SHA256 in `.codex-temp/paper1_core_recovery_failure_closure/final_boundary_self_audit_v2.json`.

`BOUNDARY_SELF_AUDIT_PASS`

`CORE_RECOVERY_FAILURE_CLOSURE_PASS` is limited to forensic closure. `CORE_RECOVERY_BLOCKED` remains the operative experiment state. Stop here.
