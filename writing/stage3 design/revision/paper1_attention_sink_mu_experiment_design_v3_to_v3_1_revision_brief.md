# Paper 1 Stage 3 实验设计 v3 -> v3.1 迭代规格

文档用途：本文件是交给 Codex 的修改任务书，不是新的实验协议正文。  
源文件：`writing/paper1_attention_sink_mu_experiment_design_v3.md`  
参考文件：`writing/paper1_attention_sink_mu_experiment_design_v2.md`、`writing/paper1_attention_sink_mu_experiment_design_v2_to_v3_revision_brief.md`、`writing/paper1_tdsc_readiness_audit.md`  
目标文件：`writing/paper1_attention_sink_mu_experiment_design_v3_1.md`  
修改方式：保留 v1、v2、v3 和已有 revision brief 不变；以 v3 为骨架新建可独立执行的 v3.1。  
目标标准：IEEE TDSC Regular Paper 对安全威胁模型、确认性推断、测量有效性、可复现性和 claim boundary 的要求。

---

## 1. 给 Codex 的执行指令

请完整阅读源文件、参考文件和本迭代规格，然后生成一份自洽、可直接冻结执行的 v3.1 实验协议。不要只在 v3 末尾追加勘误；必须把本规格要求整合进对应章节，并删除或改写与新设计冲突的旧表述。

执行时必须遵守：

1. 不修改 v1、v2、v3、已有 revision brief、实验代码或历史 artifacts。
2. 不运行实验，不启动模型生成，不虚构功效、方差、阈值或已有结果。
3. 保留 v3 已正确建立的 forensic/current 分线、factorial estimators、held-out splits、matched bridge、Gate-independent 三模型 minimum dose、dose geometry、judge-human validation 和 artifact registry。
4. 优先修复本规格中的 P0 问题；P1 只能在不重新引入混杂或选择性报告时加入。
5. 所有尚未确定的数值必须给出冻结时点、输入数据、算法和失败时的降级规则，不能写“根据结果决定”。
6. v3.1 的预算表、block registry、统计模型、primary families、允许结论和验收清单必须互相一致。
7. 若本规格与 v3 冲突，以本规格为准；若本规格未涉及，优先保留 v3 的严谨版本。

Codex 交付时只需创建目标文件，并给出简短变更摘要。除非用户另行要求，不实现代码、不运行测试、不修改其他文档。

---

## 2. v3.1 的总体定位

v3.1 继续以 measurement validity/reproducibility 为核心，不把结构 token 过滤包装为新防御，也不把随机方向下的 collapse 自动等同于成功攻击。

推荐核心主张：

> A template-sensitive activation outlier can dominate a Rogue-style norm calibration statistic. Under a matched intervention protocol, changing the calibration rule changes the actual dose represented by the same nominal multiplier and can shift the observed unsafe-to-collapse operating regime. The magnitude and behavioral consequences of this effect are evaluated within explicitly bounded white-box models, layers, templates, and vector families.

必须区分四个层级：

1. **测量层**：结构/template token 是否改变特定 `mu` estimator。
2. **协议层**：same-`c` 下 estimator 改变是否通过 `alpha=c*mu` 改变实际干预和行为。
3. **安全层**：剂量改变如何共同影响 coherent unsafe、refusal、safe/helpful 和 broken，而不是只观察 collapse。
4. **模型层**：在已测试的模型、层、template 和 vector distribution 内，控制 `rho` 与观测几何后是否仍存在 dose-response 差异。

Attention 仍是 secondary association question。没有对 attention key/value/logit 或目标 token 的干预时，不得声称 Attention Sink 导致或促成 collapse。

---

## 3. P0：必须修复的问题

### 3.1 增加正式威胁模型

v3 的 Security Relevance 仍是应用动机，不是完整 threat model。v3.1 必须新增独立的 `Threat Model and Security Objective` 章节，至少明确：

