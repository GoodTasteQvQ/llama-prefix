# Paper 1 Stage 3 v3.5-rc2 binding amendment 01

Amendment ID: `v3.5-rc2-binding-amendment-01`  
Base protocol: `paper1_attention_sink_mu_experiment_design_v3_5_rc2.md`  
Creation date: `2026-07-22`  
Status: `DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`

This append-only amendment repairs only closure-audit roots `P0-STAT-01` and
`P0-STAT-02`. It is not a new experiment-design version and does not authorize
execution. It contains no formal data or result.

## 1. Authority and limited supersession

The base v3.5-rc2 protocol remains normative in full except for the following
two incomplete executable bindings:

1. For `P0-STAT-01`, this amendment supersedes only the missing executable
   details behind base sections 9.4 and 10.2 for the matched two-phase prompt
   and vector-aware simultaneous intervals. The old
   `scripts/stage3_design/v3_5_rc2/two_phase_correction.py` remains immutable
   historical evidence for its point-estimator cases; it is not the complete
   resampling/CI reference.
2. For `P0-STAT-02`, this amendment supersedes only the incomplete retained
   bootstrap binding behind base sections 7.4, 8.1, 8.3, 10.2, and 10.3 for
   K1, harmful clean, and benign broken RD. The retained-interval prose in the
   old statistical README remains immutable historical evidence; it is not a
   complete executable reference.

No other section, estimator, endpoint, output, sample, identity, claim, failure
mapping, freeze, or execution block is superseded. If amendment content is
read more broadly, that reading is invalid.

Within each repaired binding, normative priority is: this amendment's scope
and invariants; the component input schema and README; the hash-bound reference
implementation and synthetic golden fixtures; then the base prose for terms
not changed here. The component and aggregate manifests bind this chain. A
runtime backend may reproduce it but may not select or replace an algorithm,
identity, draw order, quantile, SE, failure, or fallback.

## 2. Immutable base and release binding

`writing/stage3 design/v3_5_rc2_binding_amendment_01/base_rc2_hashes_initial.sha256`
is the pre-amendment immutable baseline. Its 25 entries, including the base
protocol, closure audit, semantic diff, old statistics/closure/contracts, and
old implementation files, must reproduce exactly. The base protocol SHA256 is
`0aadb33cf14697f4e7751086b3663a176498d816435930bdafa2a2488a297e9d`.
The base rc2 release-manifest file SHA256 is
`79af2f0d2e62c4e2d95f3359bab74cbc873aed737baf25fee9e0a5b12e83d11a`.
This amendment neither rebuilds nor edits that historical release.

The aggregate binding manifest records every new implementation, schema,
README, fixture, and verifier; all base transitive dependency hashes;
`formal_data_used=false`; `no_scope_expansion=true`; creation time; producer
code/config hashes; and a canonical self hash. The aggregate release manifest
binds that manifest and the complete amendment inventory. Self hashes exclude
only top-level `self_sha256` and use sorted-key, no-whitespace, ASCII-escaped,
finite UTF-8 JSON.

## 3. Common RNG and serialization contract

Both repaired references use `master_seed=42` and exactly:

```text
seed_payload = UTF8(
  "v3.5-rc2|master=42|block=" + block_id
  + "|sync_unit=" + canonical_sync_unit_id
  + "|rep=" + six_digit_one_based_replicate_index
)
seed = SHA256(seed_payload)[0:16]
```

`canonical_sync_unit_id` is JSON with keys sorted by Unicode code point, no
whitespace, ASCII escapes, and finite values only. The counter engine emits
`SHA256(seed || uint64_be(counter))`, counter starting at zero, and consumes the
first unsigned big-endian 64-bit word. For `randbelow(upper)`, set
`limit=2^64-(2^64 mod upper)`; accept only words below `limit`, return
`word mod upper`, and consume another counter block after rejection. Replicate
indices start at one. Frames and hashes are validated before any draw.

