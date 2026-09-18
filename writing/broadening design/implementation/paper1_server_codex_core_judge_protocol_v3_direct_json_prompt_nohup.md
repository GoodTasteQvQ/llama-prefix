# Core Judge protocol v3: direct JSON compatibility probe and gated rescore

Version: `core-judge-protocol-v3-direct-json`; execution session: `A-judge-v3`.

## Decision from the v2 probe

The v2 probe must be treated as a failed non-formal probe, not as a partial
screen result. On the second fixed input, Qwen3 generated exactly 4,096 tokens,
stopped at `max_new_tokens`, emitted no semantic `</think>` token, and repeated
the same refusal phrase about 470 times. The raw completion is
`results/paper1_broadening/core-judge-protocol-probe-20260917T141934Z-1a746872/raw/02-response-122c80122328a689cc58e19ec44de6344d4ed5df4cff6810030874496afb9ce4.txt`.

This is evidence of a thinking-channel repetition loop. Do not retry the same
protocol with 8,192 or a larger token limit. The next protocol removes the
unbounded thinking channel for the Judge and requires one strict JSON response.

## Scientific and historical boundaries

1. Treat the v2 probe result as `JUDGE_PROTOCOL_PROBE_FAIL` and
   `DESIGN_CHANGE_REQUIRED`. Do not relabel it as a successful Judge result.
2. Keep v2.1 designs, the v2 probe run, old F2, old recovery, old Judge ledgers,
   old dose decisions, canonical configs, directions, safe-pair data, and all
   behavior completions read-only. Do not overwrite, merge, delete, rename, or
   reinterpret them.
3. Do not change the behavior decoder, rubric wording, label domains, model,
   endpoint, tokenizer, dtype, layer, direction, rho, seed, generation retry
   semantics, or 2% missing gate in this task.
4. The direct-JSON protocol is a new Judge protocol. Its labels cannot be mixed
   with the 1,187 old parsed labels or the 13 old parse failures. A future full
   rescore must use one direct-JSON protocol for all 1,200 old behavior
   completions.
5. Do not start recovery, full rescore, formal evaluation, E1/E2/E3, analysis,
   or human review from this task. Do not commit or push.

## Phase 0: minimal implementation adaptation, no Judge request

Run this phase first. It sends no request and loads no model.

### Required implementation

Make the Judge output mode explicit in a run-specific configuration while
preserving the old default:

- Legacy default when the field is absent: `enable_thinking=true`,
  `max_new_tokens=1296`, semantic `</think>` split, and
  `strict_final_json_v1`.
- New direct mode only when explicitly configured:
  `enable_thinking=false`, `max_new_tokens=512`, and parser identifier
  `strict_direct_json_v1`.

In direct mode, pass `enable_thinking=false` to the existing Qwen3 chat
template. Parse the generated completion as a complete JSON object after
trimming surrounding whitespace. It must have exactly the existing two keys,
`label` and `rationale`; the label must be valid for the domain and the
rationale must be non-empty. Reject Markdown fences, extra prose, JSON with
extra keys, missing keys, `<think>`/`</think>` text, and malformed JSON. Do not
use regex recovery, substring extraction, completion-derived labels, manual
labels, or a fallback to the old parser.

Record the selected mode in Judge identity and diagnostics, including
`thinking_enabled=false`, `thinking_final_split=disabled_direct_final_json`,
`parser=strict_direct_json_v1`, and `max_new_tokens=512`. Keep the existing raw,
diagnostics, stop-reason, token-count, request-hash, and call-count evidence.

The implementation must remain backward compatible for callers and configs
that omit the new mode field. Do not replace the old default with direct mode.

### Offline checks

Add focused tests for:

- legacy omitted-field behavior (`true`, `1296`, semantic parser);
- explicit direct-mode propagation to chat template and `generate()`;
- strict direct JSON acceptance for a valid object;
- rejection of fences, extra text, extra keys, missing keys, empty rationale,
  and thinking markers;
- identity/diagnostics recording of the direct mode and token budget.

Use the laboratory Linux environment, one visible GPU setting, offline
Hugging Face flags, and `nohup` for every check. Save PID, log, and `.exit`
files under `.codex-temp/paper1_core_judge_protocol_v3/phase0/`. Run focused
tests, the complete `tests/paper1_broadening` suite, Python compile, and
`git diff --check`. No check may send a Judge request or load a model.

### Phase 0 stop condition

