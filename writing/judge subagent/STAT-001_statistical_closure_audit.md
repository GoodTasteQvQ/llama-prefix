# STAT-001: STATISTICAL CLOSURE Audit

## Audit metadata

- Finding ID: `STAT-001`
- Dimension: `STATISTICAL CLOSURE`
- Versions: `v1.0`, `v2.0`, `v3.0`, `v3.1`, `v3.2`, `v3.3`, `v3.3.1`, `v3.3.2`
- Audit criterion: whether another qualified experimenter can uniquely execute the statistical protocol from the manuscript
- Scope restriction: no new endpoint, model, scenario, sample, or statistical method is proposed
- Repository observation: no named Freeze/simulation/backend/sample-lock artifact was found at audit time; the current `scripts/analyze_attention_sink.py` implements norm inspection but not the specified inferential pipeline

## 1. Findings by version

### v1.0

Source: `writing/stage3 design/paper1_attention_sink_mu_experiment_design.md`

| Finding ID | Exact lines | Concrete failure path | Severity | Category | Minimal fix | Blocks DESIGN-READY |
|---|---|---|---|---|---|---|
| STAT-001 | 369-375, 712-718 | Four behavior quantities are labeled Primary, while the primary-family list uses different contrasts. The estimand, analysis population, null, and hierarchy are not uniquely specified, so one analyst can run broken-only inference while another treats all four outcomes as primary. | Blocking | P0 | Freeze the population, estimand, contrast, null, and hierarchy for each existing primary endpoint. | Yes |
| STAT-001 | 701-706 | The primary model may be either binomial GEE or crossed logistic, and dose may use a spline or quadratic term. Different qualified analysts can produce different primary results. | Blocking | P0 | Select one existing primary model and deterministic fallback order with triggers. | Yes |
| STAT-001 | 712-720 | Holm members, raw-p construction, and ordering are not enumerated; the multi-df `model x dose` interaction has no global statistic. | Blocking | P0 | Freeze the exact test vector, legal joint statistic/df, raw p, and Holm ordering. | Yes |
| STAT-001 | 679-682, 957 | The two-way clustered bootstrap is named but not specified. Nonzero missing cells have no denominator, exclusion, or stopping rule. | Blocking | P0 | Define synchronized resampling and one deterministic missing/failed-cell rule. | Yes |
| STAT-001 | 749-764 | Sample-size simulation covers transition broken RD, but the stated primary set also contains ASR/refusal/safe and other families; the expansion gate is not simulated. | Blocking | P0 | Make the existing simulation correspond to the frozen primary claim and expansion Boolean gate. | Yes |
| STAT-001 | 6 | Primary hypotheses/matrix remain unfrozen. | Medium | A0 | Generate the required freeze artifact after P0 closure. | No |
| STAT-001 | 954; `scripts/analyze_attention_sink.py:28-52` | The repository has no implementation of the specified GLMM, Holm, or clustered-bootstrap pipeline. | Medium | I0 | Implement and validate the already specified procedures. | No |

### v2.0