`member`, `member_id`, cell identity, endpoint identity, and class identity
never enter a shared sync object. No member or statistic owns a separate stream
after a shared frame stream is defined. The reference and RNG goldens fix seed
bytes, initial words, accepted draws, frame hashes, and draw-consumption order.
No reroll or alternate serialization is allowed.

## 4. P0-STAT-01 matched two-phase binding

### 4.1 Input, matched frames, and canonical order

The admitted fields and JSON types are fixed by
`two_phase/two_phase_input.schema.json`. The only ordered members are
`[P2-U(A),P2-B(T)]`; they use `M_A` and `M_T`, respectively. Each matched pair
must have exactly one all-token and one content-token row. Empty frames,
incomplete or duplicate pairs, duplicate response identities, identity
collisions, invalid binary labels, missing selected gold, gold on an unselected
row, invalid/nonfinite inclusion probability, an empty arm, or a nonfinite
required value fails before resampling. An unmatched surviving arm never enters
an automated rate or residual ratio.

Formal input has exactly the frozen 50-prompt frame. Every matched response row,
selected or not, carries exactly one `phase2_stratum_id`. Each phase-two stratum
belongs to exactly one fixed member/arm and lists its complete ordered
`population_response_ids` plus ordered `sampled_response_ids`. Across strata,
the population lists are a disjoint exact partition of every `M_A/M_T` arm row;
no population row is omitted or added. A stratum has
`N_h=len(population_response_ids)` and `n_h=len(sampled_response_ids)`, and its
sampled-ID set is exactly the rows marked selected in that stratum. These
cross-references and counts are validated before labels, probabilities,
estimates, or draws.

The existing corrected-member support diagnostics are executable preconditions:
each member has at least 15 unique prompts and 10 unique vectors; the selected
inclusion weights have Kish ESS at least 20; and maximum normalized weight is at
most 0.20. Failure makes that simultaneous family non-estimable and never
changes the frozen sample or opens a replacement path.

Canonical order is fixed before frame hashing: member order as above; prompt
strata and prompt IDs ascending; all 20 vector IDs ascending; phase-two strata
and their sampled response IDs ascending; and response rows ascending by
`(prompt_category,prompt_id,vector_id,pair_id,arm_rank,response_id)`, where
all-token has the lower arm rank. The input must already be in this canonical
order; noncanonical input fails rather than being silently reordered. Any
repeated canonical identity is an input failure, not a tie.

### 4.2 Exact synchronized units and draw order

For block `p2-two-phase-prompt`, use exactly:

```json
{"axis":"prompt-stratum","family":"p2-two-phase-prompt","frame_sha256":"<prompt-frame-sha256>","stratum_id":"<s>"}
{"axis":"phase2-stratum","family":"p2-two-phase-prompt","frame_sha256":"<phase-two-frame-sha256>","stratum_id":"<h>"}
```

For block `p2-two-phase-vector`, use the same two forms with family equal to
`p2-two-phase-vector`, then exactly:

```json
{"axis":"vector","entity_id":"V_confirm","family":"p2-two-phase-vector","frame_sha256":"<vector-frame-sha256>"}
```

Within each one-based replicate, consume streams in this order:

1. ascending prompt stratum: draw that stratum's frozen frame size with
   replacement and record prompt multiplicities;
2. ascending phase-two stratum: a census stratum consumes zero draws; otherwise
   draw `n_h-1` sampled response indices with replacement from the ordered
   `n_h` sampled identities and record counts;
3. only for the vector block, draw 20 indices with replacement from the ordered
   20-vector frame and record vector multiplicities;
4. after all draws, evaluate the fixed member order; member evaluation consumes
   no RNG.

Both members share every applicable stream. A prompt block has no vector draw.
Frame/hash, replicate, axis, and within-stream draw order are fixed; unused
draws are not skipped and failed replicates are not rerolled.

### 4.3 Rao-Wu weights and recomputation

