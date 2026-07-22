# v3.5-rc2 binding amendment 01: matched two-phase inference

This directory closes only `P0-STAT-01` from the v3.5-rc2 closure audit. It supersedes the incomplete
two-phase executable binding in `scripts/stage3_design/v3_5_rc2/two_phase_correction.py` for resampling
and simultaneous intervals. It does not alter that binding's matched point-estimand meaning, any other
rc2 clause, or any experiment identity. Every JSON fixture in this directory has
`synthetic_data=true`; no formal result, label, judge output, or human datum is present.

## Bound files and command

`two_phase_binding_manifest.json` binds this README, the input schema, reference implementation,
verifier, and success/failure golden files by SHA256. Its self hash is canonical UTF-8 JSON with
recursively sorted keys, ASCII escaping, comma/colon separators, and `self_sha256` omitted.

From the repository root, after setting project-local `TEMP`/`TMP` and `NX_DAEMON=false`, run:

```powershell
python scripts/stage3_design/v3_5_rc2_binding_amendment_01/two_phase/verify_two_phase_golden.py
```

The only success marker is `TWO_PHASE_AMENDMENT_GOLDEN_PASS`. The verifier imports and executes the
reference on both success and failure fixtures. It also verifies all hashes, schema constants, exact
sync JSON, RNG bytes, frame hashes, production counts, member sharing, and the 9,499/9,500 boundary.

## Input and canonical frames

The machine schema is `two_phase_input.schema.json`; `two_phase_reference.validate_input` is the
normative semantic validator. JSON objects have no unregistered keys. IDs are nonempty Unicode scalar
strings and are compared without normalization. Ordering is by Unicode code point:

1. members are exactly `[P2-U(A), P2-B(T)]`;
2. prompt strata and their prompt IDs are ascending;
3. vector IDs are exactly 20 ascending IDs in `V_confirm`;
4. phase-two strata and each stratum's sampled response IDs are ascending; each phase-two stratum is
   the frozen human-quota stratum for one logical member/arm, while its shared-stream sync object uses
   only the stratum ID and frame hash and never embeds `member_id`;
5. member rows are ordered by `(prompt_category,prompt_id,vector_id,pair_id,arm_rank,response_id)`, with
   `all-token` before `content-token`.

The ordered member tuple uses Draft 2020-12 `prefixItems`. Each present member position is checked
against its corresponding prefix schema, including every member `allOf` branch and its position-specific
constants; malformed `allOf` schemas fail closed. `items:false` permits those two prefix positions and
forbids only a third or later member. The verifier includes separate synthetic third-member, wrong-order,
and wrong-type witnesses. These do not alter or regenerate either fixed expected golden.

For `FORMAL_FROZEN_INPUT`, the prompt frame must contain exactly the already-fixed `P=50` prompts;
the smaller golden frame is allowed only with `synthetic_data=true`. `M_A` belongs only to
`P2-U(A)/unsafe`; `M_T` belongs only to `P2-B(T)/broken`. Each pair has exactly
one row per arm with identical prompt/category/vector identity. Empty members/arms, incomplete pairs,
duplicate response IDs, duplicate prompt-vector pairs, frame mismatches, or identity collisions fail.

Every member row carries its pre-gold human-quota `phase2_stratum_id`, whether selected or not. Every
phase-two stratum enumerates its full ordered `population_response_ids` and ordered
`sampled_response_ids`. The validator requires `N_h` to equal the population list and the corresponding
member/arm row count, `n_h` to equal the sampled list, the sampled list to equal exactly the rows with
`selected=true`, and the strata collectively to exhaust all member rows. Therefore no positive matched
stratum can be omitted and hidden by recomputing the phase-frame hash.

Each supplied `frame_sha256` is recomputed over canonical identity-only JSON. Prompt, vector, and
phase-two hashes cover their `frame_id` and ordered contents. A member hash covers its `frame_id`,
`member_id`, and ordered row identity fields, excluding outcomes and human labels. A mismatch precedes
value and resampling checks.

## Point estimator

For each matched member and arm, the judge component is the matched-arm mean with denominator `|M_k|`.
Selected residual rows use the unique lowest-terms rational string `pi=n_h/N_h` with no leading zero
(including census `1/1`) and weight `1/pi`. Equivalent but noncanonical strings such as `10/15` fail.
The correction is
the Hájek ratio of `weight*(gold-judge)` to `weight`, added to the judge rate and clipped armwise to
`[0,1]`. The member estimate is corrected `all-token` minus corrected `content-token`. Available-arm,
unweighted, unmatched, parametric, or unnormalized alternatives are absent.

## Resampling and draw order

Both blocks use exactly 9,999 one-based replicates and the ordered members above:

| block_id | family | axes |
|---|---|---|
| `p2-two-phase-prompt` | same as block | prompt-stratum, phase2-stratum |
| `p2-two-phase-vector` | same as block | prompt-stratum, phase2-stratum, vector |

Within each replicate, consumption is exact: prompt strata in canonical order, then phase-two strata in
canonical order, then the single vector-frame stream for the vector-aware block. Members consume no RNG;
the completed draw plan is shared and members are evaluated afterward in fixed order.

