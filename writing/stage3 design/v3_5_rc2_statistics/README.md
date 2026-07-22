# v3.5-rc2 statistical closure reference

This directory is the normative executable reference for the v3.5-rc2 P1 bootstrap and raw P2
two-member simultaneous interval. It was created before the protocol replacement text below. It does
not contain formal P1, support, generation, judge, or human data and does not run any experiment.

## Binding and verification

The protocol binds `reference_statistics.py`, both successful golden files, both failure golden files,
and this specification by SHA256 in `statistical_reference_manifest.json`. Before any formal analysis,
the executor must run `verify_golden.py` under the exact runtime in that manifest and obtain the single
line `STATISTICAL_GOLDEN_PASS`. A missing file, hash mismatch, golden mismatch, runtime mismatch, or
nonzero exit blocks analysis. No backend manifest may replace an algorithm, quantile, standard error,
RNG serialization, completion threshold, or failure branch specified here.

Fixture replicate counts (`20`) exist only to make byte-exact verification fast. Production counts are
exactly P1 `B=10,000` and P2 raw `B=9,999`; the reference function defaults are the production values.

## Replacement map for the main protocol

The main agent should apply these normative replacements after copying rc1 to rc2:

1. Replace rc1 section 5.3 with **P1 replacement text** below.
2. Replace rc1 section 7.3 with **P2 replacement text** below. This replacement deletes the optional
   memberwise-interval fallback at rc1 L466 and creates no fallback interval.
3. Add **Retained percentile intervals** to rc2 sections 7.5, 8.1, and 8.2, then make the statistical-lock
   table point to it. This closes the related bootstrap-CI root without adding an endpoint or block.
4. Replace the P1/P2 portions of rc1 sections 10.1-10.2 with **RNG identity replacement text**. Preserve
   the exact count table except for deletions independently required by the resource closure.
5. Bind the manifest SHA256 and reference path in the rc2 artifact tree and inference backend manifest.

## P1 replacement text

Use the fixed complete-case strata and exactly `B=10,000` stratified prompt-bootstrap replicates. The
point functional is the rc2 section 5.1 pooled-token functional. Before resampling, both complete-case
strata must contain at least two unique prompt identities; every registered point functional and every
required denominator must be finite, and both pooled and equal-domain content means must be strictly
positive. Failure of any precondition makes P1 inference non-estimable.

For replicate `b=1,...,10,000` and each stratum separately, initialize the bound SHA-256 counter RNG with
`block_id=p1-inference`, `replicate_index=b`, and the canonical `sync_unit_id` containing exactly
`{"family":"p1","resample":"stratified-prompt","stratum":s}`. Draw `n_s_cc` integer indices uniformly
with replacement by the reference rejection sampler, retain all token records of each selected prompt
with its multiplicity, concatenate the two sampled strata, and recompute every numerator, count, mean,
ratio, share, and equal-domain functional. Token, layer, and position are never sampling units, and no
prompt ratio replaces pooled numerators/counts.

A replicate is commonly successful only if every recomputed functional is finite and every required
denominator is valid. Do not reroll a failed replicate. At least `9,500` of `10,000` common replicates
must succeed. For each registered interval, compute bootstrap `SE` as the Bessel-corrected sample SD of
the common successful replicate estimates. P1 inference is non-estimable if the common-success count is
below `9,500`, any required `SE` or bound is nonfinite, or any required `SE < 1e-8`.

For sorted successful values `x_(1) <= ... <= x_(R)`, define the only permitted quantile as
`Q_NR(q)=x_(max(1,ceil(qR)))`; interpolation is forbidden. The two-sided 95% percentile CI is
`[Q_NR(0.025),Q_NR(0.975)]`, and the one-sided 95% lower percentile bound is `Q_NR(0.05)`. Apply this to
`delta_select_tw`, `ratio_select_tw`, and the equal-domain sensitivity delta. P1 passes only when the
one-sided lower bound for `delta_select_tw` is strictly greater than `0.10`. `dominates calibration`
additionally requires the one-sided lower bound for `ratio_select_tw` to be strictly greater than `1.5`.
Equality fails each strict gate. No normal, basic, studentized, BCa, interpolated, or post-failure CI is
permitted.

## P2 replacement text

The raw family has exactly the ordered members `[P2-U(A),P2-B(T)]`. For member `j`, retain one paired
difference `d_i in {-1,0,1}` for each unique `(prompt_id,vector_id)` in its frozen `M_A` or `M_T`, and set
`theta_hat_j = n_j^-1 sum_i d_i`. Duplicate pairs, fewer than two prompt clusters, fewer than two vector
clusters, a nonfinite value, or an invalid difference makes the entire two-member simultaneous interval
non-estimable; available point estimates and frozen counts remain reportable.

Let `r_i=d_i-theta_hat_j`, `G_p` and `G_v` be the numbers of prompt and vector clusters, `S_p=sum_(i:p_i=p)r_i`,
and `S_v=sum_(i:v_i=v)r_i`. The only observed standard error is the fixed CR1 two-way inclusion-exclusion
standard error

```text
V_hat_j = [ G_p/(G_p-1) * sum_p S_p^2
            + G_v/(G_v-1) * sum_v S_v^2
            - n_j/(n_j-1) * sum_i r_i^2 ] / n_j^2
SE_hat_j = sqrt(V_hat_j).
```

If `V_hat_j <= 0`, `V_hat_j` is nonfinite, or `SE_hat_j` is nonfinite or `<1e-8`, the entire simultaneous
interval is non-estimable. Do not truncate a negative variance to zero and do not substitute a one-way,
iid, model-based, or marginal SE.