Source: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v2.md`

| Finding ID | Exact lines | Concrete failure path | Severity | Category | Minimal fix | Blocks DESIGN-READY |
|---|---|---|---|---|---|---|
| STAT-001 | 115-154, 690-691 | Multiple RQs independently declare Primary endpoints, while the behavior section later declares only `broken_rate` primary. No common hierarchy, population, or estimand is defined. | Blocking | P0 | Freeze one hierarchy and the estimand/contrast for every retained primary endpoint. | Yes |
| STAT-001 | 901-911 | The behavior plan lists RD, RR, McNemar-type counts, and CIs but provides no primary model or fallback. | Blocking | P0 | Assign one existing analysis as primary and a deterministic fallback. | Yes |
| STAT-001 | 913-922 | Holm boundaries, nulls, and raw p values are undefined; cross-model structural-leverage `presence/absence` is not a computable global statistic. | Blocking | P0 | Enumerate the tests and define a legal global statistic. | Yes |
| STAT-001 | 868-871, 1180 | The two-way bootstrap has no resampling algorithm, and missingness is handled only by requiring zero missing cells. | Blocking | P0 | Freeze the bootstrap and the analysis consequence of terminal missing cells. | Yes |
| STAT-001 | 865-872, 928-934 | Expansion is driven by observed CI width without a prespecified candidate-N simulation or deterministic selection function. | Blocking | P0 | Connect the existing precision gate to a prespecified N-selection rule. | Yes |
| STAT-001 | 6 | Statistical scripts and primary hypotheses remain unfrozen. | Medium | A0 | Generate the required freeze artifact. | No |
| STAT-001 | 1097-1124; `scripts/analyze_attention_sink.py:28-52` | No corresponding inferential implementation is present. | Medium | I0 | Implement the existing plan and fixed-fixture validation. | No |

### v3.0

Source: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3.md`

| Finding ID | Exact lines | Concrete failure path | Severity | Category | Minimal fix | Blocks DESIGN-READY |
|---|---|---|---|---|---|---|
| STAT-001 | 844-859 | Fixed effects are only described as varying by family. The GEE correlation and small-sample correction are not specified. | Blocking | P0 | Freeze each block formula and deterministic fallback parameters. | Yes |
| STAT-001 | 870-906 | Six primary families lack explicit nulls and raw p values; Holm members are not exhaustive; multi-df interactions have no joint statistic. | Blocking | P0 | Freeze the test vector, global statistics, raw p, and Holm order. | Yes |
| STAT-001 | 830-836, 850, 1144 | Missingness is allowed for blinded re-estimation but has no formal analysis-denominator rule; parametric/two-way bootstrap execution is incomplete. | Blocking | P0 | Define the formal missingness and bootstrap rules. | Yes |
| STAT-001 | 808-826 | Nine P/V candidates are listed without a unique ordering or conjunction rule across families. | Blocking | P0 | Freeze candidate order, canonical scenario, and Boolean selector. | Yes |
| STAT-001 | 7, 910-912 | `analysis_freeze.json` has not been generated. | Medium | A0 | Generate and hash it after closure. | No |
| STAT-001 | 1114-1137; `scripts/analyze_attention_sink.py:28-52` | The GLMM/fallback/Holm pipeline has no implementation validation. | Medium | I0 | Implement and verify the existing procedures. | No |

### v3.1

Source: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_1.md`

| Finding ID | Exact lines | Concrete failure path | Severity | Category | Minimal fix | Blocks DESIGN-READY |
|---|---|---|---|---|---|---|
| STAT-001 | 894-916 | Fixed effects remain block-dependent placeholders; the GEE fallback says correlation handling must be specified but does not specify it. | Blocking | P0 | Freeze per-block formulas and fallback parameters in the manuscript. | Yes |
| STAT-001 | 204-206, 884-892 | K2 has no legal global statistic/df. Secondary multiplicity still permits multiple alternative procedures, and raw p is undefined. | Blocking | P0 | Assign one procedure to each family and define global-statistic/raw-p construction. | Yes |
| STAT-001 | 157-161, 189-191, 1030 | Missing rules are deferred to Freeze A/B, but the manuscript supplies no deterministic rule to freeze. | Blocking | P0 | Define the mapping from technical failure or missing label to the analysis denominator. | Yes |
| STAT-001 | 851-874 | Candidate sample sizes are listed without deterministic selection order; K2 interaction scenarios are absent. | Blocking | P0 | Freeze a finite scenario set, candidate order, and pass/fail function. | Yes |
| STAT-001 | 7, 292-327 | Freeze A/B have not been generated. | Medium | A0 | Generate dependency-closed Freeze artifacts. | No |
| STAT-001 | 1156-1187; `scripts/analyze_attention_sink.py:28-52` | GLMM, bootstrap, and multiplicity code is unverified and absent from the current analysis script. | Medium | I0 | Implement the existing plan and pass fixtures. | No |

### v3.2

Source: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_2.md`

