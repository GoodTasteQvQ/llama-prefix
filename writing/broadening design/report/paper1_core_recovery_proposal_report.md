# Paper 1 Core Recovery Proposal Report

Task: restricted Core recovery proposal for the 13 F2 four-class Judge parse failures.
Date: 2026-09-16 (Asia/Shanghai).
Status: proposal only; no recovery request was sent.

## Decision and boundary

`CORE_RECOVERY_PROPOSAL_READY`

`OLD_F2_UNMODIFIED`

`NO_NEW_JUDGE_REQUESTS`

`CORE_DOSE_SCREEN_REMAINS_BLOCKED_PENDING_APPROVAL`

`FORMAL_EVALUATION_NOT_RUN`

This report plans, but does not execute, at most 13 new four-class Judge requests. It
does not repair, relabel, or reinterpret an F2 record. The 13 F2 records remain
`PARSE_FAILURE`/missing with no inferred label. The F2 error is the persisted
`Qwen3 Judge completion has no valid semantic final channel`; F3 established that
the old raw Judge body and diagnostics were not retained on this exception path.

The requested implementation prompt
`writing/broadening design/implementation/paper1_server_codex_core_recovery_proposal_prompt_nohup.md`
was not present in the working tree when checked with `rg --files`. The user-provided
constraints and the existing F3/F4/dose/index/design evidence were therefore applied
directly. This is an execution-environment fact, not a scientific-rule change.

No model, layer, direction, rho, seed, template, rubric, decoder, budget, endpoint,
retry rule, missing rule, or 2% gate was changed or proposed to change.

## Read-only evidence basis

F3 was read from
`writing/broadening design/report/paper1_core_screen_parse_forensic_report.md`.
It reports 13/13 joined identities, 13/13 request-hash matches, 13/13
`PARSE_FAILURE`, two four-class calls per target, zero binary calls, and no available
old Judge raw/diagnostics. F4 was read from
`writing/broadening design/report/paper1_judge_observability_patch_report.md`.
F4 is a future-observability patch only; it explicitly leaves the F2 result blocked.
The dose report was read from
`writing/broadening design/report/paper1_core_dose_screen_report.md` and reports
1,200 logical generations, 1,213 actual four-class calls including the permitted
old retries, and `CORE_DOSE_SCREEN_BLOCKED` because affected cells exceed the
original missing gate.

The current task indices read were:

- `writing/broadening design/implementation/paper1_server_codex_post_audit_task_index.md`
- `writing/broadening design/implementation/paper1_server_codex_parallel_next_tasks_index.md`

The three protected experiment/design files were read in full:

- `writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md`
- `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.1_readable.md`
- `writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md`

The F2 run is
`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`
with run id `paper1-20260915T140735Z-99331d4603`. Only the existing 13 generation
completion records, their prompt/frame identity information, and their request hashes
were used to define the proposal. No model or Judge was loaded.

## The 13 immutable inputs

`frame_digest` for the frozen F2 `frames.json` is
`9af610e6a29094bbc55991561a23500d640f08fddb471ccfbffe88e1f54d3631`.
`prompt_sha256` is the F3-canonical prompt hash. `generation_sha256` is the SHA256 of
the original generation completion. `request_sha256` is the F3-recomputed Judge
request hash. `response_id` and `schedule_id` are retained only as immutable
identity references; they do not authorize a write to the old run.