Use exactly `B=9,999` two-way Webb replicates. A Webb draw is equiprobable on the ordered six-point set
`[-sqrt(3/2),-1,-sqrt(1/2),sqrt(1/2),1,sqrt(3/2)]`. For replicate `b`, obtain independently keyed prompt
weights `w_(p,b)` and vector weights `w_(v,b)` from the bound SHA-256 counter RNG. The same prompt or
vector identity receives the same weight in both family members, including when `M_A != M_T`. Define

```text
psi_(i,b) = w_(p_i,b) + w_(v_i,b) - w_(p_i,b)*w_(v_i,b)
theta_centered_(j,b)_star = n_j^-1 * sum_i r_i*psi_(i,b)
T_(j,b)_star = theta_centered_(j,b)_star / SE_hat_j
K_b = max_j abs(T_(j,b)_star).
```

This is fixed-scale studentization: no replicate SE is computed. A replicate is jointly successful only
when both member statistics and `K_b` are finite. Do not reroll. At least `9,500` jointly successful
replicates are required. With `R` common successes, use the only permitted critical value
`q_max=Q_NR(0.95)=K_(ceil(0.95R))` after ascending sort. The simultaneous two-sided 95% interval is
`[theta_hat_j-q_max*SE_hat_j, theta_hat_j+q_max*SE_hat_j]`. A nonfinite critical value or endpoint makes
the entire family interval non-estimable.

On any family failure, report only available point estimates, scheduled/completed/retry/failure/eligible/
parsed/excluded/matched counts, and the exact enumerated failure code. There is no marginal-interval
fallback, no p-value, no rejection decision, no reroll, no memberwise salvage, and no change to P=50,
V=20, the endpoints, anchors, prompts, vectors, human N, or execution blocks.

## Retained percentile intervals

The following rule closes the already retained descriptive/CI-only intervals; it creates no new output.
Use the exact count in the statistical lock and the applicable frozen resampling unit: synchronized
prompt/vector multiplicities for K1, prompt resampling for harmful clean, and prompt resampling of the
already defined prompt-average benign RD for benign broken. Each block uses its own bound `block_id` and
canonical `sync_unit_id`. Recompute the registered statistic in each replicate, require at least 95% of
the fixed replicates to be commonly finite, and use only the nearest-rank two-sided percentile interval
`[Q_NR(0.025),Q_NR(0.975)]`. No interpolation, BCa, basic, normal, studentized, or fallback interval is
allowed. Fewer than two units in any required resampling dimension, a nonfinite point/bound, invalid
denominator, identity collision, or insufficient common completion is non-estimable. A finite zero
bootstrap SD is reported as the degenerate interval `[theta_hat,theta_hat]` with
`degenerate_bootstrap=true`; it does not authorize a significance, detection, or confirmation claim.

## RNG identity replacement text

The seed serialization for the bound P1 and raw P2 references is exactly

```text
seed_payload = UTF8(
  "v3.5-rc2|master=42|block=" + block_id
  + "|sync_unit=" + sync_unit_id
  + "|rep=" + six_digit_replicate_index
)
seed = SHA256(seed_payload)[0:16]
```

`replicate_index` starts at one. `sync_unit_id` is UTF-8 canonical JSON: object keys sorted by Unicode
code point, no whitespace, ASCII escapes enabled, finite JSON values only. The SHA-256 counter RNG emits
block `SHA256(seed || uint64_be(counter))`, starting counter at zero; each block contributes its first
unsigned big-endian 64-bit word. Uniform integers use rejection with
`limit=2^64-(2^64 mod upper)` and return `word mod upper` only for `word < limit`. Webb selection uses
`upper=6` and the ordered weight set above.

`member_id` is metadata and is forbidden inside `sync_unit_id`. For raw P2 the exact sync object is
`{"axis":axis,"entity_id":id,"family":"p2-raw"}`; `axis` is `prompt` or `vector`. Thus both members
share weights for a shared entity while different axes, entity IDs, blocks, and replicates use different
streams. P1 uses the exact strata objects stated above. Any member-dependent stream, zero-based replicate,
different key name/order, free-form delimiter identity, digest slice, endian choice, counter start,
rejection rule, or Webb ordering is an identity failure and blocks the affected inference family.

## Frozen failure codes

The executable strings in `NonEstimable` are the canonical implementation-level reasons. The protocol
maps them without analyst choice to these report statuses:

| condition | status |
|---|---|
| invalid/missing identity, duplicate, invalid value or denominator before resampling | `INPUT_INVALID_NON_ESTIMABLE` |
| fewer than two required prompt/vector sampling units | `INSUFFICIENT_CLUSTERS_NON_ESTIMABLE` |
| P1 required bootstrap SE nonfinite or `<1e-8` | `DEGENERATE_BOOTSTRAP_NON_ESTIMABLE` |
| P2 CR1 variance nonpositive/nonfinite or SE nonfinite/`<1e-8` | `INVALID_SE_NON_ESTIMABLE` |
| common successful replicates below the fixed threshold | `RESAMPLING_COMPLETION_NON_ESTIMABLE` |
| quantile, critical value, or interval endpoint nonfinite | `NONFINITE_INTERVAL_NON_ESTIMABLE` |
| code/runtime/hash/golden mismatch | `REFERENCE_BINDING_FAILURE` |

Precedence is the reference execution order. The first raised condition is recorded; no fallback branch is
evaluated. P0-05 and P0-08 are closed as direct consequences of the same P0-03 algorithm/identity root,
not as added analysis families.