| Finding ID | Exact lines | Concrete failure path | Severity | Category | Minimal fix | Blocks DESIGN-READY |
|---|---|---|---|---|---|---|
| STAT-001 | 200-202, 224-225, 819, 846-858 | Raw/Holm/max-T reporting is required, but raw-p and max-T algorithms are undefined. The K2 multi-df interaction has no scalar or joint statistic. | Blocking | P0 | Freeze a computable raw-p/max-T procedure and global interaction statistic. | Yes |
| STAT-001 | 706-721 | Judge parse failure may enter a manual queue or remain missing, with no deterministic branch condition; this changes endpoint denominators. | Blocking | P0 | Fix one branch and analysis population. | Yes |
| STAT-001 | 782-796 | P/V has no unique candidate ordering; K2 references preregistered interaction scenarios without defining them. | Blocking | P0 | Freeze candidate selection and a finite interaction-pattern library. | Yes |
| STAT-001 | 7, 278-315 | Freeze A/B and simulation artifacts have not been generated. | Medium | A0 | Generate and hash the specified artifacts. | No |
| STAT-001 | 461-480; `scripts/analyze_attention_sink.py:28-52` | Holm/max-T/GLMM/Webb implementation is absent. | Medium | I0 | Implement and validate the E0 fixtures. | No |

### v3.3

Source: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3.md`

| Finding ID | Exact lines | Concrete failure path | Severity | Category | Minimal fix | Blocks DESIGN-READY |
|---|---|---|---|---|---|---|
| STAT-001 | 561-578, 755-768 | K2/V2 global interactions have no multi-df statistic; Holm raw p and synchronized max-T are not algorithmically defined. | Blocking | P0 | Freeze the joint statistic/df, raw p, and max-T inversion. | Yes |
| STAT-001 | 716-751 | P/V candidates lack a unique selector, and K2/V2 interaction scenarios are not finite or deterministic. | Blocking | P0 | Freeze the scenario union, candidate order, and conjunction Boolean. | Yes |
| STAT-001 | 7, 263-305 | Freeze A/B and the sample lock have not been generated. | Medium | A0 | Generate the specified artifacts. | No |
| STAT-001 | 999-1055; `scripts/analyze_attention_sink.py:28-52` | Marginal integration, Holm/max-T, and validation code is absent. | Medium | I0 | Implement and verify the existing plan. | No |

### v3.3.1

Source: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md`

| Finding ID | Exact lines | Concrete failure path | Severity | Category | Minimal fix | Blocks DESIGN-READY |
|---|---|---|---|---|---|---|
| STAT-001 | 680-697, 991-997 | Max-T accepts scalar `theta_j/SE_j`, while K2/V2 are multi-parameter global interactions. No mapping to a legal joint statistic exists, and raw p has no formula. | Blocking | P0 | Freeze a computable joint statistic/df and bootstrap raw p for the existing global null. | Yes |
| STAT-001 | 633-645, 993-997 | Two-phase uses an unspecified IPW mean and refers to studentized max-T without defining two-phase `SE_hat` or `SE_star`. | Blocking | P0 | Fix the existing residual-correction normalization and studentization calculation. | Yes |
| STAT-001 | 903-908, 924 | The canonical planning scenario and conjunction rule across prevalence-specific power/precision results are not unique. | Blocking | P0 | Specify one planning scenario, candidate order, and first-pass rule. | Yes |
| STAT-001 | 647-655, 914-933 | Sample-size simulation evaluates automated Holm/CI only, while final wording also requires two-phase, human-quality, and support gates. | Blocking | P0 | Evaluate the existing final Boolean gate or explicitly limit the N guarantee to the automated sub-gate. | Yes |
| STAT-001 | 7, 284-335 | Freeze A/B and sample lock have not been generated. | Medium | A0 | Generate and hash them. | No |
| STAT-001 | 498-526; `scripts/analyze_attention_sink.py:28-52` | Two-phase, max-T, and method-selector implementation is absent. | Medium | I0 | Implement the existing fixtures. | No |

