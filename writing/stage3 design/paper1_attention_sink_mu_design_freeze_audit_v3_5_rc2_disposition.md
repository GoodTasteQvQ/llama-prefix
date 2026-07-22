# v3.5-rc2 Design-Freeze Audit Disposition

- audited source finding set: `paper1_attention_sink_mu_design_freeze_audit_v3_5_rc1_summary.md`
- target: `paper1_attention_sink_mu_experiment_design_v3_5_rc2.md`
- disposition date: `2026-07-22`
- review boundary: design freeze only; no formal experiment execution

## P0 disposition

| Audit item/root | rc2 disposition | Executable evidence | Status |
|---|---|---|---|
| P0-01 pre-outcome freeze contamination | Split outcome-free measurement specification from the immutable post-P1 result/dose manifest; result-derived frame/count/value/c/alpha cannot enter the first object. | `freeze_contract.py`, freeze contract and golden lifecycle cases | CLOSED |
| P0-02 bootstrap CI ambiguity | Fix P1 nearest-rank percentile CI/lower bound, Bessel SE, 9,500/10,000 completion, degenerate/nonfinite conditions; apply one retained percentile rule to K1/clean/benign. | `reference_statistics.py`, success/failure golden fixtures | CLOSED |
| P0-03 synchronized Webb/max-statistic root, including P0-05 and P0-08 symptoms | Fix CR1 SE, six-point Webb law, two-way multiplier, fixed-scale statistic, nearest-rank critical value/endpoints, completion/failure, and SHA256 `sync_unit_id` excluding `member_id`; delete all marginal/memberwise fallback. This single row is the complete disposition for P0-03/P0-05/P0-08. | statistical reference, RNG/golden fixtures, statistical binding manifest | CLOSED |
| P0-04 infeasible retained statistical branch | Delete the branch and every associated method, draw, replicate, figure, claim, artifact, registry/checklist, and resource obligation; keep raw and matched two-phase families. | C removal matrix plus zero-residue release scan | CLOSED |
| P0-06 survivor-frame mismatch | Restrict P2-U/P2-B correction, residuals, point estimates, resamples, and agreement wording to `M_A/M_T`; reject incomplete/available-arm input. | `two_phase_correction.py` and golden success/failure cases | CLOSED |
| P0-07 non-unique fixed720 quota | Fix critical floors, 216/216/144/144 targets, capped-Hamilton priorities/ties, SHA256 ranking, capacity shortfall, and member-specific status mapping. | `human_quota.py` and four golden allocator cases | CLOSED |
| P0-09 retained/support ambiguity | Define retained as one nine-field conjunction; fix status precedence and A/T/H downstream execution/reporting mapping. | `freeze_contract.py` and retained/status golden cases | CLOSED |
| P0-10 judge-development resource path | Freeze judge before any support output; set `D_judge_dev` to empty formal/manual-only/zero-call; record time/non-call expense separately from formal 5,580. | freeze contract, event-order and parser golden cases | CLOSED |

## A0 and I0 boundary

External checkpoint/tokenizer/template, prompt frames, anchors, vectors, and realized protocol freezes are
not fabricated. Their absence remains `RUN_BLOCKED_EXTERNAL_INPUT`, not an open design choice. The
design-only reference implementations and synthetic golden fixtures exist and pass; remaining model/data
execution fixtures stay pending until real immutable inputs exist. No RUN-READY claim is made.

Previously noted symbol/claim issues are also closed: `theta_hat_j` and replicate statistics are defined,
`N_b` is replaced by used `N_benign_prompt`, Qwen aliases are defined in the result/dose manifest,
`dominates calibration` is in the allowed whitelist under its strict gate, and scheduled P/V is separated
from realized `M_A/M_T` support.

## Static acceptance record

- preexisting-file hash/length preservation: required over 28 captured files;
- scope residue: required zero in the active rc2 protocol;
- section cross-references: every numbered target must resolve;
- logical budget: `900+4000+50+600+30=5,580` generation and scheduled judge identities;
- human budget: 720 items, 1,440 primary assignments, at most 720 observed adjudications;
- contracted symbols: required definitions present and retired aliases absent;
- formal experiments executed: none.

The machine-readable release verifier is the final authority for these static checks. A failed hash,
golden, reference, budget, scope, section, or symbol check changes this disposition to a reproducible
failure and forbids the verdict below.

## Verdict

DESIGN-FREEZE-PASS
