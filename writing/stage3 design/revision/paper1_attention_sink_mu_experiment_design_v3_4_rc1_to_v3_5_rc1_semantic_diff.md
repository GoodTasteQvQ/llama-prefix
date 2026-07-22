# v3.4-rc1 -> v3.5-rc1 Semantic Diff

- source: `paper1_attention_sink_mu_experiment_design_v3_4_rc1.md`
- target: `paper1_attention_sink_mu_experiment_design_v3_5_rc1.md`
- change kind: scope reduction
- active target profile: `compact_single_gpu`
- machine-readable removal record:
  `paper1_attention_sink_mu_experiment_design_v3_4_rc1_to_v3_5_rc1_scope_removal_manifest.json`

This revision creates a new protocol and leaves v3.4-rc1 and every older version unchanged. It does not
add an optional execution path. Every target behavior count is a fixed constant or a fixed formula under
the one active profile.

## 1. Configuration diff

| Field | v3.4-rc1 | v3.5-rc1 |
|---|---|---|
| source/baseline | v3.3.2 | v3.4-rc1 |
| active execution profiles | selector/resource-dependent behavior paths | exactly one: `compact_single_gpu` |
| behavior model | Qwen + Llama + Mistral in cross-model block | Qwen only |
| behavior P/V | selected from 9 candidates or 100/30 resource fallback | fixed `P=50,V=20` |
| P2 status | conditional confirmatory family with downgrade | always `estimation_only` |
| behavior power selection | active selector contract | disabled |
| nested coverage/power | resource-gated obligation | disabled and removed |
| P1 sample N | selected from 100/150/200 per stratum | fixed 100 per stratum |
| benign | three-model clean + T-steered | Qwen only, `N_b=30` |
| human validation | fixed720 with two-phase correction | retained fixed720 with two-phase correction |

The P1 N change is deliberate: the target's `power_selection=disabled` is global, so the P1 measurement
primary remains intact while its prospective N-selection and extension split are removed.

## 2. Retained statistical core

| Component | Target semantics |
|---|---|
| P1 | Qwen pooled-token measurement primary; realized token shares; equal-domain sensitivity; prompt-level complete case; 10,000-replicate inference; 0.10 gate |
| P2 | Qwen all/content estimators at A/T; fixed 50 prompts x 20 vectors; raw paired RD; model-based marginal RD; two-member simultaneous 95% CIs; estimation only |
| K1 | four-class profile from the same four P2 cells; zero incremental responses |
| Human correction | fixed720 sample lock; IPW audit; Hájek residual correction; Rao-Wu phase-two uncertainty; prompt and vector sensitivities |
| Identity/freeze | experiment identity, anchor, vector identity, Freeze A/B, sample lock, self-hash and dependency closure |

P1 and P2 no longer form a confirmatory gate sequence. P1 retains its own measurement claim rule;
its outcome cannot change P2 execution or language.

## 3. Core matrix diff

### 3.1 Active target identities

```text
Qwen A/T/H support screen = 1 * 3 * 30 * 10 =   900
P2 four A/T matched cells = 2 * 2 * 50 * 20 = 4,000
K1 incremental cost                              = 0
harmful clean                                   = 50
Qwen benign T-steered    = 30 * 20             = 600
Qwen benign clean                               = 30
------------------------------------------------------
scheduled logical generation                 = 5,580
scheduled logical automated judge            = 5,580
```

The human sample frame excludes 900 support-screen outputs and does not duplicate K1, leaving a planned
formal universe of `4,000+50+600+30=4,680` responses.

### 3.2 Removed matrix obligations

The target has no cross-model behavior confirmation, second vector-family construction/screen/matched
confirmation, four-cell template-package experiment, schedule confirmation, sampled-decoding matrix, or
teacher-forced association trajectories. No bridge or same-alpha QA response is part of the active
logical budget.

## 4. P1 missingness closure

v3.4-rc1 distributed unresolved-token rules across Freeze A, E0, and estimator text. v3.5-rc1 defines one
prompt-level complete-case indicator. Any unresolved valid token, zero V/C denominator, nonfinite norm,
technical failure, or identity collision excludes the entire prompt simultaneously from all P1
functionals and resamples. Tokenwise deletion, imputation, replacement, and reroll are forbidden.