For prompt stratum `s`, draw exactly its frame size with replacement from its ordered prompt IDs and
record prompt multiplicities. For a phase-two stratum, `n_h` equals the ordered sampled-ID count:

- `n_h=N_h`: set every `g_hi=1` and consume zero draws;
- `2<=n_h<N_h`: draw exactly `n_h-1` indices with replacement and set
  `g_hi=1+sqrt(1-n_h/N_h)*(n_h*c_hi/(n_h-1)-1)`;
- `n_h=0`, `n_h>N_h`, or `n_h=1<N_h`: fail before resampling.

The vector-aware block draws exactly 20 indices with replacement from the ordered `V_confirm` frame.
Judge row weight is prompt multiplicity times vector multiplicity (vector multiplicity is one in the
prompt block). Residual row weight multiplies that row weight by `(N_h/n_h)*g_hi`.

## Exact synchronized identity and RNG

The only sync objects are:

```text
prompt = {"axis":"prompt-stratum","family":block_id,
          "frame_sha256":prompt_frame_sha256,"stratum_id":s}
phase2 = {"axis":"phase2-stratum","family":block_id,
          "frame_sha256":phase_two_frame_sha256,"stratum_id":h}
vector = {"axis":"vector","entity_id":"V_confirm","family":"p2-two-phase-vector",
          "frame_sha256":vector_frame_sha256}
```

They are serialized with sorted keys, no whitespace, ASCII escapes, and finite values. `member_id` and
`member` are rejected in every shared sync object. The seed and counter stream are exactly:

```text
payload = UTF8("v3.5-rc2|master=42|block=" + block_id
               + "|sync_unit=" + canonical_sync_json
               + "|rep=" + six_digit_one_based_index)
seed = SHA256(payload)[0:16]
block_c = SHA256(seed || uint64_be(c)), c=0,1,...
word_c = uint64_be(block_c[0:8])
limit = 2^64 - (2^64 mod upper)
accept word_c only when word_c < limit; return word_c mod upper
```

Rejected words consume their counter block. A separate stream starts at counter zero for every exact
`(block_id,sync_unit_id,replicate)` tuple. The success golden records exact canonical JSON, seed payload,
seed bytes, the first four 32-byte counter blocks, first big-endian words, and draw residues. The same
rejection primitive is also run with scripted words where two words are at or above `limit`; the golden
requires both to be consumed before the third word is accepted.

## Simultaneous interval

Every replicate recomputes matched judge rates, Hájek residuals, armwise clipping, and
`theta_(j,b)_star`. Prompt, phase-two, and vector multiplicities combine only by multiplication as
specified above. A denominator or statistic failure discards that replicate jointly for both members;
it is not rerolled. At least 9,500 common successes are required.

On the common-success set, each member's fixed scale is the Bessel sample SD of its replicate estimates
around their replicate mean. `SE<1e-8` or nonfinite SE fails the family. Studentization is exactly
`T*=(theta_star-theta_hat)/SE`; `K_b=max_j(abs(T*_(j,b)))`. Sort common `K_b` and take only nearest-rank
`q_max=K_(ceil(0.95R))`. The simultaneous interval is
`theta_hat_j +/- q_max*SE_j`. No interpolation, replicate SE, p-value, rejection, significance claim,
reroll, memberwise/marginal salvage, alternate estimator, or fallback exists.

## First failure precedence

The reference stops at the first condition in this order:

1. root schema/version/constants/member order and canonical frame order/hash;
2. identity collisions, empty member/arm, incomplete pair, or pair identity mismatch;
3. phase-two sample-size rules, including `n_h=0` and `n_h=1<N_h`;
4. binary values, exact `pi=n_h/N_h`, selection cross-references, and finite point denominators;
5. fewer than 15 member prompts or 10 member vectors;
6. for each corrected member, selected base weights pooled across its two arms have Kish
   `ESS=(sum w)^2/sum(w^2)<20` or `max(w/sum w)>0.20`, using only `w=1/pi`;
7. fewer than 9,500 common successes;
8. nonfinite/negative variance or fixed-scale `SE<1e-8`;
9. nonfinite quantile, critical value, or interval endpoint.

Report statuses are respectively `INPUT_INVALID_NON_ESTIMABLE`,
`INSUFFICIENT_CLUSTERS_NON_ESTIMABLE`, `RESAMPLING_COMPLETION_NON_ESTIMABLE`,
`INVALID_SE_NON_ESTIMABLE`, and `NONFINITE_INTERVAL_NON_ESTIMABLE`, with the exact `reason_code` emitted
by the reference. No later branch is evaluated after the first failure.

## Scope and production invariants

This reference adds no model, prompt, vector, anchor, endpoint, response, human item, output, test, or
experimental block. It keeps `P=50`, `V=20`, human `N=720`, logical generation 5,580, first-pass
scheduled judge 5,580, and both two-phase resampling counts at 9,999 with the 9,500 common-success floor.
Its only status is design reference material under `DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`.