| 要素 | v3.1 必须写明的内容 |
|---|---|
| attacker access | white-box 模型权重、目标层 residual-stream hook、tokenizer/template、generation config；是否能读取 calibration prompts/activations |
| attacker action | 选择或构造 steering vector、选择 phase/layer 和 nominal `c`，在 inference 时执行 additive intervention |
| attacker knowledge | 是否知道 `mu` estimator、content norm、vector normalization、cache/phase semantics |
| attacker objective | 提高 coherent actionable unsafe 输出，同时避免 broken/refusal；不能把纯 collapse 记为成功 |
| defender/evaluator objective | 可比较地测量攻击强度、unsafe-to-collapse operating regime 和模型完整性 |
| excluded setting | remote black-box API、无中间层写权限、非加性干预、所有模型/模板的普遍结论 |

必须明确：本实验主要适用于 white-box activation-steering attack/evaluation 和可修改 inference pipeline 的研究场景，不得暗示普通远程 API 攻击者具备相同能力。

若 Paper 1 其他 Stage 已经提供第二攻击家族或 behavior-informed vector，v3.1 应显式说明 Stage 3 不重复该矩阵，并把 random-vector 结论限定为 Rogue-style protocol。若整篇论文没有任何非随机或第二 vector family，则在 `Threats to Validity` 中将其列为投稿级主要限制，并加入第 8.4 节的条件性最小 robustness block。

### 3.2 将论文级 primary claims 收敛为固定层级

v3 目前列出六个相互独立的 primary families，仅做 family 内 Holm，不能控制论文整体的 confirmatory claim 空间。v3.1 必须改为固定序贯层级：

```text
P1 Measurement primary:
  Qwen delta_select_tw on D_norm_confirm at the frozen formal layer

P2 Protocol primary, tested only after P1:
  Qwen mu_all_tw vs mu_content_tw at frozen transition-neighborhood c_T
  primary behavioral estimand = paired broken-rate risk difference

K1 Key security secondary:
  paired unsafe-rate difference and the full four-class distribution
  at the same matched cells

K2 Key cross-model secondary:
  categorical common-rho model x dose interaction on nonzero anchors
```

要求：

- 使用 fixed-sequence/hierarchical testing：P1 未通过预注册实质性与统计门槛时，P2 只作 estimation，不宣称确认性 protocol effect。
- P1 和 P2 构成论文主确认链；各自内部如有多个对照，使用 Holm 或预先指定单一主对照。
- historical bridge、template package、harmful/benign domain interaction、attention、all-layer profile 和 extra-layer experiments 降为 key secondary 或 exploratory。
- 不得把六个 family 分别校正后全部称为 co-primary。
- 所有结果仍报告 effect size 与 CI；层级只限制确认性措辞，不隐藏负结果。

P2 保留 `broken` 作为 calibration-to-collapse 的主终点，但安全解释必须同时报告 `unsafe`。正文主图必须展示 `(unsafe_rate, broken_rate)` 的联合 operating points 或 Pareto-style 图，避免把模型损坏写成攻击成功。

### 3.3 实施两阶段冻结，避免 E2 后修改 measurement analysis

v3 当前在 E1/E2/E3 之后统一生成 `analysis_freeze.json`，会使 E2 这个 measurement primary 暴露在分析冻结之前。v3.1 必须拆成两个不可覆盖的冻结文件。

#### Freeze A：measurement freeze

在读取 `D_norm_confirm` outcomes 前生成：

```text
measurement_freeze.json
```

至少包含：

- model/checkpoint/template/formal layer；
- `V_p/C_p` 和统一 special-token rule；
- `mu_all_tw/mu_content_tw/mu_all_pb/mu_content_pb` 公式；
- P1 estimand、bootstrap unit、CI、实质性门槛和缺失处理；
- all-layer simultaneous-band 方法；
- harmful/benign measurement comparison 的地位；
- code/config hashes。

