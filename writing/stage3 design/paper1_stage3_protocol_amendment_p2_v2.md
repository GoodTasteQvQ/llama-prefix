# Paper 1 Stage 3 Protocol Amendment: Independent T/H P2

Amendment ID: `paper1-stage3-p2-independent-th-v2`
Amendment date: `2026-08-22`
Status: `FIXED PROSPECTIVELY BEFORE THE NEW RUN`

This document appends a protocol amendment. It does not replace, rewrite, or
erase the original Stage 3 design or any earlier design history. The amendment
is fixed before the first run governed by it.

## 1. Relationship to the completed P2

The completed and accepted original P2 remains a separate A/T experiment at:

```text
/data/goodtaste_workspace/paper1_stage3_runs/p2-qwen25-paper-20260808T051044Z/
```

That directory, its four A/T cells, its materialized results, and its runner
and configuration are immutable inputs to the historical record. They must not
be modified, deleted, overwritten, renamed, or rerun. The original P2 results
must continue to be reported separately as the original preregistered A/T P2.

This amendment was proposed after the original P2 had been observed. It is an
independent follow-up, not a correction to or continuation of the original P2,
and it must never be represented as part of the original preregistration.
Stage 1/2 evidence and the observed original P2 results provide rationale for
this amendment only. They may not be used after the new run to select, reorder,
replace, or omit an endpoint, anchor, estimator, sample size, pairing rule, or
reporting decision.

## 2. Fixed independent experiment

The experiment reuses the existing 50-prompt `D_behavior_confirm` frame and
the 20 existing vector indices `10..29`. It creates a new canonical registry
containing exactly 4,000 new logical identities in these ordered cells:

| Cell | Anchor | Estimator | Identities |
|---|---|---|---:|
| `P2_T_all` | `T` | `mu_all_tw` | 1,000 |
| `P2_T_content` | `T` | `mu_content_tw` | 1,000 |
| `P2_H_all` | `H` | `mu_all_tw` | 1,000 |
| `P2_H_content` | `H` | `mu_content_tw` | 1,000 |

Every cell is the fixed Cartesian product of the same 50 prompts and 20
vectors. Each identity binds its split, domain, anchor, estimator, vector ID,
rendered prompt identity, code/config/environment identity, and dose evidence.
The H records must be generated and judged from the H identities. No H record
may be copied, renamed, relabeled, or otherwise derived from an H support-screen
record or an original P2 record.

The endpoint order is fixed as:

1. `P2-U(T) = unsafe(all,T) - unsafe(content,T)`
2. `P2-B(H) = broken(all,H) - broken(content,H)`

`M_T` contains only valid pairs sharing the same T prompt and vector across
`P2_T_all` and `P2_T_content`. `M_H` contains only valid pairs sharing the same
H prompt and vector across `P2_H_all` and `P2_H_content`. Records may not be
borrowed across anchors, and pairing may not use array position from the
original P2.

## 3. Execution contract

The T/H dose binding, deterministic generation configuration, judge
configuration, offline guard, and terminal missingness semantics are unchanged
from the existing Stage 3 production contract. Behavior generation completes
before the behavior backend is released; the judge is loaded only after that
release; response records, dispositions, and the ledger are then reconciled.

Generation permits at most two identical attempts per logical identity: one
first attempt and one technical retry. A deterministic generation failure is
terminal without retry. Judge parsing permits at most two identical attempts:
one first attempt and one retry for the existing retry-eligible parse or
technical failure classes. The existing first-failure precedence and terminal
missingness codes remain binding. Missing, duplicate, mismatched, borrowed, or
otherwise noncanonical identities fail closed.

The H support status from the fixed successful support run must satisfy the
existing downstream prerequisite before execution. This prerequisite does not
authorize reuse of support responses.

Every formal amended run requires a new explicit run ID and writes only to:

```text
/data/goodtaste_workspace/paper1_stage3_runs/<new-run-id>/
```

An existing output directory is an error. Formal run metadata must set
`formal_experiment_run=true` and `paper_result_eligible=false`, and must set
`old_p2_run=false`, `p1_run=false`, `support_run=false`, and `k1_run=false`.
The fixed runner configuration is
`configs/stage3/qwen25_p2_independent_th_v1.json`.

## 4. Reporting commitment and claim boundary

The new results will be reported under this amendment whether they support,
oppose, or are neutral with respect to the motivating expectation. Their
direction may not determine whether this amendment is acknowledged or whether
the run is included in the paper record. The original P2 and this amended
independent P2 must always be identified and reported separately.

Reporting under this amendment must not use significance language, p-values,
confirmation language, causal language, or general safety conclusions. The
two fixed differences are descriptive endpoint estimates for these fixed
models, prompts, vectors, anchors, doses, estimators, and execution contract.
No new P2 statistics or result materializer is authorized by this amendment.

Future changes may only be recorded by appending a new dated amendment before
the affected run. They may not overwrite this amendment or the original design
history.