### v3.3.2

Source: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md`

| Finding ID | Exact lines | Concrete failure path | Severity | Category | Minimal fix | Blocks DESIGN-READY |
|---|---|---|---|---|---|---|
| STAT-001 | 762-779, 1150-1167 | K2/V2 global interaction is a multi-df null, but raw-p/max-T uses scalar `theta_j/SE_j`. The global Holm p value is therefore not computable as written. | Blocking | P0 | Freeze one joint statistic/df and its raw bootstrap p for the existing interaction vector. | Yes |
| STAT-001 | 721-733, 1159 | Two-phase max-T requires replicate-level `SE_j_star`, but the prompt-bootstrap section never defines how that SE is calculated. | Blocking | P0 | Define the unique two-phase point and replicate SE calculation and non-estimable rule. | Yes |
| STAT-001 | 975-986, 1086-1088 | The N selector uses automated P2-B Holm power and P2-U automated CI width, while the final claim Boolean also requires automated max-T, two-phase CI, judge quality, positivity, and cluster/weight gates. | Blocking | P0 | Evaluate the existing complete Boolean gate or explicitly restrict the N guarantee to the automated sub-gate. | Yes |
| STAT-001 | 321-361 | `base_anchor_manifest.json`, Freeze A/B, simulation/backend manifests, and sample lock were not found. | Medium | A0 | Generate them using the specified dependency-closure rules; do not fabricate values. | No |
| STAT-001 | 552-588; `scripts/analyze_attention_sink.py:28-52` | Raw-p, selector, Hajek, and max-T fixture implementations are absent. | Medium | I0 | Implement the already specified algorithms and pass all fixed fixtures. | No |

## 2. P0/A0/I0 counts

| Version | P0 | A0 | I0 |
|---|---:|---:|---:|
| v1.0 | 5 | 1 | 1 |
| v2.0 | 5 | 1 | 1 |
| v3.0 | 4 | 1 | 1 |
| v3.1 | 4 | 1 | 1 |
| v3.2 | 3 | 1 | 1 |
| v3.3 | 2 | 1 | 1 |
| v3.3.1 | 4 | 1 | 1 |
| v3.3.2 | 3 | 1 | 1 |

## 3. DESIGN-READY decisions

| Version | DESIGN-READY | Decisive reason |
|---|---|---|
| v1.0 | No | Estimand, model, multiplicity, missingness, and N are not closed. |
| v2.0 | No | No unique primary model; testing and expansion rules are not closed. |
| v3.0 | No | Fallback, global interaction, Holm, and N selector are not unique. |
| v3.1 | No | Freeze artifacts are expected to resolve choices that the manuscript does not define. |
| v3.2 | No | Global/max-T, parse missingness, and P/V selection are not closed. |
| v3.3 | No | Global statistic/max-T and sample-size selection are not closed. |
| v3.3.1 | No | Global statistic, two-phase studentization, and final-gate power are not closed. |
| v3.3.2 | No | Global statistic, two-phase SE, and Boolean-gate power remain unclosed. |

## 4. Dimension conclusion

The version sequence closes most endpoint definitions, population-average RD rules, Holm-family membership, fallback triggers, missingness taxonomy, and artifact dependencies. Three blocking paths remain in the latest protocol:

1. K2/V2 multi-df global interactions do not have a legal, computable joint statistic.
2. The v3.3.1/v3.3.2 two-phase max-T procedure does not define complete studentization.
3. Sample-size selection does not correspond to the complete Boolean gate that controls the final confirmatory claim.

All eight versions are therefore `NOT DESIGN-READY` in the `STATISTICAL CLOSURE` dimension. No finding in this record is `CROSS-DIMENSION`.