E1 historical evidence可以用于定义 token 类别和历史 estimators，但不能在看到 E2 结果后更改 P1。

#### Freeze B：behavior freeze

仅使用 existing artifacts、E1/E2 的冻结输出、独立 `D_behavior_screen/V_screen` 的 range/nuisance 信息，在任何 behavior/attention confirmation outcome 可见前生成：

```text
behavior_freeze.json
```

至少包含：

- anchors、common support、confirmation N；
- prompt/vector manifests；
- P2/K1/K2 estimands；
- categorical dose model、GLMM/fallback；
- multiplicity hierarchy；
- judge version、failure/exclusion rules；
- template/attention secondary analysis；
- code/config hashes。

两个 freeze 文件必须分别带时间戳和 SHA256。Freeze B 不得回写或覆盖 Freeze A。

### 3.4 修复三点剂量与 spline/threshold 欠识别

v3 的 minimum dose 只有 `rho_A/rho_T/rho_H` 三个非零 anchors，却计划拟合 restricted cubic spline 并估计 `rho_50`。默认预算下，v3.1 必须采用以下保守方案：

1. 保留三个预冻结非零 anchors，作为 categorical dose levels；
2. 主模型不使用 restricted cubic spline；
3. K2 以 anchor-wise model contrasts、全局 `model x categorical_rho` interaction 和 simultaneous CI 为主；
4. 不把三个点拟合出的连续 `rho_50` 作为 primary/key secondary；
5. transition 只作区间定位：若相邻 anchors 的 broken probability 跨越 0.5，报告 `rho_50` 被 bracket 在两点之间；否则报告 `not bracketed within tested support`；
6. 不用二次曲线、任意 spline 或插值制造精确 threshold。

只有在 threshold estimation 对主论文不可缺少时，才允许在 behavior confirmation 前选择 dense-grid 备选设计：

```text
at least 5 nonzero common-support rho levels per model
```

该备选必须重新完成功效模拟、预算和 multiplicity 冻结；不能在看到三点 confirmation 后补点并与原数据合并为单次确认性曲线。若后续补点，只能作为独立 replication/secondary extension。

### 3.5 单独处理 vector-free clean baseline

clean baseline 每个 prompt 只需生成一次，没有定义良好的 `vector_id`。v3.1 必须禁止把同一 clean 输出复制到每个 vector 后作为独立观测输入 crossed GLMM。

默认处理：

- nonzero dose 的主 GLMM 只使用真实 `(prompt_id, model, vector_id, rho_anchor)` observations；
- clean baseline 以 prompt 为推断单位，单独报告四分类比例与 prompt-bootstrap CI；
- clean vs steered comparison 作为 prompt-level marginal sensitivity，先在每个 `(model,prompt,rho)` 内对 vectors 求均值，再与 clean 配对；
- clean 不参与 `vector_id` random effect，也不用于拟合三个非零 anchor 的 categorical interaction；
- 表格中分别报告 clean trajectories 和 vector-conditioned steered trajectories，不能把二者相加后称为同一 N。

若 Codex 选择其他有效建模方法，必须明确权重和相关结构，并证明不会把重复的 deterministic clean 输出形成伪重复。默认优先采用上述方案。

### 3.6 修正 crossed model 的层级结构

v3.1 的主 binary model 应考虑同一 prompt-vector pair 在不同 estimator/dose cells 中重复出现。推荐写为：

```text
logit P(y=1) = fixed effects
               + (1 | prompt_id)
               + (1 | model_id:vector_id)
               + (1 | model_id:prompt_id:vector_id)
```

说明：

- Qwen estimator/template paired analyses可省略 `model_id:` 前缀，但保留 prompt、vector 和 prompt-vector pair 结构；
- 跨模型中相同 PRNG index 不代表相同几何向量，因此 `vector_id` 必须 nested within model；
- 相同 semantic prompt 可跨模型保留共同 `prompt_id`，并对 model interaction 建模；
- 若 pair-level random intercept 造成 singular fit，按预注册顺序降级，不能按显著性选择模型；
- random slopes 可作为预注册 sensitivity，但不强行作为默认主模型。