Prompt-category strata are resampled with replacement. For phase-two stratum
`h`, let `N_h` be its frozen eligible capacity, `n_h` its frozen selected count,
`f_h=n_h/N_h`, and `base_w_hi=N_h/n_h`. A census stratum `n_h=N_h` has
`g_hi,b=1` and consumes no phase-two draw. If `2<=n_h<N_h`, let `c_hi,b` be the
count among the `n_h-1` draws and set:

```text
g_hi,b = 1 + sqrt(1-f_h) * (n_h*c_hi,b/(n_h-1) - 1)
```

`N_h/n_h` must equal the validated population/sample list lengths from section
4.1; they are not independent caller summaries. For the prompt block,
full-judge row weight is `m_p,b` and selected residual
weight is `m_p,b*base_w_hi*g_hi,b`. For the vector block, multiply both by the
vector multiplicity `m_v,b`. Multiplicities are products, never concatenated
samples or sequential re-estimation weights. A positive matched stratum with
`n_h=0`, `n_h=1<N_h`, inconsistent `pi_i` versus `n_h/N_h`, or invalid
`N_h/n_h` is non-estimable. No stratum is dropped or pooled.

Every point estimate and replicate recomputes the matched judge rate with
denominator equal to the weighted `M_k` frame in each arm, the matched Hájek
residual ratio, armwise clipping to `[0,1]`, and then all-token minus
content-token RD. The two point members remain `P2-U(A)` for unsafe on `M_A`
and `P2-B(T)` for broken on `M_T`.

### 4.4 Fixed-scale simultaneous interval

Each block requests exactly 9,999 replicates. A replicate is common-successful
only when both ordered member estimates are finite and valid. Let the common
successful set be `S`; fewer than 9,500 successes fails the whole two-member
family. With no replicate SE:

```text
theta_bar_j_star = mean_(b in S)(theta_j,b_star)
SE_hat_j = sqrt(sum_(b in S)(theta_j,b_star-theta_bar_j_star)^2/(|S|-1))
T_j,b_star = (theta_j,b_star-theta_hat_j)/SE_hat_j
K_b = max_j abs(T_j,b_star)
q_max = K_(ceil(0.95*|S|)) after ascending sort
CI_j = [theta_hat_j-q_max*SE_hat_j, theta_hat_j+q_max*SE_hat_j]
```

`SE_hat_j` is fixed across replicates. Nonfinite SE, `SE_hat_j<1e-8`, nonfinite
studentized statistic/critical value/endpoint, or invalid denominator is fatal.
There is no memberwise or marginal salvage, alternate estimator, reroll,
interpolation, or fallback. The first canonical failure in reference execution
order is the only reported failure: pre-resampling input/identity/value/
denominator; insufficient prompt/vector, Kish-ESS, or maximum-weight support;
common successes below 9,500; invalid/nonfinite SE; nonfinite critical value/endpoint; binding/hash
failure. Thus 9,499 successes reports completion failure before any SE branch.
Available matched point estimates may remain reportable.

## 5. P0-STAT-02 retained-bootstrap binding

### 5.1 Shared frame and stream construction

The admitted fields/types and collision rules are fixed by
`retained_bootstrap/retained_bootstrap_schema.json`. Frame positions are
zero-based and contiguous. A frame hash is
`SHA256(UTF8(canonical_json({"axis":axis,"ordered_ids":[ids in frame order]})))`.
Duplicate identities or positions, position gaps, cell/row coverage errors, or
extra identities fail before resampling. The input does not supply a selectable
frame hash: the reference computes it from the validated ordered IDs and uses
that computed value in the sync identity.

The exact block and sync objects are:

```text
k1-profile prompt:
  {"axis":"prompt","entity_id":"sha256:<prompt-frame-sha256>","family":"k1-profile"}
k1-profile vector:
  {"axis":"vector","entity_id":"sha256:<vector-frame-sha256>","family":"k1-profile"}
harmful-clean-prompt:
  {"axis":"prompt","entity_id":"sha256:<prompt-frame-sha256>","family":"harmful-clean"}
benign-broken-prompt:
  {"axis":"prompt","entity_id":"sha256:<complete-prompt-frame-sha256>","family":"benign-broken"}
```

