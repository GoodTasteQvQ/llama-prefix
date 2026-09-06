# Paper 1 Broadening Implementation Completion Report

## Final Status

- `CODE_REVIEW=PASS` (original server implementation review; see follow-up below)
- `CORE_SMOKE=PASS (NON_EVIDENCE)`
- `E1_ASSETS=NOT_RUN`
- `E2_ASSETS=NOT_RUN`
- `FORMAL_EXPERIMENTS=NOT_RUN`
- Unresolved implementation findings in the server review: none.
- Formal-run prerequisites still pending: safe-pair semantic-overlap review; E1 HarmBench source/metadata;
  E2 Gemma checkpoint; E3 core direction/layer assets.

## Scope Compliance

Implemented the MBD-NM v2.1 core plus bounded E1/E2/E3 orchestration contracts. No Mistral path, new experiment block, formal supplemental experiment, Git commit, or Git push was added or run.

Development dose screens use the fixed first 20 harmful prompts from the safe-pair development split. E1 references core dose decisions; E2 and E3 retain independent screens. Generation and Judge workers use separate process boundaries and block/screen-scoped release and recovery files.

## Review Findings And Fixes

The bounded review found and fixed the following issues:

1. Critical: screen artifact grouping used a type annotation instead of assigning the grouping key. Fixed in `paper1_broadening/pipeline.py` and covered by a regression test.
2. High: E2/E3 screens could use evaluation prompts. Fixed to use `development20` safe-pair harmful prompts only.
3. High: screen and evaluation lifecycle files could be reused across blocks. Fixed with explicit screen-scoped filenames and complete scheduled model/layer release validation before Judge load.
4. High: safetensors index presence did not verify every declared shard. Fixed in `paper1_broadening/runtime.py`.
5. High: archive terminal checks did not require runtime release evidence. Fixed with fail-closed checks for behavior/Judge releases, Judge status failures, screen process completion, and screen artifacts.
6. Medium: E1 prompt records were not resolved by the local prompt map. Fixed and covered by a regression test.

The server report states that all listed findings were retested after repair; no blocking or unresolved
implementation finding was reported there.

## Server-Reported Verification

- Specialized tests: `29 passed` (server environment).
- Full regression: `294 passed, 8 skipped, 5 warnings, 126 subtests passed`.
- Python compilation: passed (server environment).
- CLI help, offline asset discovery, hidden screen routing, `git diff --check`, shell syntax, and line-ending checks: passed.
- `prepare` offline check: passed; it reported E1 missing HarmBench/metadata, E2 missing configured Gemma, and E3 pending core direction/layer gates.
- Fixture smoke: `PASS`, `NON_EVIDENCE`.
- Fixture E2E: `NON_EVIDENCE`, archive revision 1.
- Previously authorized bounded real smoke was not rerun because its quota was already exhausted. Existing report: `.codex-temp/paper1_broadening_smoke-final/smoke_report.json`, with 24 generation calls and 4 Judge calls, `PASS`, `NON_EVIDENCE`.

No model download or formal experiment was started. The implementation completion itself did not create a Git commit or push; publishing this report is a separate user-requested GitHub action.

## Independent Follow-up Review (2026-09-06)

The follow-up found and repaired core screen status aggregation, A/S alias accounting, generation retry
handoff, Judge recovery and release/archive contracts, Gemma clean-layer release resolution, and missing
human-packet rubric text. It also updated snapshot paths for the reorganized documentation.

After installing local CPU test dependencies with user authorization, the focused suite actually ran:
`54 passed, 1 warning` (38 broadening tests and 16 shared model-contract tests). The full repository suite
did not pass locally: server-specific Stage 3 assets, paths, repository-state and numerical checks remain
environment-dependent failures. The server-reported counts above remain historical, not a reproduction
of this follow-up revision. No formal model experiment was run.

Local prepare reports JBB100=100, JBB40=40, benign30=30, 498 preliminary eligible safe pairs out of 500,
86 overlap-candidate rows, preliminary k=79, and `PENDING_SEMANTIC_REVIEW`. These are not human approvals.

See [the detailed readiness review](../review/paper1_run_readiness_review.md) for fixes, test commands,
logs, limitations and remaining gates. Use [the current nohup task](../implementation/paper1_server_codex_run_prompt_nohup.md)
after synchronization. Its immediate scope is preflight and human-review handoff; core generation is
conditional on the human and real-runtime gates, and E1/E2/E3 are not automatically launched.