预定义 fallback 顺序：

1. 去掉 pair-level random intercept、保留 prompt 与 model-nested vector random intercept；
2. GEE/cluster-robust model，明确 prompt 与 vector 的处理；
3. 先在 prompt-vector pair 内计算 paired contrast，再做 prompt/vector two-way bootstrap；
4. 按 prompt 聚合的 paired risk-difference bootstrap作为最保守 sensitivity。

报告每个模型的 convergence、singularity、方差分量和 fallback 是否触发。不得在多个模型中挑选最有利的 p-value。

### 3.7 收紧 `rho` 与 model-specific sensitivity 的结论

`rho=alpha/median_content_norm` 只能提供比 raw alpha 更可比较的尺度，不能完全控制非线性几何、tokenization、template、vector distribution 或 layer correspondence。

v3.1 必须：

- 把 `rho` 称为 normalized intervention magnitude，不称为完整生物/物理等效剂量；
- 同时报告 observed token-level `relative_dose_r`、`vector_alignment`、`cosine_drift` 和 generated-steered-call count；
- 冻结 formal layer 的选择理由和 normalized depth；
- 将模型结论限定为“within the tested models, formal layers, templates, and Rogue-style vector distributions”；
- 把 `model x rho` interaction 称为 residual model-associated sensitivity，不写成架构固有因果机制；
- 若 common support 不成立，不比较 threshold，也不移动 confirmation anchors追求预期语义。

---

## 4. Estimator 与 measurement 表述修订

### 4.1 不再声称 trimming 已完全正交分解

v3 已经正交拆分 selection 与 prompt aggregation，但只定义 `mu_content_trim10_pb`，没有完整的 `selection x aggregation x trimming` factorial。v3.1 应采用以下默认措辞：

> Selection and prompt aggregation are factorially decomposed; trimming and median estimators are robustness sensitivities rather than factors in the primary decomposition.

同步修改执行摘要、贡献、验收清单和图表标题。不要继续写“selection、aggregation、trimming 已全部正交”。

除非确有必要，不新增 `mu_all_trim10_pb`；新增它会扩展 secondary estimator 空间，但不会改变 behavior primary contrast。

### 4.2 P1 的效应量和 Gate 分开

P1 必须同时报告：

```text
delta_select_tw
mu_all_tw / mu_content_tw
paired prompt-level influence summaries
95% prompt-bootstrap CI
```

`lower CI > 1.5` 或 top-1 contribution >50% 只能作为资源扩展 Gate，不得自动成为统计显著性定义。P1 的确认性判定需要预冻结的 null、minimal relevant effect 和 CI/test rule。

### 4.3 harmful/benign measurement 不预设方向一致

删除“harmful 与 benign 必须同方向才算成立”的不必要理论预设。measurement consistency 应报告 domain-specific effect、interaction 和 CI；不一致可能揭示 template length/content composition 的 effect modification，而不是自动判定失败。

---

## 5. Template 实验的可识别边界

v3 的 `T0_native_user_only` vs `T2_controlled_no_system` 同时改变 system semantic content、role/header、whitespace、token count 和位置。因此默认 2x2 只能识别 **rendering/template package effect**，不能识别目标换行 token 的直接效应。

v3.1 必须：

1. 将章节和表格中的 `direct template effect` 改为 `fixed-alpha rendering-package contrast`；
2. 保留 A/B/C/D factorial 和以下 contrasts：

```text
B-A: rendering-package contrast at alpha0
D-C: rendering-package contrast at alpha1
C-A: dose contrast under T0
D-B: dose contrast under T2
template-package x alpha interaction
```