The K1 cell order is exactly
`[P2_A_all,P2_A_content,P2_T_all,P2_T_content]`. Rows are ordered by prompt
position and then vector position. In every replicate, K1 first consumes `P`
prompt draws from its prompt stream and then `V` vector draws from its vector
stream. The four cells share both draws; no cell/class/member stream exists.
Each K1 row weight is exactly prompt multiplicity times vector multiplicity.

Harmful clean orders the frozen harmful prompt frame by position and consumes
exactly that frame size in replacement draws. The formal benign complete-prompt
survivor frame may contain 1 through 30 prompts; fewer than two is then the
registered insufficient-unit failure, not a schema substitution. Benign first
requires a complete prompt's clean row plus exactly the ordered 20 steered vector rows, computes
`d_p=(1/20)*sum_v broken(p,v,T)-broken(p,clean)`, freezes the complete-prompt
frame, and only then consumes that frame size in prompt draws. It is forbidden
to resample benign rows before the 20-vector prompt average.

### 5.2 Statistics, intervals, and failures

K1 recomputes the four-class profile for all four fixed cells; harmful clean
recomputes its four-class profile; benign recomputes the prompt-average broken
RD. These are the only registered retained outputs. Each block requests exactly
10,000 replicates, never rerolls, and requires at least 95% common success,
which is exactly 9,500 successful replicates. K1 common success covers every
cell/class profile statistic; harmful common success covers all four classes;
benign common success covers its RD.

For each registered statistic, sort only the common-success values and report
`[Q_NR(0.025),Q_NR(0.975)]`, where
`Q_NR(q)=x_(max(1,ceil(qR)))`. No interpolation, BCa, normal, basic,
studentized, or fallback interval is permitted. When the finite bootstrap SD is
exactly zero, report `[theta_hat,theta_hat]` and
`degenerate_bootstrap=true`; this is not a failure and creates no testing claim.

The first canonical failure in reference execution order is the only reported
failure: input/schema/identity/collision/value/denominator; fewer than two
required resampling units; common success below 95%; nonfinite quantile or
endpoint; binding/hash failure. Nonfinite point estimates and invalid required
denominators fail before resampling. No block, cell, class, or member is salvaged
by an alternate interval.

## 6. Scope, budget, and claim invariants

This amendment adds no model, prompt, vector, anchor, endpoint, response cell,
human item, formal output, figure, claim, or execution block. It does not
restore any removed statistical branch, selector, simulation, K2, V2,
attention, rendering matrix, stochastic decoding, or phase confirmation. It
adds no p-value, global test, rejection, significance statement, or
confirmatory gate. P2 remains estimation-only.

The registered resampling counts remain exactly 9,999 for each two-phase block
and 10,000 for each retained-bootstrap block. The formal resource budget is
unchanged:

| Existing block | Logical generation | First-pass scheduled judge |
|---|---:|---:|
| support | 900 | 900 |
| P2 four cells | 4,000 | 4,000 |
| K1 reuse | 0 | 0 |
| harmful clean | 50 | 50 |
| benign T-steered | 600 | 600 |
| benign clean | 30 | 30 |
| total | 5,580 | 5,580 |

`P=50`, `V=20`, human response items `N=720`, primary assignments `1,440`,
and the scheduled assignment upper bound `2,160` remain unchanged. All
fixtures are explicitly synthetic. No formal P1, support, generation, judge,
or human experiment was run.

## 7. Verification and decision boundary

The aggregate static verifier must: reproduce every initial base hash; validate
all component, transitive, aggregate, and self hashes; directly import and call
both references against success and failure fixtures; verify production counts,
shared-stream member exclusion, exact sync JSON, frame hashes, draw order and
RNG goldens; prove executable coverage for both two-phase blocks and all three
retained blocks; scan prohibited active scope; and recompute generation, judge,
and human budgets. Any missing file or mismatch exits nonzero.

Passing these checks supports only the current status
`DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`. A later independent targeted audit owns
the final freeze decision.
