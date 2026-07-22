# v3.5-rc2 binding amendment 01: retained bootstrap

This directory and its paired implementation directory are the normative executable binding for
P0-STAT-02 only. They supersede the incomplete retained-bootstrap execution wording in v3.5-rc2
sections 7.4, 8.1, 8.3, 10.2, and 10.3 without changing any registered output, frame, sample, endpoint,
claim, or execution block. All fixtures have machine-readable `synthetic_data=true`; no formal P1,
support, generation, judge, or human data are present.

## Bound implementation and public API

The standard-library reference is
`scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap.py`.
Its public production entry points are `analyze_k1`, `analyze_harmful_clean`, and
`analyze_benign_broken`. Production constants are uniquely fixed as:

```text
MASTER_SEED = 42
PRODUCTION_REPLICATES = 10000
PRODUCTION_MIN_SUCCESS = 9500
PRODUCTION_SUCCESS_FRACTION = 0.95
```

The `fixture_mode` parameter exists only for records carrying `synthetic_data=true`; it permits small
synthetic frame sizes but does not change the replicate count or completion boundary. Production calls
require `synthetic_data=false` and the frozen sizes K1 `P=50,V=20`, harmful clean `P=50`, and benign
candidate support `P=30,V=20`. Benign's complete-prompt frame may contain `1..30` prompts after terminal
missingness; fewer than two is non-estimable, while `2..30` is executable. No count, threshold,
quantile, RNG, estimator, or fallback is configurable.

## Canonical frames and collision precedence

Every frame is an ordered array of `{position, identity}` objects. Positions must be the exact
zero-based contiguous input order. A frame hash is

```text
SHA256(UTF8(canonical_json({"axis":axis,"ordered_ids":[ids in frame order]})))
```

Canonical JSON sorts keys by Unicode code point, has no whitespace, uses ASCII escapes, rejects
nonfinite values, and is UTF-8 encoded. K1 cells are ordered exactly
`[P2_A_all,P2_A_content,P2_T_all,P2_T_content]`; each cell's rows are ordered by prompt-frame position
then vector-frame position. Harmful-clean rows are an ordered, duplicate-free subset of the frozen
prompt frame and follow prompt-frame position; they need not cover every frozen prompt. Benign prompt records
exactly match the complete-prompt frame, and each prompt's steered rows exactly match the 20-vector
frame order.

Identity collision is checked before frame-order, value/denominator, and insufficient-unit checks. A
collision is any duplicate frame identity, duplicate frame position, duplicate response/row identity,
duplicate K1 `(cell_id,prompt_id,vector_id)`, duplicate harmful-clean prompt coordinate, or duplicate
benign `(prompt_id,vector_id)` coordinate. Even byte-identical duplicate rows are collisions; they are
never deduplicated. Rows outside their frozen frame are invalid and are never appended or substituted.

## Exact RNG and sync identities

All three blocks use the v3.5-rc2 SHA256 counter engine:

```text
seed_payload = UTF8(
  "v3.5-rc2|master=42|block=" + block_id
  + "|sync_unit=" + sync_unit_id
  + "|rep=" + six_digit_one_based_replicate_index
)
seed = SHA256(seed_payload)[0:16]
word = uint64_be(SHA256(seed || uint64_be(counter))[0:8]), counter starts at 0
limit = 2^64 - (2^64 mod upper)
accept word only when word < limit; draw = word mod upper
```

The exact block and sync identities are:

| block | `block_id` | exact canonical `sync_unit_id` object |
|---|---|---|
| K1 prompt | `k1-profile` | `{"axis":"prompt","entity_id":"sha256:<prompt-frame-sha256>","family":"k1-profile"}` |
| K1 vector | `k1-profile` | `{"axis":"vector","entity_id":"sha256:<vector-frame-sha256>","family":"k1-profile"}` |
| harmful clean | `harmful-clean-prompt` | `{"axis":"prompt","entity_id":"sha256:<prompt-frame-sha256>","family":"harmful-clean"}` |
| benign broken | `benign-broken-prompt` | `{"axis":"prompt","entity_id":"sha256:<complete-prompt-frame-sha256>","family":"benign-broken"}` |

