# Paper 1 F4 Judge Observability Patch Report

Task: `judge-observability-patch-v1`
Session: `F4`
Date: 2026-09-16 (Asia/Shanghai)

## Result

`F4_IMPLEMENTATION_PATCH_PASS`

`F2_CORE_DOSE_SCREEN_REMAINS_BLOCKED`

`FORMAL_EVALUATION_NOT_RUN`

The patch is limited to future Judge evidence retention. It does not reinterpret or repair any
existing F2 record.

## Actual F4 changes

- `paper1_broadening/judge.py`
  - Carries the decoded completion and partial diagnostics through semantic split failures.
  - Carries the generated raw completion through strict four-class/binary parse failures.
  - Adds explicit observability statuses, including `RAW_AND_DIAGNOSTICS_AVAILABLE` and
    `RAW_UNAVAILABLE`; no raw text is fabricated when generation has not produced one.
  - Persists four-class and binary observability evidence fields while retaining
    `paper1-broadening-judge-record-v1` and all existing semantic fields.
  - Leaves labels, strict parser acceptance, semantic split rule, rubric text, decoder settings,
    retry control, missingness rules, request identity and call-count accounting unchanged.
- `tests/paper1_broadening/test_judge_observability.py`
  - Offline fixtures for split failure, strict parse failure, pre-raw failure, and binary success.
- `writing/broadening design/report/paper1_judge_observability_patch_report.md`
  - This report.

No parser/rubric/semantic-split/decoder/retry/scientific field was changed. No F2 retry or new
Judge request was made.

## Required behavior checks

1. A semantic split failure after decoding returns `PARSE_FAILURE`, retains the full raw
   completion and split diagnostics, and reports `actual_call_count=1`.
2. A strict final JSON failure retains the generated raw completion and available diagnostics,
   with no label or rationale.
3. A failure before raw generation returns `PARSE_FAILURE`, `raw=null`, `diagnostics={}`, and
   `RAW_UNAVAILABLE`; it does not invent a completion.
4. Existing four-class, binary, and retry-related broadening tests remain green.

## Offline commands and evidence

All commands used the project-local offline environment requested by F4:
`TMPDIR/TMP/TEMP=$PWD/.codex-temp`, `NX_DAEMON=false`, all three HF offline flags,
`PYTHONUNBUFFERED=1`, and the project pycache prefix. No model, network, GPU, prepare, screen,
generation, Judge, or formal evaluation was run.

Successful nohup evidence is under `.codex-temp/paper1_f4_judge_observability/`:

| Check | PID | Log | Exit | Result |
|---|---:|---|---|---|
| focused pytest: observability + Judge/runtime/ledger tests | `1685550` | `f4-final3-focused-pytest-20260916T123333Z-1685546.log` | `f4-final3-focused-pytest-20260916T123333Z-1685546.exit` = `0` | `15 passed` |
| full `tests/paper1_broadening` | `1685552` | `f4-final3-all-pytest-20260916T123333Z-1685546.log` | `f4-final3-all-pytest-20260916T123333Z-1685546.exit` = `0` | `57 passed` |
| Python compileall (`paper1_broadening`, `tests/paper1_broadening`) | `1685554` | `f4-final3-compile-20260916T123333Z-1685546.log` | `f4-final3-compile-20260916T123333Z-1685546.exit` = `0` | pass |
| `git diff --check` | `1685557` | `f4-final3-diff-check-20260916T123333Z-1685546.log` | `f4-final3-diff-check-20260916T123333Z-1685546.exit` = `0` | pass |

The first plain nohup focused-test submission (`PID 1675254`) was interrupted before execution
and has an empty log with no `.exit`; it was not counted as a test result. The retained setsid
rerun passed (`PID 1675525`, `14 passed`). An invalid placeholder diff command
(`PID 1676509`, exit `1`) was also not counted; the correct diff check is the passing entry above
(`PID 1677019` was the earlier passing rerun).

## Protected inputs and boundary audit

The pre-edit Git state and empty pre-edit `paper1_broadening/judge.py` diff were captured in:

- `.codex-temp/paper1_f4_judge_observability/pre_edit_git_status.txt`
- `.codex-temp/paper1_f4_judge_observability/pre_edit_judge.diff`

The worktree was already dirty with unrelated user/session changes. Those changes were preserved.
The F4 changes are confined to the two files listed above plus this report. A later status also
showed unrelated concurrent changes in `paper1_broadening/pipeline.py` and
`tests/paper1_broadening/test_e2r_release_serialization.py`; F4 did not edit or revert them.

The following F2 originals were read-only and their post-check hashes match the frozen F2 report;
the full hash output is retained in `.codex-temp/paper1_f4_judge_observability/protected_f2_hashes_after.sha256`:

- `screen_generation_schedule_core.jsonl`
- `screen_generation_attempts_core.jsonl`
- `screen_generation_ledger_core.jsonl`
- `screen_judge_records_core.jsonl`
- `dose_decisions.json`

The F2 source snapshot, runtime/release files, F2 ledger and Judge records, dose decisions, E1/C3
files, canonical config and existing run artifacts were not modified. F2 remains blocked because
its original 13 parse failures and missingness gate were not changed.

The three original design/specification files were read-only and unchanged. Their post-check
hashes are retained in `.codex-temp/paper1_f4_judge_observability/protected_design_hashes_after.sha256`:

- `writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md`
- `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.1_readable.md`
- `writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md`

No new run is required for this evidence-only implementation patch. No commit or push was made.
