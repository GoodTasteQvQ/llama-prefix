# Core Judge protocol v3 direct-JSON task review

Review date: 2026-09-18
Review status: `REVIEW_PASS`

## Evidence basis

The v2 probe report records that fixed input 2 used all 4,096 generated tokens,
had stop reason `max_new_tokens`, contained no semantic `</think>`, and repeated
the same refusal phrase about 470 times. The raw completion and diagnostics are
retained in the v2 probe run. The v2 boundary audit is
`PHASE1_PROBE_FAIL_BOUNDARY_AUDIT_PASS`; no later run was started and protected
historical hashes match.

## Decision review

Increasing the thinking budget to 8,192 or higher is rejected. The observed
failure is a repetition loop in the hidden reasoning channel, so a larger limit
would add cost without establishing a reliable final channel. The proposed
change removes only that channel for the Judge and makes direct JSON parsing
explicit. It preserves the old default for old callers and keeps all new labels
under a separate protocol.

## Boundary review

- Phase 0 has no model load and no request.
- Phase 1 is limited to the same six fixed inputs, at most six requests, one per
  input, and zero retries.
- A failed row stops the probe; there is no automatic token escalation,
  thinking-mode fallback, parser relaxation, or manual label.
- A pass may create only a new v2.3 design and run-specific config; recovery,
  full rescore, formal evaluation, E1/E2/E3, analysis, and human review remain
  separately gated.
- The old v2.1 design, old F2/recovery, old ledgers, canonical configs, and
  previous probe artifacts remain read-only. New direct-mode labels cannot be
  mixed with old Judge labels.
- The direct parser rejects extra text, fences, malformed JSON, invalid labels,
  empty rationale, and thinking markers. It does not use a hidden fallback.

## Overdesign review

The task adds one bounded protocol comparison and one small parser/config
adaptation. It does not add models, datasets, prompts, directions, doses,
metrics, retries, or a second benchmark. The six-row probe is sufficient to
cover the same failed/successful inputs used to diagnose the prior protocol;
full 1,200-row rescore remains conditional and is not started here.

## Conclusion

`REVIEW_PASS`. The next action is Phase 0 of the v3 task by server session
`A-judge-v3`. It must stop at `READY_FOR_DIRECT_JSON_PROBE_APPROVAL`; no direct
JSON probe approval is included in this task review.
