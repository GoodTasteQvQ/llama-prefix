# PIPE-001 - PROTOCOL EXECUTION Audit

- finding ID: `PIPE-001`
- audit dimension: `PROTOCOL EXECUTION`
- audit date: `2026-07-22`
- versions: `v1.0`, `v2.0`, `v3.0`, `v3.1`, `v3.2`, `v3.3`, `v3.3.1`, `v3.3.2`
- criterion: whether another qualified experimenter can execute each version uniquely from the manuscript through the final report
- exclusions: no assessment of statistical optimality or resource sufficiency; no new model, endpoint, sample, scenario, or statistical method

## 1. Findings by Version

### v1.0

#### Subfinding 1

- finding ID: `PIPE-001`
- version: `v1.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:148`, `:189`, `:555`
- specific failure path: Models are identified only to the model-series level, prompt sources include "recommended/equivalent fixed set", and random vectors have no generation algorithm, seed, or identity manifest. Two qualified experimenters can therefore instantiate different model, prompt, vector, and cell identities.
- severity: blocking
- category: `P0`
- minimal fix: Freeze exact checkpoint revision/hash, dataset source/version and sampling algorithm, and vector PRNG/seed/index in the protocol or by a uniquely derived referenced artifact.
- blocks DESIGN-READY: yes

#### Subfinding 2

- finding ID: `PIPE-001`
- version: `v1.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:517`, `:529`, `:533`
- specific failure path: `low/transition/high` are derived from historical or pilot curves whose identities are not uniquely specified. Tie, missing-point, and out-of-range selection are not fully defined, so anchors and downstream cells are not unique.
- severity: blocking
- category: `P0`
- minimal fix: Freeze the input artifact identity and define anchor selection, tie, missing, and out-of-range rules.
- blocks DESIGN-READY: yes

#### Subfinding 3

- finding ID: `PIPE-001`
- version: `v1.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:424`, `:839`, `:854`
- specific failure path: QA failure has a stop rule, but formal generation/judge failures do not have a defined retry count, exclusion rule, or denominator treatment. Different executors can retry or count the same failure differently.
- severity: blocking
- category: `P0`
- minimal fix: Define the failure taxonomy, per-logical-call retry limit, same-config constraint, terminal state, and denominator accounting.
- blocks DESIGN-READY: yes

#### Subfinding 4

- finding ID: `PIPE-001`
- version: `v1.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:820`
- specific failure path: Required frozen, prompt, and vector manifests have not been generated.
- severity: high, run readiness
- category: `A0`
- minimal fix: After resolving the P0 rules, generate and hash the required manifests.
- blocks DESIGN-READY: no

#### Subfinding 5

- finding ID: `PIPE-001`
- version: `v1.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:399`, `:424`
- specific failure path: The manuscript records an undefined `valid_mask`, incorrect left-padding extraction, and other production-tool defects. The hard tool gate cannot currently be accepted.
- severity: high, implementation acceptance
- category: `I0`
- minimal fix: Repair the implementation and archive all Section 9.2 QA results.
- blocks DESIGN-READY: no

### v2.0

#### Subfinding 1

- finding ID: `PIPE-001`
- version: `v2.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:220`, `:252`, `:267`
- specific failure path: Historical checkpoint recovery is only "as far as possible"; current revision, prompt source/sampling, and vector-pool sampling are not uniquely fixed.
- severity: blocking
- category: `P0`
- minimal fix: Freeze all identities, hashes, and deterministic sampling functions.
- blocks DESIGN-READY: yes

#### Subfinding 2

- finding ID: `PIPE-001`
- version: `v2.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:651`, `:703`, `:773`, `:814`
- specific failure path: Peak/transition anchors, the low-`c` point, the benign "most explanatory" condition, and `20-30 prompts` allow executor selection. Arm and cell identities can differ.
- severity: blocking
- category: `P0`
- minimal fix: Define one selection order and tie/out-of-range rule for every anchor, condition, and sample count.
- blocks DESIGN-READY: yes

#### Subfinding 3

- finding ID: `PIPE-001`
- version: `v2.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:979`, `:1082`
- specific failure path: Insufficient precision can expand to `500/1000 as justified`, while failed/interrupted runs are only preserved, not governed by a unique retry, stop, and denominator rule.
- severity: blocking
- category: `P0`
- minimal fix: Define a deterministic expansion selector and failure state machine.
- blocks DESIGN-READY: yes

#### Subfinding 4

- finding ID: `PIPE-001`
- version: `v2.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:1062`
- specific failure path: Required model and prompt manifests are not present.
- severity: high, run readiness
- category: `A0`
- minimal fix: Generate dependency-closed manifests after resolving the P0 inputs.
- blocks DESIGN-READY: no

#### Subfinding 5

