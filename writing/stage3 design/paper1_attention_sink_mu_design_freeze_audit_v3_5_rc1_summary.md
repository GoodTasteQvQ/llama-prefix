# TDSC DESIGN-FREEZE AUDIT SUMMARY

## Audit metadata

- Audit target: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc1.md`
- Version audited: `v3.5-rc1` only; no comparison with older protocol versions.
- Review role: IEEE TDSC senior methods reviewer.
- Audit mode: read-only. The target protocol was not modified.
- Delegation: three read-only subagents covered scope/claims, statistics, and reproducibility/resources.
- P0 count policy: unrestricted for this handoff. Findings are grouped by independent failure root; related symptoms are not counted as separate roots unless they create a distinct execution or claim path.

## Executive verdict

`DESIGN-FREEZE-FAIL`.

The scope reduction is statically closed and the logical generation/judge/human arithmetic is correct. The protocol is not yet design-frozen because several active inference, identity, and resource paths are not uniquely executable. A0/I0 artifacts remain separate from these design blockers.

The protocol cannot stop changing and cannot enter E0 implementation until the P0 items below are resolved. The previous three-P0 cap does not apply to this handoff.

## P0 blockers

### P0-01: Freeze A requires an outcome-derived value before the outcome exists

**Evidence:** L90-L91, L177-L185, L191-L204, L391, L415-L419, L869-L871.

Freeze A is required to lock the complete-case P1 frame, token count, numerator, value, and hash for `median_content_norm`. The same section requires Freeze A to be created before any formal P1 norm outcome is visible. That derived value is then used for the support screen and for `c_A/c_T`; exact dose/cell identity is only closed in Freeze B after support.

**Failure path:**

1. Compute the value before Freeze A: the pre-outcome freeze is contaminated.
2. Fill the value after P1: an immutable Freeze A is overwritten or incomplete.
3. Run support/P2 without it: the treatment dose and cell identity are not frozen.

**Affected validity:** internal validity, treatment identity, calibration reproducibility, and P2 estimand identity.

**Why downgrade is insufficient:** this invalidates the executed treatment identity itself; weaker wording cannot repair a dose that was not pre-frozen.

**Minimal repair:** Freeze A should lock only the pre-outcome specification/frame. After P1, create an immutable measurement-result/dose manifest, hash it before support, and make Freeze B reference it. No new experiment is required.

### P0-02: P1 primary and benign CI construction is not uniquely specified

**Evidence:** L315-L320, L365-L378, L535-L541. Related retained intervals: L495-L498 and L510-L511.

The protocol fixes bootstrap counts, seed, and resampling unit, but does not fix percentile/basic/studentized/BCa construction, quantile convention, finite-replicate rule, zero-variance handling, or nonfinite-bound handling. P1 declares non-estimability only for empty complete-case strata or zero aggregate denominators. With one complete prompt in a stratum, all bootstrap replicates can be degenerate while a finite-looking gate bound is still produced.

**Failure path:** two compliant implementations can produce different P1 lower bounds and different benign/K1/clean intervals. The P1 `0.10` gate can therefore change without changing data.

**Affected validity:** primary P1 claim, benign CI-only output, and retained descriptive interval outputs.

**Why downgrade is insufficient:** removing the CI would remove the registered P1 gate or the registered benign inferential output.

**Minimal repair:** freeze one existing bootstrap CI/quantile algorithm, a replicate-success rule, and all degenerate/non-estimable conditions. Do not add samples or endpoints.

### P0-03: P2 raw simultaneous CI leaves the Webb/max-statistic procedure open

**Evidence:** L451-L469, L676-L694, L700-L714.

`two-way Webb`, studentization, and a maximum absolute statistic are named, but the Webb weight distribution, two-way multiplier combination, centering, observed and replicate SE definitions, and CI endpoint formula are not specified. The backend manifest is promised to freeze these details later, but the protocol does not constrain the choice.

**Failure path:** two qualified analysts can use different Webb weights or studentization and obtain different intervals. The conflict between `canonical_unit_id` containing `member` (L710) and synchronized members sharing the same unit identity (L712-L713) also permits different RNG streams for a supposedly synchronized family.

**Affected validity:** P2 uncertainty intervals, synchronized-family reproducibility, and the statistical lock.

**Why downgrade is insufficient:** reporting point estimates only would violate the active P2 simultaneous-CI contract.

**Minimal repair:** freeze one exact two-way multiplier/Webb and max-statistic implementation, including member identity, SE, quantile, and stream serialization. Do not add a global test.

### P0-04: P2 model-based CI creates an unresolved nested-resource branch

**Evidence:** L25, L471-L491, L688-L699, L716-L752.

Each model fit requires 160,000 counterfactual random-effect draws, while the model-based interval requires 9,999 synchronized replicates. The protocol does not say whether every replicate refits and reintegrates, or whether one draw bank and one fit are reused. Under the natural refit/integrate path, the obligation is approximately `9,999 x 160,000 = 1,599,840,000` integration evaluations per endpoint, before counting fitting overhead; the two binary endpoints imply approximately 3.2 billion evaluations.

**Failure path:** executing literally can exceed the compact single-GPU/resource boundary; executing a cheaper single-fit path changes the frozen interval method. Neither statistical-fit count nor storage is included in the exact resource table.

**Affected validity:** model-based RD/CI reproducibility and resource feasibility.

**Why downgrade is insufficient:** L488-L490 only describes what to report after a fit failure; it does not predefine the algorithm or prevent a resource-dependent method choice.

**Minimal repair:** freeze a single-level integration/interval algorithm, draw-bank reuse and fit count, and include fit/memory/storage accounting. Alternatively remove the retained model-based obligation and its figure/claim/registry entries without adding scope.

### P0-05: P2 `marginal intervals if available` is an unregistered failure fallback

**Evidence:** L461-L466, L676-L694.

When the simultaneous interval fails, the protocol says to report “marginal intervals if available,” but provides no marginal CI algorithm, confidence level, multiplicity status, or availability criterion. The statistical lock registers only the simultaneous families.

**Failure path:** an analyst can decide after observing completion/failure whether to emit an unregistered interval.

**Affected validity:** missingness/failure analysis and claim boundary.

**Why downgrade is insufficient:** this is an outcome-dependent analysis branch, not a mere artifact gap.

**Minimal repair:** delete the fallback, or fully pre-register it as a non-confirmatory estimate with a fixed algorithm and label. Do not restore testing or add a robustness block.

### P0-06: Human-corrected RD uses a different survivor frame from the matched raw estimand without an explicit boundary

**Evidence:** L437-L449, L456-L466, L611-L627, L646-L668, L778-L779.

Raw P2 RD is defined on `M_k`, requiring the same prompt-vector pair to survive in both arms. The two-phase correction instead defines `p_judge_full` separately on each full eligible P2 arm and subtracts the two arm prevalences. With asymmetric terminal missingness, the corrected RD uses different survivor frames. The text permits directional agreement between automated and corrected estimates without explicitly stating that these are different estimands.

**Failure path:** a corrected direction can be driven by arm-specific missingness selection rather than the matched contrast.

**Affected validity:** estimand uniqueness and the interpretation of corrected-vs-raw agreement.

**Why downgrade is insufficient:** reporting the output as the same paired RD would remain invalid; merely calling it a “sensitivity” does not define the comparison boundary.

**Minimal repair:** either restrict corrected analysis to the corresponding `M_k`, or explicitly name it as an available-arm estimand and forbid paired-RD/agreement interpretation. No added endpoint is needed.

### P0-07: Fixed720 quota allocation is not a unique algorithm

**Evidence:** L562-L591, L209-L213, L606-L668.

The protocol supplies cell minima, a global predicted-class target, Hamilton redistribution, and tie-breaking, but does not define base weights or priority/reconciliation rules between critical and noncritical strata under capacity limits. Freeze B promises to lock “quota construction,” but the current protocol permits multiple quota traces.

**Failure path:** two implementations select different `n_h`, `pi_i`, ESS, and two-phase correction weights while respecting the visible constraints.

**Affected validity:** human-corrected estimand, inclusion probabilities, and reproducibility.

**Why downgrade is insufficient:** the quota trace changes the active correction estimator; it is not just a missing output artifact.

**Minimal repair:** specify the deterministic allocator and constraint priority, then validate it with the quota/inclusion fixture. Keep the sample size at 720.

### P0-08: Synchronized resampling identity has contradictory member semantics

**Evidence:** L700-L714.

`canonical_unit_id` includes family member identity, but synchronized family members are also required to share the same block/unit/replicate identity. This leaves it unclear whether synchronized members share or differ in RNG stream inputs.

**Failure path:** different streams produce different maximum-statistic resamples and CI endpoints, even though the protocol claims synchronized members.

**Affected validity:** simultaneous CI reproducibility.

**Minimal repair:** define separate `sync_unit_id` and `member_id` fields, and state exactly which fields enter the seed hash. No new resampling family is needed.

### P0-09: Support-screen failure status and retained identity are not deterministic

**Evidence:** L384-L399, L442-L449, L880-L890.

Support requires “retained identities” and at least 285 per anchor, but retained is not defined as completed, judge-eligible, parsed, or dose-valid. An A/T failure is described as making P2 “support-limited or non-estimable,” without a unique status rule or explicit execution rule for the 4,000 P2 responses.

**Failure path:** analysts can classify the same support result differently or decide whether to report an estimate after observing support failure.

**Affected validity:** support estimand, P2 reportability, and claim boundary.

**Minimal repair:** define retained identity and the exact A/T/H failure-to-status mapping; keep all fixed logical N unchanged.

### P0-10: Judge-development split has an unbounded resource path under literal execution

**Evidence:** L220-L229, L191-L202, L718-L752, L878-L890.

`D_judge_dev` is an independent split, but its size and any automated judge calls are not specified or included in the 5,580 scheduled total. If it requires judge development calls, the declared actual-call budget is incomplete; if it uses no calls, that exclusion is not stated.

**Affected resource feasibility and reproducibility:** a literal executor cannot derive the same judge-development workload or total calls.

**Minimal repair:** explicitly define `D_judge_dev` as zero-call/manual-only, or give it a fixed identity count and separate generation/judge budget. Do not let it alter formal labels or sample size.

## A0: defined protocol artifacts not yet generated

- The target results tree and all named manifests/freezes are absent in the workspace. The document itself declares the artifact tree future-only (L783-L828).
- External checkpoint, tokenizer/template, prompt frames, anchor manifest, vector manifest, backend manifest, measurement Freeze, behavior Freeze, and human sample lock remain A0.
- Actual estimates, labels, intervals, figures, fixture passes, and resource logs are correctly not claimed as existing.

These are RUN-READY blockers, not substitutes for the P0 design defects above.

## I0: implementation or fixture verification still required

- E0 mask, batch, layer/hook, span, pooled-token, complete-case, vector, anchor, matrix, CI, benign, quota, and budget fixtures are pending or unverified (L274-L298).
- `theta_hat_j` and `theta_(j,b)_star` are used without formal symbol definitions (L651-L656); several stratum/Qwen aliases also need schema-level mapping (L353, L415-L416).
- GPU/VRAM, batch, wall-time, storage, and statistical-fit accounting are not yet verified as implementation fixtures, apart from the P0 model-based ambiguity.

## P1/P2 risks, not independent P0 roots

- `dominates calibration` is gated in L377 but omitted from the Allowed list at L834-L845; close the whitelist wording before writing claims.
- L837 should distinguish scheduled `P=50,V=20` support from realized `M_A/M_T` support and model-based target frames.
- `N_b` is declared at L36 but unused.
- Names containing “behavior confirmation” remain, but explicit estimation-only/no-confirmation language prevents a ghost confirmatory block (L432-L434, L497-L498, L668-L684, L848-L860).

## TDSC dimension conclusion

- **Internal validity:** FAIL, primarily P0-01 and P0-06.
- **Statistical closure:** FAIL, P0-02, P0-03, P0-05, and P0-08.
- **Reproducibility:** FAIL, P0-01, P0-04, P0-07, P0-08, and P0-09.
- **Resource feasibility:** FAIL, P0-04 and P0-10; the fixed generation/judge/human arithmetic itself is correct.
- **Claim boundary:** scope-removal scan passes; remaining whitelist/support wording is P1 until corrected.

## Static verification record

- Invalid section references: none; §0.1, §4, §5.3, and §7.3 resolve.
- Removed scope residue: none found for K2, V2, rendering_2x2, stochastic decoding, attention/teacher-forced analysis, power/coverage simulation, P/V selector, or `P=100,V=30` fallback. Canonical rendering is an active protocol component, not removed scope.
- Budget arithmetic: support `900`; P2 `4,000`; harmful clean `50`; benign `630`; total logical generation/judge `5,580`; human universe `4,680`; generation/judge one-retry upper bound `11,160` each; human upper bound `2,160`.
- Hidden branches: model fit/draw reuse/refit, unregistered marginal intervals, support-failure status, quota reconciliation, and judge-development calls.
- No file changes were made by the audit.

## Handoff decision

This summary is intended for review by the main Codex branch. It intentionally reports all independent P0 roots rather than applying a three-P0 cap. The target protocol should remain `DESIGN-FREEZE-FAIL` until the P0 items are explicitly resolved; A0/I0 work must then be completed before RUN-READY/E0 execution.