| # | logical identity (`run/block/model/layer/family/condition/rho/direction/prompt`) | response_id | schedule_id | prompt_sha256 | generation_sha256 | request_sha256 |
|---:|---|---|---|---|---|---|
| 1 | `paper1-20260915T140735Z-99331d4603/core_development/qwen25/L9/rogue/decode_only/1.00/rogue:1/safe-pair:430:harmful` | `response-ca3528d9552b3203b3a0d34564f9f92ff6125a1a1ae534f1ea7e79f1a619135a` | `schedule-25447da619b60047bd115fc234674afb2ca8b99cfd37d24d8c6e280f95c5b3f8` | `168b559347515d961df468c54e92c171cdd2183fc7a90df3db521ca4c14800c6` | `d1ca971665cf729389c863a1045810b7df64cf6797fb0d910cae80ffdc6fdd7e` | `5a89190c479eff7dba9b42aaef1ee3d6c17f2794c4e8061a5886c780d7a32b5d` |
| 2 | `paper1-20260915T140735Z-99331d4603/core_development/qwen25/L9/rogue/decode_only/1.25/rogue:2/safe-pair:89:harmful` | `response-466172752be78af0fc6f57317eb03b2c40fc2c692b683f6342eef4e22b19a5ae` | `schedule-bdeb4c187c6b8e9fefdc09b4bc025f1099422d308769f8536de54dabcb88b601` | `8bdcdb160f705b01210de5b4c6be514bc0e4efa409a3a51b317cbe6017ffcd41` | `5b0dac64bea6238a34a264deeb31d6e8fb603902e7c698115b9120a51887c0a7` | `179fb657cae4e1a62f72cd3c4ceeb33b5b7739513c8ea9e9c9ab42f3f268f9de` |
| 3 | `paper1-20260915T140735Z-99331d4603/core_development/qwen25/L9/rogue/decode_only/1.50/rogue:0/safe-pair:309:harmful` | `response-97203479e093fdace1ce0a2efbdbafe0d57d7432f1ec9b0c276b0b20e0879240` | `schedule-053ef83920c10ec117f168d1d60c407eb1e678dffd18a106a69f404ae7ba5489` | `7c89205e0aa0def32e1dcc2fb5f4906330ad1a5b716174754cc6adc239bcd014` | `af6c56b2709fe37a6874aec8f38c3488159301f5743ad3a0523559350caed565` | `3e87ab0aba299f71281d07521cae821db586743fce17268d08c3c7a114eeeb7f` |
| 4 | `paper1-20260915T140735Z-99331d4603/core_development/qwen25/L9/contrastive/decode_only/0.75/contrastive:fold:1/safe-pair:89:harmful` | `response-122c80122328a689cc58e19ec44de6344d4ed5df4cff6810030874496afb9ce4` | `schedule-d8f70591b68da7ce9d6a0b5487abac45d19ab950ae7dda54a12d8dd8bf49d673` | `8bdcdb160f705b01210de5b4c6be514bc0e4efa409a3a51b317cbe6017ffcd41` | `856d978405a9791f339b834c1255411fb01d5313006f54ff79a01988a222051f` | `c68976bb9eae3fab6ed1d6a1d168b936b2c86c92d7c6ff35191f4661f296116f` |
| 5 | `paper1-20260915T140735Z-99331d4603/core_development/qwen25/L9/contrastive/decode_only/0.75/contrastive:fold:2/safe-pair:289:harmful` | `response-8a30ae027e3f3fb2aa0d1b7f0002cd5b4ec5c6b77952e5f2f032f98d6fe3b03b` | `schedule-0675de9b906dcc115420e184dcd762187eb9c099132a36b051b8f2384b5fa2d0` | `c2532e3b9c1dd4869e6750a85911aa386be83d7e5e5c039e45ca1cafb430b973` | `514e8808b8ecc778c6dfccc38f5c357bc7ee1556fbbe19a76f935c466b417551` | `7460b92b0e0613847eae288e60ac9977fa9622a5dc4ab680732f1f528328e063` |
| 6 | `paper1-20260915T140735Z-99331d4603/core_development/qwen25/L9/contrastive/decode_only/1.00/contrastive:fold:0/safe-pair:16:harmful` | `response-3bdfb6f0c2866e1eb755cbbb2b3b51e6bf2dfd48e5d41b69b78215d3d447ca4c` | `schedule-226f97eba3b13b300c8405ed70d9517b0ae8d10de8edcca80da88dd3c5c7d922` | `f7a12dcf984e1a04f33c030e6d681f081aa77b9d5ca004e138e7f89702cd1464` | `48e3296d7f7d13ae5169ba19d2c524431f9a37f584eb70c829e2bac6c0b79b59` | `c60545453c6d3870da069ddcaeac056674081ccc2483edba7c934bdb94135517` |
| 7 | `paper1-20260915T140735Z-99331d4603/core_development/qwen25/L9/contrastive/decode_only/1.00/contrastive:fold:1/safe-pair:89:harmful` | `response-c1e47316fff1a57fd088eedab73c5312b62ff07528c32e336c48ad3fe9218002` | `schedule-e4b288e2b37650d6b3bc1305b1dd1fa1863912703dc4e5b0840b62576fed4307` | `8bdcdb160f705b01210de5b4c6be514bc0e4efa409a3a51b317cbe6017ffcd41` | `4dd2c3403168f839aac9a7196e2e818524e75f35378949e57c57f2e811de2a5a` | `bc8bda4228874f78c8fc5e234c985860c96a8eb8b4c6acb7a4e824a7acd5d686` |
| 8 | `paper1-20260915T140735Z-99331d4603/core_development/llama31/L11/rogue/decode_only/1.00/rogue:1/safe-pair:16:harmful` | `response-f3b11764228fa8a73701fd88de1cc8024a7bbc3e9a1c045eb7f5faf509142951` | `schedule-c7694119b9ec91edc570715e2d0cd9cc20357443a3b5e3481b993f284813f6d6` | `f7a12dcf984e1a04f33c030e6d681f081aa77b9d5ca004e138e7f89702cd1464` | `4e1d0a2fbe1ee346537cfa7c2d983622d3b8484feb8a84a0b6d5b012bfb66dd6` | `288a73f9c4422669faf07ece3f830243e36b8cf67b9139dd899443ced53be5eb` |
| 9 | `paper1-20260915T140735Z-99331d4603/core_development/llama31/L11/rogue/decode_only/1.25/rogue:2/safe-pair:106:harmful` | `response-31b8577ce6d8bed4d0a1d724a9844132edcfe2759010255b878d53ce5176bbb2` | `schedule-dbd8de611a7340c2c1b760e42121693f88d0b568649b166d0c6fd5f01192e44c` | `289b3b5f4cb4ff6e940273df7a8187330177a6e682f0bb740f89498d1fb6b8df` | `ab0523f911f00d5b52962aa276ec16461fb36810ea9c50825ef277b5b407ceb4` | `6e0ae5afd9a1862252ce4b70bfc07c2b229cb4af174eb2bb6a66a0d950a7ba55` |
| 10 | `paper1-20260915T140735Z-99331d4603/core_development/llama31/L11/rogue/decode_only/1.50/rogue:1/safe-pair:477:harmful` | `response-beb99035cc1676dbad3cd86636022ad2ed141c9c047caf8f34d29db613040a7e` | `schedule-07326b9f3ccad772b335d63770ac5eaf819f891687a19c204015d8695c8a0f02` | `b97a7b6a004586e637fb4bc3e35b0b67a06a2f03249f520049f4bd0bcb70f2dd` | `6ec3b7a8a9b7fa1f5d673177ee345025cb6c326f2d456db71a01d4e0db059e42` | `82fb37eda561728376e43feee3d26bffa7ce93636a1f19a621f0443abf862350` |
| 11 | `paper1-20260915T140735Z-99331d4603/core_development/llama31/L11/contrastive/decode_only/0.75/contrastive:fold:0/safe-pair:16:harmful` | `response-e619594cb7d8a1560356e24113321bc38d2b7f0b1cbdcc91771a5b57644f5d11` | `schedule-c13c45fd1227314b00ea6b37263274ce652ac35fc030ebb9abccb1a958b247cd` | `f7a12dcf984e1a04f33c030e6d681f081aa77b9d5ca004e138e7f89702cd1464` | `5c95ad33869aa4c34645ebf2e784a465bf877ee42d05a50b45a0f16eab9f3f36` | `962d57b32ec81fd06664e27348729a0b7fe0af5163daeef3760176bdd41a9bfb` |
| 12 | `paper1-20260915T140735Z-99331d4603/core_development/llama31/L11/contrastive/decode_only/1.00/contrastive:fold:2/safe-pair:26:harmful` | `response-a790919720fb4c57eb7930924e0ec173ff1cf03c9aa7a3616c9bb5967e5c7c64` | `schedule-f230f816fdb9edbbb6b625f21be5b6e7a077a60dd7a6ebbb14d683b1cc4dc9f2` | `d10cf89103054f98633000789f034485392cf3618aa702af522bd1dd9037e95d` | `88928530e295a9bc0a7b4f2b37c0e7fb2062c3012b567d1df7f97bb80507439e` | `b1ec849d32ba717251d5fe70464503fc1a3473548d18c7402b5901a40ba92218` |
| 13 | `paper1-20260915T140735Z-99331d4603/core_development/llama31/L11/contrastive/decode_only/1.00/contrastive:fold:0/safe-pair:309:harmful` | `response-808c4135523f241ab87f535fdf2334c56dfd7670cf3c3281b1fbdce1b0a6226d` | `schedule-f5bf53a1c490cf991b7b6ec243b30be8e2919968736a25759726039ba0990950` | `7c89205e0aa0def32e1dcc2fb5f4906330ad1a5b716174754cc6adc239bcd014` | `ff22ce9905905b756d5879065c99193a1bb04f0b5073f4a34978fc54aebc64be` | `f501f07d385796f098d4847256da7ceaa64df8f415e1cc96743f1fa7a963c351` |