- finding ID: `PIPE-001`
- version: `v2.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:1101`
- specific failure path: The measurement implementation retains known defects and has not passed E0.
- severity: high, implementation acceptance
- category: `I0`
- minimal fix: Repair the implementation and pass E0.
- blocks DESIGN-READY: no

### v3.0

#### Subfinding 1

- finding ID: `PIPE-001`
- version: `v3.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:252`, `:258`, `:275`
- specific failure path: Checkpoint, prompt source, PRNG algorithm/seed, and whether confirmation uses 10 or at least 20 vectors remain executor choices before freeze.
- severity: blocking
- category: `P0`
- minimal fix: Fix the entities in the manuscript or define a unique derivation from identified inputs.
- blocks DESIGN-READY: yes

#### Subfinding 2

- finding ID: `PIPE-001`
- version: `v3.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:658`
- specific failure path: A/T/H are semantic neighborhoods, but no unique conversion from historical/current pilot artifacts to three numeric anchors is defined.
- severity: blocking
- category: `P0`
- minimal fix: Freeze source artifact identities and an executable anchor selector.
- blocks DESIGN-READY: yes

#### Subfinding 3

- finding ID: `PIPE-001`
- version: `v3.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:988`, `:995`
- specific failure path: Failed/interrupted reruns are said to follow predefined rules, but those rules are absent from the manuscript.
- severity: blocking
- category: `P0`
- minimal fix: State the failure taxonomy, retry limit, and denominator treatment.
- blocks DESIGN-READY: yes

#### Subfinding 4

- finding ID: `PIPE-001`
- version: `v3.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:1024`
- specific failure path: Analysis, prompt, and vector freeze artifacts have not been generated.
- severity: high, run readiness
- category: `A0`
- minimal fix: Generate and verify the required artifacts.
- blocks DESIGN-READY: no

#### Subfinding 5

- finding ID: `PIPE-001`
- version: `v3.0`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:375`
- specific failure path: Mask, span, vector, eager-backend, and dose-logging QA have no accepted implementation results.
- severity: high, implementation acceptance
- category: `I0`
- minimal fix: Execute all E0 fixtures and archive the outputs.
- blocks DESIGN-READY: no

### v3.1

#### Subfinding 1

- finding ID: `PIPE-001`
- version: `v3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:330`, `:342`, `:360`
- specific failure path: Model revision, prompt source/category frame, random PRNG/seed, and 20-30 confirmation vectors remain non-unique.
- severity: blocking
- category: `P0`
- minimal fix: Freeze exact identities and deterministic generation rules.
- blocks DESIGN-READY: yes

#### Subfinding 2

- finding ID: `PIPE-001`
- version: `v3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:705`
- specific failure path: Existing/pilot material merely proposes base anchors; no unique source selection or conversion function exists.
- severity: blocking
- category: `P0`
- minimal fix: Freeze source hashes, conversion formula, and tie/missing rules.
- blocks DESIGN-READY: yes

#### Subfinding 3

- finding ID: `PIPE-001`
- version: `v3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:1003`, `:1009`
- specific failure path: If a second vector family is missing, the protocol requires a behavior-informed direction without defining inputs, pooling, sign, partition, or deterministic replacement.
- severity: blocking
- category: `P0`
- minimal fix: Define one construction algorithm or one qualified fixed cross-reference.
- blocks DESIGN-READY: yes

#### Subfinding 4

- finding ID: `PIPE-001`
- version: `v3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:1030`
- specific failure path: Failed/interrupted runs still reference an unstated predefined rule.
- severity: blocking
- category: `P0`
- minimal fix: Include the failure state machine in the protocol.
- blocks DESIGN-READY: yes

#### Subfinding 5

- finding ID: `PIPE-001`
- version: `v3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:292`, `:309`
- specific failure path: Freeze A and Freeze B have not been generated.
- severity: high, run readiness
- category: `A0`
- minimal fix: Generate and hash both freezes after resolving the P0 inputs.
- blocks DESIGN-READY: no

#### Subfinding 6

- finding ID: `PIPE-001`
- version: `v3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:461`
- specific failure path: E0 has not been implementation-verified.
- severity: high, implementation acceptance
- category: `I0`
- minimal fix: Run all QA and archive the results.
- blocks DESIGN-READY: no

### v3.2

#### Subfinding 1

- finding ID: `PIPE-001`
- version: `v3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:318`, `:326`, `:381`
- specific failure path: Exact checkpoint, prompt dataset/source/category registry, and random-family PRNG/seed are only recorded later, not uniquely selected by the manuscript.
- severity: blocking
- category: `P0`
- minimal fix: Fix revision/hash, source/version/category registry, and random-vector PRNG/seed/index.
- blocks DESIGN-READY: yes

#### Subfinding 2

- finding ID: `PIPE-001`
- version: `v3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:581`, `:631`
- specific failure path: Base A/T/H values and their derivation from existing evidence are undefined. The deterministic V2 rescue operates only after this non-unique input.
- severity: blocking
- category: `P0`
- minimal fix: Freeze a base-anchor source/hash and conversion function.
- blocks DESIGN-READY: yes

#### Subfinding 3

- finding ID: `PIPE-001`
- version: `v3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:278`, `:295`
- specific failure path: Freeze A and Freeze B have not been generated.
- severity: high, run readiness
- category: `A0`
- minimal fix: Generate and hash dependency-closed freezes.
- blocks DESIGN-READY: no

#### Subfinding 4

- finding ID: `PIPE-001`
- version: `v3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:339`, `:876`
- specific failure path: `data/safe_pairs.json` exists, but the manuscript explicitly states that provenance, license, taxonomy, and leakage qualification are incomplete.
- severity: high, run readiness
- category: `A0`
- minimal fix: Archive only verifiable provenance; otherwise retain the specified generalization downgrade.
- blocks DESIGN-READY: no

#### Subfinding 5

- finding ID: `PIPE-001`
- version: `v3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:463`
- specific failure path: Vector construction, greedy repeatability, cell identity, and related implementation fixtures have not passed E0.
- severity: high, implementation acceptance
- category: `I0`
- minimal fix: Run and archive all fixtures.
- blocks DESIGN-READY: no

### v3.3

#### Subfinding 1

- finding ID: `PIPE-001`
- version: `v3.3`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:311`, `:315`, `:377`
- specific failure path: Model revision, prompt source/category registry, and random PRNG/seed remain open inputs.
- severity: blocking
- category: `P0`
- minimal fix: Freeze exact identities and deterministic generation rules.
- blocks DESIGN-READY: yes

