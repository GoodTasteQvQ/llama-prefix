# Paper 1 E1 Consumer Finalization Report

Task: `e1-consumer-finalize-v1` (C3)
Date: 2026-09-15 (UTC)
Worktree: `/data/goodtaste_workspace/llama-prefix`

## Status

`E1_CONSUMER_PASS`

`E1_EXPERIMENT_NOT_RUN`

`FORMAL_EXPERIMENTS_NOT_RUN`

C3 only materialized final derived E1 files from the frozen C2 evidence. No model was loaded and no
prepare, directions, screen, generation, Judge, analysis, or human-packet stage was run.

## Final binding and counts

- Output: `.codex-temp/paper1_e1_consumer_final/`
- Reference digest: `d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`
- Reference snapshot: 700 records (JBB100 plus the 600 selected safe-pair role texts); benign30 is excluded.
- Review revision: `harmbench-e1-dual-codex-overlap-v1`
- Candidate rows: 200; deterministic exact exclusions: 9; near-match queue: 17; deterministic no-near-match: 174.
- Reviewer results: A and B each 17 records, each 11 `overlap` and 6 `no_material_overlap`, 0 uncertain and 0 technical failure.
- Final ledger: 180 include, 20 exclude, 0 pending.
- Fixed selection: 40 prompts across 6 native categories; consumer result `READY_FOR_RUN`.

The final selection SHA256 is `d9c2450ae65615e4d0e10f2601fa8f4c21a098561b2c1b5541ea808428ba636f`.
The C3 finalization manifest SHA256 is `7356a24e00733b19e80d6cd6baff22eca18bfd1d0910fa9aad7b1ee592adc4c2`.

## Source evidence and validation

The final materialization completed with `C3_MATERIALIZATION_PASS` in
`logs/paper1_broadening/c3-materialize-final3-20260915T133329Z-1367614-6207.log` (exit `0`).
Two earlier fail-closed attempts are retained: `c3-materialize-retry-20260915T132804Z-1366307-4542`
and `c3-materialize-final-20260915T132959Z-1366802-3672`; neither modified the final output.

The pure CPU consumer validator completed with `E1_CONSUMER_PASS` in
`logs/paper1_broadening/c3-consumer-validate-final-20260915T134216Z-1377308-11394.log` (PID
1377311, exit `0`). A preceding validator invocation failed only because its standalone script lacked
`PYTHONPATH` (`c3-consumer-validate-20260915T133649Z-1370901-24522`, exit `1`); it did not change data.

## Final file hashes

| file | SHA256 |
|---|---|
| `reference_snapshot.json` | `41eb9125644d8e8c9d50191ec8970902cf57fd250fd489466aeab7b6b6982311` |
| `c3_source_binding.json` | `25462901b9914d34abb16fb7edef0328bc0aca556b70b216ad3c0ab42c5a3110` |
| `review_identity_manifest.json` | `cfb7047fc7374b547503de3b5de81aefdd34d28f6ee7b71dae92391498332de2` |
| `near_match_review_ledger.json` | `51983340a7790fa1aff504b860df83797153d6ecffad7e35421e801ffc5eee3d` |
| `e1_overlap_ledger.json` | `575e3175a9c5fba8a9e2183673351cf06fe8794b0af2696a3c5fb7a483a42d24` |
| `e1_overlap_decisions.json` | `03a1a89a9f50d14c6fc8824bf463e040af2141fd6d77e76e10ba00d26d10e4ab` |
| `harmbench40_selection.json` | `d9c2450ae65615e4d0e10f2601fa8f4c21a098561b2c1b5541ea808428ba636f` |

## Change boundary and self-review

Only the new `.codex-temp/paper1_e1_consumer_final/` derived directory and this report were added by
C3. The old C2 provisional directory, raw reviewer evidence, safe-pair source/ledger, JBB, benign
frame, canonical config, and design documents were not overwritten. The final derived files preserve
the C2 reviewer identities and verdicts and bind every consumer record to the single final digest.

Self-review: counts, digest, review revision, selection identity, native-category coverage, and the
CPU consumer output were checked against the final manifest and current loader. No scientific field
was changed; no `DESIGN_CHANGE_REQUIRED` condition was encountered.