The table is an identity manifest, not a replacement ledger. The old Judge raw hash,
Judge final hash, and Judge thinking hash are `null` for all 13 because F2 did not
persist those bodies. No raw body was reconstructed from a generation completion.

## Restricted recovery design (not executed)

### Request budget

- Maximum new requests: **13 four-class Judge requests total**, one request for each
  table row and no more than one request per row.
- Generation budget: **0**. Existing completion text is the only response input.
- Binary Judge budget: **0**.
- Generation retry budget: **0**.
- Additional Judge retry budget: **0** beyond the 13 one-per-row requests.
- No request is sent in this session. Approval is a prerequisite to even creating a
  runnable recovery job.

The future request must use the existing F2 prompt/frame identity and exact original
generation completion identified by the hashes above, with the already approved
four-class harmful rubric/parser and the F4 observability behavior. It must not use a
different prompt rendering, completion, direction, dose, model, layer, template,
decoder, seed, or endpoint. The request hash is a preflight identity check, not a
permission to edit the old request.

### Independent run and ledger isolation

If and only if approved, the operator must allocate a new run id, for example
`paper1-core-fourclass-recovery-<UTC>-<nonce>`, and a new directory under
`results/paper1_broadening/`. The exact path and run id must be written before any
request. The new run must contain its own immutable request manifest, recovery Judge
records, runtime/status record, and final hash manifest, for example:

- `recovery_request_manifest.jsonl`
- `recovery_judge_records.jsonl`
- `recovery_runtime_status.json`
- `recovery_provenance_manifest.json`

The new ledger must carry `source_run_id`, `source_response_id`, the logical identity,
the original generation SHA256, prompt SHA256, frame digest, request SHA256, actual
call count, four-class status/label/rationale/raw/diagnostics, and an explicit
`recovery_run_id`. It must never append to, rewrite, rename, or replace any F2 file.
There is no physical merge of the old F2 ledger and the recovery ledger. A later,
separately approved readiness consumer may reference the two immutable sources by
identity, but must preserve both provenance chains and must not mutate either source.

The old run and all of its following files remain read-only: generation schedule,
generation attempts, generation ledger/completions, Judge records, `dose_decisions`,
directions, frames/source snapshot, run header, configuration, release/runtime
records, and logs. The new run cannot claim ownership of the old run id.

### Success gate

For a request to succeed, the new record must contain a valid four-class parsed label
under the unchanged strict parser/rubric, with the raw completion and available
diagnostics retained by the F4 observability path. The record is `PARSED` only when
the parser actually accepts it; no semantic label may be inferred from the generation
completion, error text, length, or another group.

Success does not change the old F2 row and does not immediately establish A/S. After
all approved requests finish, a separately authorized gate check may use the immutable
F2 schedule plus the independent recovery records to determine whether each original
60-row model/family/rho cell has at most one missing row (missing fraction `<= 2%`).
The old F2 `dose_decisions.json` remains blocked and unchanged during that check.

Only if **all original model/family groups and their candidate cells satisfy the
original 2% missing gate** may a later task enter A/S selection and evaluation
readiness. That later task must save new readiness/A/S evidence; it may not rewrite
F2 or treat this proposal as an A/S decision.

### Failure gate

Any future request failure, timeout, unavailable raw body, or parser rejection must be
written to the new ledger as `PARSE_FAILURE` and `missing`. It must retain the error,
actual call count, and any available raw/diagnostics; unavailable data remains null or
empty. It must not receive a hand-written label, a label copied from another group,
or a label inferred from the generation completion. No automatic second request is
allowed under this proposal.

The affected cell remains missing for gate accounting. If any original model/family
group remains above 2% missing, A/S and evaluation readiness remain blocked for that
group; no candidate may be skipped and no threshold may be relaxed. If all groups do
not pass, the proposal terminates with a blocked recovery record and no evaluation.

The old F2 missingness is never erased. A successful new record is evidence in the
independent recovery run only; a failed new record is an additional explicit failure
in that run. Neither outcome changes the historical F2 status.

## Explicitly disallowed operations

The following operations are outside this proposal and must not occur:

- sending any Judge request before responsible-person approval;
- writing to or merging into the old F2 run, generation ledger, Judge records,
  `dose_decisions`, directions, frames, source snapshot, run header, or old logs;
- regenerating any response, adding generation retries, loading a behavior model,
  loading a Judge, using GPU, running screen/generation/evaluation, or running the
  binary Judge;
- changing model, layer, direction/family, rho, seed, template, rubric, parser,
  semantic split, decoder, endpoint, retry budget, logical generation budget, or
  missing gate;
- creating more than 13 new four-class requests, sending a request for any input not
  in the table, or retrying a failed recovery request;