Write a report at
`writing/broadening design/report/paper1_core_judge_protocol_v3_direct_json_report.md`
with `PROPOSAL_WRITTEN`, `DIRECT_JSON_IMPLEMENTATION_OFFLINE_PASS` (or a
failure marker), `DIRECT_JSON_PROBE_NOT_RUN`, and
`FORMAL_EVALUATION_NOT_RUN`. Save a boundary self-audit that confirms the
protected historical hashes are unchanged, no direct-mode run/config was used
for a request, and no later phase started. Stop at
`READY_FOR_DIRECT_JSON_PROBE_APPROVAL`.

If implementation requires changing a scientific rule beyond the output mode,
parser, and explicit Judge budget, record `DESIGN_CHANGE_REQUIRED` and stop.

## Phase 1: six-input direct-JSON compatibility probe, approval required

Do not enter this phase until a complete
`.codex-temp/paper1_core_judge_protocol_v3/DIRECT_JSON_PROBE_APPROVAL.md` is
present and validated. The approval must bind the same six fixed old-F2 inputs
used by the failed v2 probe, including their response IDs and 64-character
request hashes. Do not select replacement rows or choose inputs based on a
probe outcome.

After approval:

1. Create a new independent run under
   `results/paper1_broadening/core-judge-protocol-v3-direct-json-probe-<UTC>-<shortid>/`.
2. Use the existing Qwen3 Judge, tokenizer, chat template, rubric, model
   endpoint, float32, greedy decoding, and one beam. The only protocol changes
   are `enable_thinking=false`, `max_new_tokens=512`, and the strict direct
   JSON parser.
3. Send exactly one four-class request for each of the six bound inputs. Use
   `binary Judge=0`, behavior generation retry `0`, and additional Judge retry
   `0`. Stop immediately after any failed row; do not send remaining rows.
4. Save the fixed-input manifest, prompt/request hashes, raw completions,
   diagnostics, strict parse result, stop reason, token counts, runtime/release
   identity, request accounting, PID/log/.exit files, and an artifact hash
   manifest.

The probe passes only if every sent row has a complete direct strict JSON object,
a legal label, a non-empty rationale, no thinking markers or unparsed text, and
complete evidence. The final accounting must show six logical identities and,
if no row fails, six requests with zero retries.

On any failed row, missing evidence, OOM, identity mismatch, or hidden retry,
write `DIRECT_JSON_PROBE_FAIL` and `DESIGN_CHANGE_REQUIRED`, issue no further
request, and stop. Do not increase the token limit and do not silently switch
back to thinking mode.

Only on 6/6 success write `DIRECT_JSON_PROBE_PASS`. A probe pass does not
authorize recovery or a full rescore.

## Conditional Phase 2: versioned design, no request

If and only if Phase 1 passes 6/6, create:

- `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.3_direct_json.md`
- `configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json`

Copy the v2.1 scientific design without changing data, model, direction, dose,
generation, endpoint, or metrics. Document only the new Judge protocol:
`enable_thinking=false`, `max_new_tokens=512`, and strict direct JSON parsing.
Mark v2.1 and the failed v2 probe as historical pilot artifacts. Never modify
the v2.1 file or an old/canonical config. Run offline syntax and contract
checks, perform a boundary self-audit, record
`DESIGN_REVISION_V2.3_WRITTEN` and `READY_FOR_RECOVERY_APPROVAL`, then stop.

Phase 2 sends no model or Judge request. Recovery requires a separate complete
approval file and a new task.

## Required final report fields

The report must distinguish the actual branch:

- `DIRECT_JSON_IMPLEMENTATION_OFFLINE_PASS` or failure;
- `DIRECT_JSON_PROBE_NOT_RUN`, `DIRECT_JSON_PROBE_PASS`, or
  `DIRECT_JSON_PROBE_FAIL`;
- `DESIGN_REVISION_V2.3_NOT_RUN` or `DESIGN_REVISION_V2.3_WRITTEN`;
- `CORE_RECOVERY_V3_NOT_RUN`, `CORE_SCREEN_V3_NOT_RUN`, and
  `FORMAL_EVALUATION_NOT_RUN` unless separately authorized in a later task;
- `JUDGE_PROTOCOL_PROBE_FAIL` and `DESIGN_CHANGE_REQUIRED` for the historical
  v2 probe;
- `OLD_F2_AND_OLD_RECOVERY_IMMUTABLE`.

List actual code/config/design hashes, approval-file hash when present, run IDs,
logical/request/retry counts, runtime identity, all PID/log/.exit evidence,
changed files, pre-existing worktree differences, and the final boundary
self-audit result. A process exit code of zero is not a scientific PASS.
