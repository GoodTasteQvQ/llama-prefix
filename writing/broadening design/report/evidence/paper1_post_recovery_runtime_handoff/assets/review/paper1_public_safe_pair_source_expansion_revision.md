# Paper 1 public safe-pair source expansion revision

Revision: `MBD-NM v2.1.2-public-pairs-expanded`  
Task: `public-safe-pair-gate-recovery-v3` / E4 continuation  
Date: 2026-09-15 (Asia/Shanghai)

This revision changes only the append-only public safe-pair source collection and its
provenance. It does not change the scientific design, model registry, model layers,
hook site, prompt templates, decoder settings, rho grid, seed, fold count, development
count, evaluation frames, reviewer criteria, adjudication rule, or logical generation
budget. The `20,480` value remains the formal logical generation budget; reviewer API
requests are not experiment generations.

## Baseline retained

The existing 416 source rows and A2 rebuilt review result remain unchanged and are reused
by reference. The baseline is 409 preliminary eligible rows, 221 executable rows, and
`actual_k=24`. The seven exact-overlap rows are not reviewed again, and the old 409 rows
are not re-requested.

## Candidate and selection rule

The first candidate bundle is the GitHub repository
`https://github.com/fevziegeyurtsevenler/turkish-over-refusal-set.git` at commit
`13682bf03c9e7805b81df2eab7e23fb2512e560b`. Its source file
`data/turkish_over_refusal.jsonl` has SHA256
`5e1910a1dfb129de7c68ee875143e2e810056efec895dec9b1b5cf663709f396` and is licensed
under Apache-2.0 as recorded by the repository `LICENSE` and `NOTICE.md`.

Only rows with `lang=en`, a non-empty prompt, an explicit stable `pair_id`, and exactly
one `type=safe` and one `type=harmful` row per pair are eligible for this source. The
Turkish rows are retained in the source snapshot for provenance but are never included
in this experiment.

Candidate pair order is ascending upstream numeric `pair_id`. Before any reviewer
request, every pair is checked for malformed English structure, empty text, normalized
exact duplication within the candidate batch, normalized exact overlap with all old 416
source texts, and normalized exact overlap with JBB100/JBB40/benign30 evaluation texts.
The first at most 100 pairs with no precheck exclusion are frozen as batch 1. Remaining
eligible pairs are recorded as not selected. The complete candidate order, all exclusion
reasons, selected IDs, and not-selected IDs are stored in the batch freeze JSON.

There may be at most two source bundles and at most 100 preliminary eligible pairs per
bundle. The second candidate is not enabled unless batch 1 completes both reviews for
all selected pairs and the resulting executable count is still below 250. No batch is
stopped early based on interim verdicts, and no source is added to change a verdict.

## Review and merge invariants

Every frozen pair receives two real, isolated Codex requests using
`public-semantic-pair-quality-v2` and the `public-safe-pair-quality-ledger-v2` schema.
Only unanimous `include` is executable; any `exclude` or `uncertain` yields an exclude,
and failed or invalid requests remain pending. Raw requests, event streams, identities,
input hashes, evaluation digest, timestamps, attempts, and output hashes are retained
under the E recovery directory.

After review, new rows may only be appended to a new versioned source/config/ledger.
The old source, old ledger, old raw evidence, and old run are not overwritten. A final
shared-code adaptation is allowed only after confirming the B3 `B2_DELIVERY_READY`
handoff and its stopped-write state. If any requested change would alter a scientific
field, the task stops with `DESIGN_CHANGE_REQUIRED`.

