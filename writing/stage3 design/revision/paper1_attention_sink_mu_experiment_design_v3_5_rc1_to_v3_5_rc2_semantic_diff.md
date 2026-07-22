# v3.5-rc1 -> v3.5-rc2 Semantic Diff

- source: `paper1_attention_sink_mu_experiment_design_v3_5_rc1.md`
- target: `paper1_attention_sink_mu_experiment_design_v3_5_rc2.md`
- change kind: design closure without scope expansion
- source SHA256: `f557fb8a06329f92778e9e1eb7ddb2822b05e80bf83784ba1ec243b9343fb85a`
- date: `2026-07-22`

This revision creates a new protocol and does not overwrite rc1 or an older design/audit file. It fixes
only choices already implied by rc1, removes one infeasible retained statistical branch, and binds the
remaining choices to executable standard-library references, synthetic golden fixtures, and SHA256
manifests. No formal P1, support, generation, judge, or human experiment was run.

## 1. Invariants

| Field | rc1 | rc2 |
|---|---|---|
| behavior-confirmation model | Qwen only | unchanged |
| P2 support | `P=50,V=20` | unchanged |
| human response items | 720 | unchanged |
| anchors/endpoints/prompt/vector frames | A/T/H and existing frames | unchanged |
| formal logical generation | 5,580 | unchanged |
| formal scheduled judge identities | 5,580 | unchanged |
| P2 status | estimation only | unchanged |
| added experiment block | none | none |

No K2, V2, template 2x2, schedule/phase confirmation, sampled decoding, teacher-forced association,
power/coverage simulation, or alternate P/V profile is restored.

## 2. Statistical closure

### P1

rc1 named a stratified prompt bootstrap but left CI type, quantile convention, degenerate handling, and
completion undefined. rc2 binds `stratified_prompt_percentile_nearest_rank_v1`:

- exactly 10,000 replicates and at least 9,500 common successes;
- one-sided lower `Q_NR(0.05)` and two-sided `[Q_NR(0.025),Q_NR(0.975)]`;
- Bessel-corrected bootstrap SE and `SE<1e-8` failure;
- strict 0.10 and 1.5 lower-bound gates, with equality failing;
- no interpolation, normal/basic/studentized/BCa, reroll, or post-failure interval.

### P2 raw

rc1 named two-way Webb/max-statistic but left the weight law, two-way combination, observed/replicate SE,
critical value, endpoint formula, and synchronized identity open. rc2 fixes:

- ordered members `[P2-U(A),P2-B(T)]`;
- CR1 prompt-plus-vector-minus-intersection observed SE;
- ordered six-point Webb law and `psi=w_p+w_v-w_p*w_v`;
- fixed-scale studentization, `K_b=max_j|T*_(j,b)|`, and nearest-rank 0.95 critical value;
- exactly 9,999 replicates, at least 9,500 common successes, and simultaneous endpoints
  `theta_hat_j +/- q_max*SE_hat_j`;
- SHA256-counter RNG with separate `sync_unit_id` and metadata `member_id`; member identity never enters
  the stream seed.

The rc1 optional marginal/memberwise failure output is deleted. P0-05 and P0-08 are therefore closed as
symptoms of the same P0-03 algorithm/identity root, without registering another interval family.

### Retained descriptive intervals

K1, harmful clean, and benign broken RD now share one exact nearest-rank percentile rule, 95% common
completion, fixed block/unit identities, and enumerated failures. A finite zero bootstrap SD produces a
flagged degenerate descriptive interval only; it cannot support a test claim.

## 3. Freeze and execution lifecycle

The ambiguous measurement/behavior Freeze A/B pair is replaced by an append-only ordered lifecycle:

1. pre-outcome `measurement_specification_freeze.json`;
2. post-P1/pre-support `measurement_result_dose_manifest.json`;
3. pre-support `judge_freeze.json` after manual-only development;
4. post-support `support_execution_manifest.json`;
5. pre-confirmation `behavior_confirmation_freeze.json`;
6. pre-gold `human_validation_sample_freeze.json`.

The result/dose manifest alone contains realized complete cases, pooled values, median content norm,
binary64 `c_A/c_T/c_H`, and alpha. The specification freeze forbids those outcomes. Judge development is
fixed to an empty formal response set, manual document review, and zero generation/judge calls. Its human
time/non-call expense is recorded separately and never enters formal 5,580 accounting. The exact-JSON
judge parser replaces free-text/regex fallback.

Support retention is one nine-field conjunction. A ledger maps deterministically to `SUPPORTED`,
`SUPPORT_LIMITED`, or `NON_ESTIMABLE_IDENTITY`; A/T/H downstream status and attempted/unattempted behavior
are fixed. A/T support limitation does not move anchors or change P, V, endpoint, or human N.

## 4. Human correction and quota

The corrected P2-U and P2-B estimands now use exactly the raw survivor frames `M_A` and `M_T`. Automated
rates, validation residual numerators/denominators, point estimates, and every resample exclude
available-arm rows. An incomplete pair is a hard error; matched-frame directional comparison is
descriptive only.

The fixed720 allocator is executable and unique:

- critical matched P2 strata receive nonempty-class seats and a 30-item cell floor;
- global class targets are exactly `216/216/144/144`;
- capacity deficits use iterative capped Hamilton with fixed `3:3:2:2` weights and lexical ties;
- within-stratum selection uses one SHA256 rank, not mutable PRNG state;
- eligible capacity below 720 makes both corrected members non-estimable without changing N;
- A/T matched-cell capacity below 30 makes only the mapped corrected member quota-incomplete.

## 5. Statistical branch and resource deletion

The crossed-intercept marginal RD/CI branch is removed in full, including its model family, nested draw
obligation, replicate family, fallback language, statistical-lock row, figure/claim text, artifact
placeholder, registry/checklist duty, and resource entry. Raw paired and matched two-phase 9,999-replicate
families remain. Logical response, judge, and human counts are unchanged.

Actual call equations now distinguish fixed logical identities, pre-attempt integrity blocks, terminal
pre-judge exclusions, and retries. The absolute one-retry upper bound remains 11,160 for generation and
11,160 for judging.

## 6. Executable bindings

| Closure | Manifest SHA256 |
|---|---|
| statistics/RNG | `b0e3456a303ac4831daa35cc5aa162073a2cde1a91d5bb7d184a5df0b7e23ece` |
| freeze/judge/support | `6f80ba31a5fe79ec26693c69e0be410ce3fac3b2d4ff52f19105bb98f22a1a27` |
| human correction/quota | `f29943a08a87177a0fce99d536d3cebbb0c99d0ca10c55cd53c8bec27de020fd` |

All referenced code and fixtures are synthetic design references. The release manifest and verifier add
the rc2 protocol/diff/audit hashes and recheck all 28 captured preexisting files.

## 7. Deliberate non-outputs

This revision did not materialize checkpoint, prompt, anchor, vector, measurement, support, confirmation,
judge-output, or human-gold artifacts. It did not produce formal labels, estimates, intervals, figures,
or claims. External identity and execution-specific E0 prerequisites therefore remain RUN-BLOCKED while
the design choices themselves are closed.