3. `D-A` 仍只能称 combined contrast，不称 mediation；
4. 不把任何 contrast 归因于单个 structural newline token；
5. 将 `T1_explicit_empty_system` 保留为 rendering decomposition/sensitivity，可先做 norm/token manifest，不默认扩为完整 behavior cell；
6. 若论文必须声称单 token direct effect，另立独立的 surgical intervention protocol，要求语义、长度、位置和 equal-count token controls；不得塞入默认 v3.1 2x2。

---

## 6. Strict Attention 的完整操作定义

### 6.1 target 冻结来源

目标定义分两步：

1. E1 historical forensic 预定义 candidate token class、template-relative region 和 historical layers；
2. E2 current held-out norm confirmation 只验证 candidate recurrence，并按 Freeze A 中的固定映射规则确定 current checkpoint target。

在读取 `D_attention_confirm` 前，把每模型/层的 target token class、允许位置集合、无法匹配时的 null-target 规则写入 Freeze B。不得在 attention outcomes 上重选 target/head/layer。

### 6.2 query、key control 和聚合顺序

v3.1 必须明确：

- prefill query set：目标 key 之后的 valid user-content 与 assistant-preamble queries；
- decode query set：teacher-forced replay 的前32个 frozen output steps；
- key target：冻结的单个或固定数量 structural positions；
- control keys：相同 prompt 内、相近 valid-position/causal exposure、equal-count 的 nonstructural keys；
- 匹配窗口、候选不足、多个 target 和 special token 的确定性处理；
- clean 与 steered replay使用完全相同 token prefix、query indices 和 control indices。

聚合顺序默认写为：

```text
query-level mass/rank
-> within head/layer summary
-> within prompt-vector summary
-> vector average within prompt
-> prompt-level inference
```

head、query、decode step 和 token 都不是独立样本。主 attention contrast 以 prompt 为推断单位；per-head/layer 分布属于 secondary，并使用 simultaneous band、BH-FDR 或 effect-size/CI only。

### 6.3 允许结论

观测性/teacher-forced attention 最多支持：

```text
attention concentration is associated with the frozen structural-token target
```

即使 steering 改变了 attention distribution，也不能由此推出 target attention 导致 broken。若要使用 `causes` 或 `contributes to collapse`，必须另立 attention/token intervention 协议和 clean utility controls。

---

## 7. 行为终点与安全解释

### 7.1 保留互斥四分类，但联合报告

保留优先级：

```text
broken > unsafe > refusal > safe/helpful
```

同时要求：

- `broken` 只表示不可用/病理输出，不是攻击成功；
- `unsafe` 必须 coherent、relevant、actionable；
- 主结果同时给出四分类 multinomial distribution；
- binary broken 和 binary unsafe 分别建模，不把 `not broken` 当作 unsafe；
- attack-to-collapse 图同时展示 unsafe 与 broken 的 CI；
- 若 unsafe 极稀少，报告 exact/clustered upper CI，不用 broken shift 代替攻击证据。

### 7.2 benign integrity 不要求与 harmful 同方向

将原 H6 改写为非方向性的 collateral-integrity question：

> Does the frozen transition intervention alter pathological generation differently between harmful and benign domains?

主报告 per-model domain difference 和 `domain x dose` interaction。benign 上更低或更高的 broken 都是可解释结果，不把“方向不一致”视为协议失败。

### 7.3 judge-human validation 必须可支持主终点

`D_judge_valid>=360` 必须说明抽样与加权：

- 按 model、dose、template/estimator arm 和 predicted class 分层；
- 可过采样 rare unsafe/broken，但总体性能必须用目标实验 prevalence 加权回去；
- 双人盲标、第三人 adjudication；
- 报告 raw agreement、Krippendorff alpha或适当 chance-corrected agreement、macro-F1、per-class precision/recall和per-model confusion；
- 预冻结 judge acceptance 门槛及未达到时的后果；
- 若 primary broken/unsafe 的 recall 未达门槛，必须在人工标注子集上重估关键 effect，或将对应结论降级，不能在 validation set 上继续调 prompt。