`member_id` and cell identity never enter a sync object. For replicate `b`, K1 initializes its prompt
stream, consumes exactly `P` draws in draw-position order, then initializes its vector stream and
consumes exactly `V` draws. Those two multiplicity arrays are reused unchanged by all four cells; no
cell consumes RNG. Harmful clean and benign each initialize one prompt stream and consume exactly the
number of prompts in their frozen frame. A rejected uint64 consumes a counter word but not a draw. The
success golden includes a scripted rejection path where `2^64-1` is consumed and rejected before the
next word is accepted. There is no reroll of a failed replicate.

## Frozen estimators

K1 resamples `P` prompts and `V` vectors independently with replacement. For row `(p,v)`, the only row
weight is

```text
prompt_multiplicity[p,b] * vector_multiplicity[v,b]
```

Each of the four cells recomputes the four harmful-class proportions from that same product-weighted
draw. All 16 cell/class proportions share one common-success set. No cellwise stream or interval salvage
is allowed.

Harmful clean draws exactly the full frozen prompt-frame size with replacement and recomputes the
four-class profile using prompt multiplicity. The point-profile denominator is the retained-record
count. A frozen prompt without a retained row contributes zero to both numerator and denominator; a
replicate whose retained denominator is zero fails commonly and is not rerolled. Formal `records` must
remain nonempty (`1..50`); the synthetic invalid-denominator golden calls the internal profile helper
directly as a failure-contract unit witness and is not a valid formal input example.

For benign broken RD, a prompt enters the complete-prompt frame only when its clean row and every one of
the exact 20 vector rows are present and valid. The implementation first computes

```text
d_p = mean over the 20 frozen vectors of I(label=broken) - I(clean label=broken)
```

and only then draws the complete-prompt frame size with replacement and averages the selected `d_p`.
The clean response is not duplicated across vector rows and vectors are not resampled in this block.

## Interval and failure contract

Every block uses exactly 10,000 replicates and requires at least 9,500 common successes. For sorted
common-success values `x_(1)<=...<=x_(R)`, `Q_NR(q)=x_(max(1,ceil(qR)))`; the only interval is
`[Q_NR(0.025),Q_NR(0.975)]`. Interpolation, BCa, normal, basic, studentized, testing, p-values,
significance, rejection, confirmation, reroll, and fallback are forbidden. A finite zero bootstrap SD
returns `[theta_hat,theta_hat]` and `degenerate_bootstrap=true`; it is descriptive/CI-only.

First-failure precedence is exact:

1. `INPUT_SCHEMA_INVALID`
2. `IDENTITY_COLLISION`
3. `FRAME_ORDER_INVALID`
4. `INVALID_DENOMINATOR`
5. `NONFINITE_INPUT`
6. `INSUFFICIENT_RESAMPLING_UNITS`
7. `RESAMPLING_COMPLETION_INSUFFICIENT`
8. `NONFINITE_INTERVAL`
9. `RNG_IDENTITY_INVALID` for binding verification failures

Codes 1-5 map to `INPUT_INVALID_NON_ESTIMABLE`; code 6 maps to
`INSUFFICIENT_CLUSTERS_NON_ESTIMABLE`; code 7 maps to
`RESAMPLING_COMPLETION_NON_ESTIMABLE`; code 8 maps to
`NONFINITE_INTERVAL_NON_ESTIMABLE`; code 9 maps to `REFERENCE_BINDING_FAILURE`. Validation is staged so
that collisions precede ordering and all input-invalid conditions precede insufficient units.

## Verification

From the repository root, after setting project-local `TEMP`, `TMP`, and `NX_DAEMON=false`, run:

```powershell
python scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/verify_golden.py
```

The only success marker is `RETAINED_BOOTSTRAP_GOLDEN_PASS`. The verifier checks the component manifest
and canonical self hash, imports and executes the reference, runs all 10,000 replicates for K1,
harmful-clean, benign, and zero-SD success fixtures, independently recomputes their four full-output
canonical SHA256 digests, exercises a schema-shaped synthetic partial harmful-clean case, runs
failure/RNG cases, and compares exact canonical JSON. Missing files, hash mismatch, schema/constant
mismatch, or golden mismatch exits nonzero.