#### Subfinding 2

- finding ID: `PIPE-001`
- version: `v3.3`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:705`, `:714`
- specific failure path: A/T/H are still proposed from unspecified existing/pilot inputs. Rescue logic cannot remove the initial-value ambiguity.
- severity: blocking
- category: `P0`
- minimal fix: Fix the base-anchor artifact and unique conversion.
- blocks DESIGN-READY: yes

#### Subfinding 3

- finding ID: `PIPE-001`
- version: `v3.3`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:263`, `:293`
- specific failure path: Freeze A/B and the human sample lock have not been generated.
- severity: high, run readiness
- category: `A0`
- minimal fix: Generate and hash the artifacts at their required times.
- blocks DESIGN-READY: no

#### Subfinding 4

- finding ID: `PIPE-001`
- version: `v3.3`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:329`, `:791`
- specific failure path: The V2 provenance artifact is incomplete.
- severity: high, run readiness
- category: `A0`
- minimal fix: Archive authentic provenance or apply the specified blocked downgrade.
- blocks DESIGN-READY: no

#### Subfinding 5

- finding ID: `PIPE-001`
- version: `v3.3`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:424`
- specific failure path: Greedy, stochastic, vector, and cell-hash QA have not been implementation-verified.
- severity: high, implementation acceptance
- category: `I0`
- minimal fix: Execute E0 and archive the results.
- blocks DESIGN-READY: no

### v3.3.1

#### Subfinding 1

- finding ID: `PIPE-001`
- version: `v3.3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:341`, `:345`, `:453`
- specific failure path: Dependency-closed references solve artifact closure but do not decide which checkpoint, prompt source/category registry, or random PRNG/seed to use.
- severity: blocking
- category: `P0`
- minimal fix: Fix these entities or deterministic selectors in the protocol.
- blocks DESIGN-READY: yes

#### Subfinding 2

- finding ID: `PIPE-001`
- version: `v3.3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:308`, `:381`
- specific failure path: Freeze B must contain base anchors, but the source identity and base-anchor generation function are absent. The unique V2 rescue starts only after that open choice.
- severity: blocking
- category: `P0`
- minimal fix: Fix exact base-anchor values/hashes or one source-to-anchor algorithm.
- blocks DESIGN-READY: yes

#### Subfinding 3

- finding ID: `PIPE-001`
- version: `v3.3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:284`, `:301`, `:323`
- specific failure path: Freeze A/B and the human sample lock have not been generated.
- severity: high, run readiness
- category: `A0`
- minimal fix: Resolve P0 and generate the dependency-closed artifacts.
- blocks DESIGN-READY: no

#### Subfinding 4

- finding ID: `PIPE-001`
- version: `v3.3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:359`, `:1005`
- specific failure path: The V2 candidate provenance has not become a qualified artifact.
- severity: high, run readiness
- category: `A0`
- minimal fix: Supply authentic provenance or retain the blocked downgrade.
- blocks DESIGN-READY: no

#### Subfinding 5