360 是最低总量，不保证每个模型和稀有类别都精确。功效/精度不足时优先增加关键类别人工样本，不把生成 N 当作人工验证 N。

---

## 8. 功效、预算与条件性扩展

### 8.1 Power simulation 必须与主模型一致

screening-based simulation 至少包含：

- prompt、model-nested vector、prompt-vector pair 三个方差来源或保守近似；
- within-pair estimator/dose correlation；
- baseline broken/unsafe prevalence；
- missing/failure rate；
- P1/P2 固定序贯检验和 P2 内 multiplicity；
- candidate `n_prompt in {50,75,100}`、`n_vector in {20,25,30}`；
- minimal relevant broken RD；
- rare unsafe endpoint的预期 CI，而不是强求80%显著性功效；
- GLMM nonconvergence/singularity frequency。

默认 50 prompts x 20 vectors 只能称为 planning configuration。最终 N 必须在 Freeze B 中锁定；若最大可承受 N 仍无足够 power，缩窄 claim 或标为 estimation-only，不增加更多 layers/schedules掩盖功效不足。

### 8.2 Equivalence claim

只有在 Freeze A/B 中给出 security-relevant margin、依据和足够 power 时才能作 equivalence。否则删除“等效”判定，只报告 CI 与 compatible effect range。

### 8.3 预算表必须重算但不虚构

默认采用三点 categorical dose 时，可保留 v3 的大致 generation 架构，但必须按最终 unique cells 重算：

```text
screening
mandatory harmful confirmation
vector-free clean baselines
benign confirmation
same-alpha identity QA
Gate-after secondary blocks
```

clean baseline 不计入 vector-conditioned response 数。表中分别写 logical cells、unique generated trajectories、judged responses和non-generation attention trajectories。

如果选择 dense-grid threshold 方案，必须在预算中显式增加对应 cells，不得继续保留约20,800的旧总数。

### 8.4 条件性 vector-family robustness block

只有整篇 Paper 1 缺少第二攻击/vector family 时，v3.1 才加入以下 key secondary 最小块：

- Qwen formal layer；
- 一种在独立数据上构造、与 confirm prompts 不重叠的 behavior-informed steering direction；
- frozen low/transition/high 三个 actual-dose或`rho` anchors；
- `D_behavior_confirm` 的预冻结子集和至少20 vectors/directions；若方法只产生一个确定性方向，则明确推断仅针对该方向，不伪装 vector population；
- broken、unsafe、refusal、safe 与完整 dose geometry；
- 不进入 P1/P2，不根据 random-vector结果选择方向。

若第二 family 已在 Paper 1 其他 Stage 完成，v3.1 只需交叉引用其 protocol/artifact contract，不重复生成。

---

## 9. Gate 与执行顺序修订

推荐顺序：

```text
P0  manifests + E0 QA
P1  Freeze A
P2  E1 historical reconstruction
P3  E2 held-out norm confirmation under Freeze A
P4  E3 descriptive existing-curve remapping
P5  independent behavior screening + power simulation
P6  Freeze B
P7  mandatory P2/K1/K2 behavior confirmation + benign minimum
P8  strict attention confirmation
P9  predeclared Gate-after secondary/replication blocks
P10 judge-human validation + locked analysis
```

Gate 可以决定：

- 是否运行完整 Qwen extra estimator matrix；
- 是否扩 Llama/Mistral attention；
- 是否运行 extra-layer、matched phase 或独立 replication；
- 是否启动本规格第8.4节的条件性 robustness block。

Gate 不可以决定：

- 是否报告 P1/P2/K1/K2 的负结果；
- 是否跳过三模型 minimum categorical-dose confirmation；
- 是否事后改变 anchors、target、primary endpoint、judge 或 statistical model；
- 是否把 screening并入confirmation；
- 是否因 p-value 接近0.05而加样。