Every stratum reports frozen/successful/complete/excluded prompt counts, excluded identities/reasons,
pre-exclusion unresolved rate, and post-exclusion V/C denominators. The inference target is explicitly
the frozen-frame complete-case target.

## 5. P2 inference and claim reduction

v3.4-rc1 specified zero-null tests, family adjustment, confirmatory rejection, a Boolean decision gate,
a broken-RD practical threshold, and coverage/power-based P/V selection. v3.5-rc1 removes that entire
decision layer.

The target keeps three estimation views:

1. raw paired RD with a synchronized two-member prompt/vector simultaneous CI;
2. a pre-frozen crossed-intercept model-based marginal RD with a synchronized two-member CI;
3. mandatory two-phase human-corrected sensitivity with a synchronized two-member CI.

An interval excluding zero remains an estimate on fixed Qwen support. It is not translated into
significance, rejection, detection, confirmation, practical-threshold exceedance, or a general changed
profile. Automated/corrected disagreement is reported descriptively and never used to select a method.

## 6. Benign and human closure

Benign integrity is now one Qwen CI-only estimand. Each complete benign prompt has one clean response and
20 T-steered responses; vectors are averaged within prompt before clean subtraction. The prompt-level
broken RD receives a 10,000-replicate two-sided CI and no safety, harmlessness, equivalence, or general
domain-interaction claim.

The fixed human budget is unchanged in meaning and made exact:

```text
720 response items
1,440 primary annotation assignments
D_adj third-annotator assignments, where 0 <= D_adj <= 720
1,440 + D_adj total assignments; 2,160 scheduled upper bound
```

Screen outputs are excluded from the prevalence-restoration universe. P2 critical strata remain the four
logical cells crossed with predicted class. Noncritical strata now explicitly encode harmful clean,
benign clean, and benign T-steered sentinel identities.

## 7. Deletion closure

The following v3.4-rc1 surfaces are removed together rather than left as dormant or optional text:

| Removed block | Statistics/claims | Artifacts/figures | Budget/registry/checklist/priority |
|---|---|---|---|
| 9-candidate P/V selector and 100/30 fallback | removed | selection/coverage outputs removed | candidates and old totals removed |
| nested coverage/power and resource contract | removed | simulation plan/resource/coverage removed | fit budget and execution step removed |
| K2 three-model behavior | removed | manifests/tables/figures removed | cells and obligations removed |
| V2 construction/screen/confirmation | removed | vector-family tree/fixtures/figures removed | partial-state/rematch costs removed |
| template-package 2x2 | removed | package fixtures/figures removed | rescue/cells removed |
| phase confirmation | removed | schedule outputs removed | priority/checklist entries removed |
| sampled-decoding robustness | removed | sampled-output tree/figure removed | 1,200 responses and RNG QA removed |
| attention association | removed | trajectory tree/figure removed | 192 trajectories and BH-FDR duty removed |
| P2 confirmatory layer | null/rejection/p-value/threshold language removed | decision and power figures removed | decision gates and acceptance items removed |

The target retains fixed decode-only `phase` as an execution identity and `phase-two` as a survey-sampling
term. These are not references to the removed schedule-confirmation block.

## 8. Artifact contract diff

Retained future artifact obligations are limited to identity/anchor/vector manifests, Freeze A/B, the
human sample lock, inference backend, active QA fixtures, prompt/render/norm records, support and
confirmation responses, benign responses, judge/human records, statistics, figures, logs, and resource
accounting.

Removed future obligations include:

```text
simulation_plan.json
simulation_resource_contract.json
simulation_coverage/
second_vector_family/
rendering_2x2_fixtures/
v2_anchor_fixtures/
stochastic_robustness/
attention_confirm/
```

## 9. Deliberate non-outputs

This revision did not run a model forward, generation, judge, annotation, bootstrap, fit, integration,
coverage calculation, power calculation, or experiment. It did not create Freeze A/B, a response sample
lock, checkpoint/prompt/vector/anchor manifests, fixture passes, labels, estimates, intervals, figures,
or results. The two newly authored revision files are protocol documentation, not experimental artifacts.

Source SHA256 before and after this edit must remain:

```text
E209E2AEA170682C6CF17248197E36CE3B4702F3A66D83C69E241F93847BDD1E
```

The scope-removal manifest records the target protocol SHA256 used for this semantic diff.