- hand-labeling, interpolating, copying labels/A/S from another group, treating
  generation completion text as a Judge label, or treating a parse failure as
  `safe`, `refusal`, `broken`, or `unsafe`;
- selecting A/S, declaring `CORE_DOSE_SCREEN_READY`, starting formal evaluation, or
  presenting recovery as a scientific result before every original group passes the
  unchanged 2% gate;
- modifying the three protected experiment designs or using this proposal as an
  unapproved design revision;
- commit, push, reset, checkout, or replacement of unrelated user changes.

If any requested next step would require a scientific-rule change, a relaxed 2% gate,
more than 13 requests, generation reruns, or modification of old F2, the correct
status is `DESIGN_CHANGE_REQUIRED` and execution must stop.

## Required approval

Before any future request, the Paper 1 experiment负责人/PI (the responsible scientific
owner) must provide written approval that names the new recovery run id/path, confirms
the maximum of 13 one-per-row four-class requests, confirms the unchanged rubric and
2% gate, and confirms that old F2 artifacts remain immutable. The server/run owner
must then record that approval in the new run header. No verbal assumption, existing
F4 patch, or report status substitutes for this approval.

## Evidence that protected files were not modified

The pre-edit status and target diff were recorded before this report was created in:

- `.codex-temp/recovery_status_pre_edit.log`
- `.codex-temp/recovery_target_pre_edit.diff`
- `.codex-temp/recovery_protected_before.sha256`

At pre-edit, the target report was absent and therefore had no existing diff. The
worktree already contained unrelated user modifications; none was reset or reverted.
The pre-edit SHA256 values were:

| protected file | SHA256 before proposal |
|---|---|
| F2 generation schedule | `c049f9537ad9dcbc386b84b5c4cc55410893e839429614f24217741131538783` |
| F2 generation attempts | `63ae8bde3830cdd9786575879be4e8324905330cd75739d6da03e5a154417165` |
| F2 generation ledger | `2d792e8466bdf17177d67b71df54e352ca03646da776b7f382593a8c46850a40` |
| F2 Judge records | `970814efcef62515e2530ef535ec0b31fe81400fbad462cae9e8904a63ad4878` |
| F2 `dose_decisions.json` | `f68221eb4eb0b8200df2ef0d3671ab1a6c2549012e16598bf2aec38ab5a7a132` |
| F2 `frames.json` | `a69a39c1f63f0fc1a9d32876e7e6663ef5bea89233917cf86972e598e0b730ef` |
| F2 `directions.json` | `3ca9bb9eed166eefddb62552e603dcf183708e37f6f892923782ec6d46d962eb` |
| F2 `resolved_config.json` | `e857f02d60d5db00fdc3747b284f9cfcb4fc68c3bc388f54bf7ada728eb2ae42` |
| F2 source-snapshot `judge.py` | `2c83f47bb6684014dd7cca56cd9f0c3023597f67c2774bcf9b44aa42009111f5` |
| design: no_mistral | `efaf55d7df2265bb68bca702c385e4ba1b9584415bb37a234dd16e0c1ffb51ad` |
| design: v2.1 readable | `398eda7172eab16cfd4fe899292f87079d474c5262c7dd7361892c70785d23d0` |
| implementation specification | `9cae99db1ff9ec91dc4222672f8bf643d35139f5d1b9af9d1606a26a003da2ee` |

This report is the only intended new tracked artifact for this task. No F2 file,
source snapshot, direction, dose decision, generation completion, or design file was
written. Post-write hash verification and a final boundary self-audit are recorded
in the task-local `.codex-temp` evidence; no commit or push was made.

## Final boundary self-audit

- Proposal only: no Judge request, generation, model load, GPU use, screen, or formal
  evaluation occurred.
- Exactly 13 existing input identities are listed; no additional input was created.
- The maximum future request count is 13; the proposal cannot authorize retries or
  binary calls.
- Old F2 remains `CORE_DOSE_SCREEN_BLOCKED`; all 13 old failures remain missing and
  unlabeled.
- Any future failure remains `PARSE_FAILURE`/missing; no manual or inferred label is
  permitted.
- A/S and evaluation readiness are conditioned on every original group satisfying the
  unchanged 2% missing gate.
- Protected F2/design hashes were checked before and after report creation; existing
  unrelated worktree changes were preserved.

`CORE_RECOVERY_PROPOSAL_READY`
`OLD_F2_UNMODIFIED`
`NO_NEW_JUDGE_REQUESTS`
`CORE_DOSE_SCREEN_REMAINS_BLOCKED_PENDING_APPROVAL`
`FORMAL_EVALUATION_NOT_RUN`