---

## 10. v3.1 推荐章节结构

Codex 可以按以下结构重组 v3；标题可微调，但内容不可缺失：

1. Executive Summary and Claim Boundary
2. Threat Model and Security Objective
3. Historical Observations as Hypothesis-Generating Evidence
4. Research Questions, Hierarchical Primary Claims, and Endpoints
5. Steering, Actual Alpha, Rho, and Dose Geometry
6. Evidence Levels and Freeze Architecture
7. Models, Vectors, Prompt Splits, and Independence
8. Rendering, Padding, Span Annotation, and Estimators
9. E0 Tool QA
10. E1 Historical Forensic Reconstruction
11. E2 Held-out Measurement Confirmation
12. E3 Descriptive Existing-Curve Remapping
13. E4 Strict Attention Association
14. E5 Matched Protocol Confirmation
15. E6 Gate-Independent Three-Model Categorical-Dose Confirmation
16. Rendering-Package Factorial, Phase Controls, and Benign Integrity
17. Behavior Labels and Judge-Human Validation
18. Screening, Power, and Sample-Size Freeze
19. Statistical Analysis Plan
20. Gates, Unique-Cell Budget, and Block Registry
21. Security Relevance, Generalization, and Threats to Validity
22. Artifacts, Figures, and Reproducibility
23. Allowed/Forbidden Claims
24. Freeze and Acceptance Checklist
25. Execution Priority

---

## 11. 必须同步修改的表述

| v3 表述/设计 | v3.1 修改 |
|---|---|
| 六个 `Primary families` | 改为 P1 -> P2 固定序贯；其余 key secondary/exploratory |
| 三个非零点拟合 restricted cubic spline | 默认改为 categorical dose；阈值只 bracket/not-bracketed |
| clean baseline 与 vector observations 一起进入 crossed model | clean 单独做 prompt-level分析，不复制成20个vector rows |
| `vector_id` 跨模型同义 | 改为 vector nested within model；相同 seed/index不等于同几何方向 |
| 一次 `analysis_freeze.json` | 拆为 Freeze A measurement 与 Freeze B behavior |
| selection/aggregation/trimming 全部正交 | 仅 selection/aggregation factorial；trimming为sensitivity |
| `direct template effect` | 改为 fixed-alpha rendering-package contrast |
| harmful/benign collapse方向应一致 | 改为非方向性 domain effect modification/integrity question |
| `model-specific sensitivity` | 限定为 tested models/layers/templates/vector distributions 内的 residual difference |
| `broken` 足以代表攻击 operating point | broken与unsafe联合报告，broken不算攻击成功 |

---

## 12. 允许结论与禁止表述

### 12.1 允许

- 在冻结的 Qwen current line 中，all-token 与 content-token selection 对 `mu` 有或没有实质影响；
- same-`c` matched protocol 下，calibration rule 通过改变 actual alpha 改变或未改变 broken/unsafe 分布；
- historical curves 的 actual-alpha remapping 与 calibration-induced rescaling 一致或不一致；
- 三个测试模型在共同非零 categorical `rho` anchors 上表现出相同或不同的 dose response；
- rendering package 在固定 alpha 下有或没有行为影响；
- 冻结 structural target 与 attention concentration相关或不相关；
- harmful 与 benign domain 对病理输出的响应存在或不存在 effect modification。

### 12.2 禁止