- finding ID: `PIPE-001`
- version: `v3.3.1`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:500`
- specific failure path: Anchor/reuse/budget/freeze-hash/two-phase fixtures have not been implementation-verified.
- severity: high, implementation acceptance
- category: `I0`
- minimal fix: Run E0 and archive fixture outputs.
- blocks DESIGN-READY: no

### v3.3.2

#### Subfinding 1

- finding ID: `PIPE-001`
- version: `v3.3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:381`, `:385`, `:507`
- specific failure path: Model, prompt, and vector identities remain non-unique. In particular, the random family only requires recording the algorithm and seed; it does not specify them.
- severity: blocking
- category: `P0`
- minimal fix: Fix checkpoint revision/hash, prompt source/category manifest hash, and random PRNG/seed/index partition.
- blocks DESIGN-READY: yes

#### Subfinding 2

- finding ID: `PIPE-001`
- version: `v3.3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:259`, `:267`, `:289`
- specific failure path: The `base_anchor_manifest` schema and validity checks are explicit, but any finite ordered triple and any prior source artifacts can pass. `conversion_formula_version` is required without an actual conversion formula, so another experimenter cannot uniquely derive A/T/H.
- severity: blocking
- category: `P0`
- minimal fix: Embed exact decimal/binary anchor values and source hashes, or specify one source-selection and conversion algorithm.
- blocks DESIGN-READY: yes

#### Subfinding 3

- finding ID: `PIPE-001`
- version: `v3.3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:321`, `:338`, `:363`
- specific failure path: Freeze A/B, base-anchor/simulation/backend manifests, and the sample lock have not been generated.
- severity: high, run readiness
- category: `A0`
- minimal fix: Resolve the P0 inputs and generate all dependency-closed artifacts.
- blocks DESIGN-READY: no

#### Subfinding 4

- finding ID: `PIPE-001`
- version: `v3.3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:411`, `:1173`
- specific failure path: V2 provenance/license/taxonomy qualification has not been generated. The protocol does define a blocked downgrade, so this is an artifact state rather than a design branch.
- severity: high, run readiness
- category: `A0`
- minimal fix: Archive only verifiable provenance; otherwise retain blocked status.
- blocks DESIGN-READY: no

#### Subfinding 5

- finding ID: `PIPE-001`
- version: `v3.3.2`
- exact file and lines: `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:554`, `:594`
- specific failure path: Base-anchor, P/V selector, backend, quota, Hajek, budget, and retry fixtures require implementation verification, and no accepted QA artifact is present.
- severity: high, implementation acceptance
- category: `I0`
- minimal fix: Execute all E0 fixtures before generating a valid freeze.
- blocks DESIGN-READY: no

## 2. P0/A0/I0 Counts

| version | P0 | A0 | I0 |
|---|---:|---:|---:|
| v1.0 | 3 | 1 | 1 |
| v2.0 | 3 | 1 | 1 |
| v3.0 | 3 | 1 | 1 |
| v3.1 | 4 | 1 | 1 |
| v3.2 | 2 | 2 | 1 |
| v3.3 | 2 | 2 | 1 |
| v3.3.1 | 2 | 2 | 1 |
| v3.3.2 | 2 | 2 | 1 |

## 3. DESIGN-READY Decisions

| version | DESIGN-READY | direct reason |
|---|---|---|
| v1.0 | no | Experiment identities, anchors/cells, and formal failure handling are non-unique. |
| v2.0 | no | Experiment identities, condition/N/anchor selection, and failure expansion are non-unique. |
| v3.0 | no | Pre-freeze inputs and anchors are non-unique, and failure rules are not stated. |
| v3.1 | no | The second-vector-family construction branch is additionally undefined. |
| v3.2 | no | Checkpoint/prompt/random-vector identities and base anchors are non-unique. |
| v3.3 | no | Same blocking identities and base-anchor derivation remain open. |
| v3.3.1 | no | Dependency closure does not resolve upstream entity selection. |
| v3.3.2 | no | Base-anchor schema is complete but its values/source algorithm remain open; model/prompt/random-vector identities also remain non-unique. |

## 4. PROTOCOL EXECUTION Conclusion

From v3.2 onward, stage order, arm/cell mapping, V2 rescue, technical-failure retry/downgrade, human sample locking, and the final reporting path are largely executable and codable. v3.3.2 has the highest execution closure.

Under the strict criterion that another qualified experimenter must obtain the same experiment from the manuscript alone, none of the eight versions is DESIGN-READY. The latest version still lacks four uniquely fixed inputs:

1. exact checkpoint identities;
2. exact prompt sampling sources and category registry;
3. random-family PRNG, seed, and index partition;
4. exact base-anchor values or one deterministic source-to-anchor algorithm.

`A0` and `I0` findings block RUN-READY but do not independently block DESIGN-READY. The negative DESIGN-READY decisions are caused by `P0` findings. No CROSS-DIMENSION finding is expanded here.