- 由 hidden norm 或 attention weights直接推出 Attention Sink 导致 collapse；
- 由 rendering 2x2 推出单个换行 token 的直接行为效应；
- 用三个非零剂量点给出高精度 spline threshold；
- 把复制的 clean output 当作独立 vector observations；
- 把相同 PRNG seed下的跨模型向量称为同一个几何向量；
- 把 family 内 Holm 当作六个论文级 primary families 的整体错误率控制；
- 把 broken/collapse 记为越狱成功；
- 把 `rho` 当作完全控制跨模型内部几何的等效剂量；
- 把 observed model interaction写成架构固有因果机制；
- 把 random-vector结果推广到所有 activation steering vectors；
- 把 white-box hook攻击推广到普通black-box API威胁模型；
- 在 E2 后修改 P1，或在 behavior confirmation 后修改 Freeze B；
- 将 screening、rescue screening或事后补点并入初始 confirmation CI。

---

## 13. Codex 交付前验收清单

- [ ] v1、v2、v3 和已有 revision brief 均未修改
- [ ] 新建 `writing/paper1_attention_sink_mu_experiment_design_v3_1.md`
- [ ] v3.1 可独立执行，不要求读者回看本任务书
- [ ] 独立 Threat Model 明确 attacker access、action、objective 和 excluded setting
- [ ] P1/P2 固定序贯，其他结果已降为 key secondary/exploratory
- [ ] broken 与 unsafe 联合解释，broken 未被记为攻击成功
- [ ] Freeze A 在 E2 outcomes 前锁定
- [ ] Freeze B 在 behavior/attention confirmation outcomes 前锁定
- [ ] Freeze B 不覆盖 Freeze A
- [ ] 三个非零 `rho` anchors 默认按 categorical dose 分析
- [ ] 三点设计不再拟合 primary restricted cubic spline或精确`rho_50`
- [ ] threshold 使用 bracket/not-bracketed 规则
- [ ] clean baseline按prompt分析，未复制成vector伪重复
- [ ] vector random effect在跨模型分析中nested within model
- [ ] prompt-vector pair重复结构已进入主模型或预注册fallback
- [ ] GLMM singular/nonconvergence fallback顺序明确
- [ ] `rho` 和 model-specific claim 已限制到测试范围
- [ ] selection与aggregation factorial；trimming明确为sensitivity
- [ ] P1 effect/test rule 与资源 Gate 分开
- [ ] template 2x2 改称 rendering-package factorial
- [ ] template实验不再声称单structural token direct effect
- [ ] attention target由 E1 candidate + E2 frozen mapping确定
- [ ] attention query/control/aggregation和缺失target规则可执行
- [ ] attention推断单位为prompt，head/query/token不作独立样本
- [ ] harmful/benign改为非方向性domain interaction
- [ ] judge validation分层、加权、阈值和失败后果明确
- [ ] power simulation与实际hierarchical model和multiplicity一致
- [ ] equivalence无依据时已删除而非事后设margin
- [ ] budget区分clean、vector-conditioned、judged和attention trajectories
- [ ] 第二vector family已由其他Stage覆盖，或按第8.4节条件处理
- [ ] Gate不删除负结果、不跳过三模型minimum dose
- [ ] block registry、预算、统计计划和验收清单数字一致
- [ ] 允许/禁止结论与实验识别能力一致
- [ ] 所有 TBD 都有冻结输入、时间和决策算法

---

## 14. 最终交付要求

Codex 最终只需交付：

1. `writing/paper1_attention_sink_mu_experiment_design_v3_1.md`；
2. 一段简短变更摘要，至少说明如何修复：
   - TDSC threat model 缺失；
   - 六个 primary families 的整体多重检验问题；
   - E2 暴露在统一 analysis freeze 之前的问题；
   - 三点剂量与 spline/`rho_50` 欠识别；
   - clean baseline 的 vector 伪重复；
   - 跨模型 vector nesting 和 prompt-vector repeated structure；
   - template package 与单 token direct effect 混淆；
   - attention target/query/control/aggregation定义不足；
   - broken 与 coherent unsafe 安全含义混淆；
   - random-vector 外部有效性边界。

除非用户另有明确要求，不修改实验代码、已有 artifacts、v1/v2/v3、其他 Paper 1 文档或运行环境。
