# Paper 1 Stage 3 实验设计 v3.1 -> v3.2 迭代规格

文档用途：本文件是交给 Codex 的修改任务书，不是新的实验协议正文。  
源文件：`writing/paper1_attention_sink_mu_experiment_design_v3_1.md`  
参考文件：`writing/paper1_attention_sink_mu_experiment_design_v3.md`、`writing/paper1_attention_sink_mu_experiment_design_v3_to_v3_1_revision_brief.md`、`writing/paper1_tdsc_readiness_audit.md`  
目标文件：`writing/paper1_attention_sink_mu_experiment_design_v3_2.md`  
修改方式：保留 v1、v2、v3、v3.1 和全部已有 revision brief 不变；以 v3.1 为骨架，新建一份可独立冻结和执行的 v3.2。  
目标标准：IEEE TDSC Regular Paper 对安全问题定义、确认性终点、层级统计模型、外部有效性、可复现性和 claim boundary 的要求。

---

## 1. 给 Codex 的执行指令

请完整阅读源文件、参考文件和本迭代规格，然后生成一份自洽、可直接冻结执行的 v3.2 实验协议。不要在 v3.1 末尾追加勘误；必须把本规格整合到执行摘要、威胁模型、P1/P2、E2/E5/E6、功效分析、统计计划、预算、允许结论和验收清单等对应章节。

执行时必须遵守：

1. 不修改 v1、v2、v3、v3.1、已有 revision brief、实验代码或历史 artifacts。
2. 不运行实验，不启动模型生成，不虚构数据集、功效、方差、阈值、judge 性能或已有第二向量族。
3. 保留 v3.1 已正确建立的 forensic/current 分线、Freeze A/B、categorical dose、vector-free clean、attention mapping/missing rule、Gate-independent 三模型 minimum dose、dose geometry 和 append-only amendment。
4. 本规格中的 P0 修改必须全部落入 v3.2；不能只在 Threats to Validity 中承认问题而不修改主设计。
5. 所有尚未确定的实体或数值都必须有唯一冻结时点、允许输入、确定性算法和失败后的 claim downgrade。禁止写“根据结果选择最佳方法”。
6. 统计模型、功效模拟、block registry、预算、主图、允许结论和验收清单必须使用同一组 endpoints、anchors、N 和证据等级。
7. 若本规格与 v3.1 冲突，以本规格为准；若本规格未涉及，优先保留 v3.1 中更保守、更可审计的版本。

Codex 交付时只创建目标文件并给出简短变更摘要。除非用户另行要求，不实现代码、不运行测试、不修改其他文档。

---

## 2. v3.2 的总体定位

### 2.1 论文贡献重新定位

v3.2 必须把核心贡献定位为：

```text
security-evaluation measurement validity and reproducibility
```

而不是新的攻击能力、新防御或普通 black-box 漏洞。高范数结构 token 导致的 calibration distortion 主要影响使用 nominal `c` 比较攻击、模型或实现的 evaluator。具备完整 white-box knowledge 且能自由选择 actual alpha 的攻击者可以补偿该偏差，因此不得声称该偏差本身赋予攻击者新的能力。

推荐核心表述：

> A template-sensitive activation outlier can materially distort a norm-based steering calibration statistic. In a matched white-box evaluation protocol, this distortion changes the mapping from a nominal multiplier to the actual intervention magnitude and can alter the joint unsafe/integrity profile at preregistered operating points. The contribution is a security-evaluation validity and reproducibility finding, bounded to the tested models, layers, templates, decoding protocol, and vector families.

只有满足第 4.4 节规定的双 anchor 证据时，才能使用 `joint unsafe/integrity profile`。只有额外 dense-grid 或独立曲线证据足以定位整体曲线时，才能使用更强的 `operating-regime shift`。默认两点确认不得暗示恢复了完整连续曲线。

### 2.2 论文级确认链

v3.2 保留固定序贯，但重定义 P2，使安全目标与主行为终点对齐：

```text
P1 Measurement primary
  -> P2 Matched protocol primary family

K1 Full outcome-profile secondary
K2 Cross-model categorical-dose secondary
```

- `P1`：Qwen frozen formal layer 上的 `delta_select_tw`；
- `P2-U`：attack-neighborhood `c_A` 上的 paired unsafe-rate difference；
- `P2-B`：transition-neighborhood `c_T` 上的 paired broken-rate difference；
- `K1`：同一四个 matched cells 的完整四分类分布、其他 component contrasts 和 estimator x anchor interaction；
- `K2`：三模型三个非零 categorical `rho` anchors 上的全局 `model x dose` interaction。

P2-U/P2-B 构成同一个预注册 family，按 Holm 控制 family-wise two-sided alpha `0.05`。P1 未通过时，P2-U/P2-B 仍完整运行和报告，但降为 estimation-only。不得再把 `unsafe` 仅作为不影响论文主结论的附属指标，同时继续声称安全 operating profile 已被确认。

---

## 3. P0：修正 Threat Model 与安全问题定义

### 3.1 明确区分两个角色

Threat Model 必须分别定义：

| 角色 | 能力与目标 |
|---|---|
| intervention operator / adversary | white-box 访问模型、目标层 hook、template、calibration activations 与 vector；选择 layer、phase、direction 和 nominal `c`；目标是提高 coherent actionable unsafe，同时避免 refusal/broken |
| evaluator / defender / reproducer | 运行安全评估、比较模型或实现、解释 nominal `c`、actual alpha 和 unsafe-to-collapse profile；目标是避免不可比剂量、错误排序和 collapse 误判 |

必须明确：

1. 已知 `mu` 且可自由选择 actual alpha 的攻击者可以补偿 calibration mismatch；
2. 本文主要风险是 evaluator 使用 nominal `c` 时产生错误的攻击强度比较、错误模型排名、错误安全边界或不可复现实验；
3. white-box additive hook 不推广到 remote API、prompt-only jailbreak、权重攻击或非加性 intervention；
4. `broken` 是模型完整性损失，不是攻击成功；
5. security relevance 必须由 unsafe 与 integrity 两类结果共同表达。

### 3.2 增加可观测的安全后果

v3.2 必须把以下结果纳入主表或 key secondary 表，而不能只停留在动机文字：

- 同一 nominal `c` 下 actual alpha/rho 的偏移；
- `P2-U` 与 `P2-B` 的 paired RD 和 simultaneous/Holm-adjusted CI；
- 四分类 outcome profile；
- 按 raw `c` 与 actual alpha/rho 得到的模型或 protocol 排序是否改变；
- 若无法支持 ranking reversal，只报告 `ranking stability/uncertainty`，不得暗示已经观察到反转；
- unsafe 过稀时的 cluster-aware upper CI 和可识别边界。

Existing-curve remapping 仍是 descriptive，不能单独承担安全因果结论。

---

## 4. P0：重写 P1/P2 的 estimand、门槛和解释规则

### 4.1 P1 的目标总体与 bootstrap 必须唯一

`D_norm_confirm` 默认包含 100 harmful + 100 benign prompts。v3.2 必须明确 P1 的 target calibration population 是冻结的 50:50 prompt-stratified mixture，而不是未定义的 pooled convenience sample。

默认 bootstrap：

1. 在 harmful 和 benign strata 内分别以 prompt 为 cluster、有放回抽取原定数量；
2. 每次 replicate 从头重算 `mu_all_tw`、`mu_content_tw` 和 `delta_select_tw`；
3. 保留每个 stratum 的固定 prompt 数，不把 token、layer 或 token position 当作独立抽样单位；
4. 报告 mixture primary、两个 domain-specific estimates 和 domain interaction secondary；
5. 如果实际 calibration protocol 不是 50:50 mixture，必须在 Freeze A 前改写目标总体和权重，不能在 E2 后重加权。

必须明确 token-weighted estimator 在每个 bootstrap replicate 中如何重算，不得先计算 prompt ratios 再简单平均并仍称其为 `delta_select_tw`。

### 4.2 删除依赖历史 grid 分辨率的实质门槛

删除 v3.1 中：

```text
delta_P1_min = 0.5 * Delta_c_existing / c_ref_existing
```

原因是该值由历史 nominal grid 的人为间距决定，不是稳定的安全或测量效应门槛。

v3.2 默认使用固定的 protocol-level smallest effect of interest：

```text
delta_P1_min = 0.10
```

其含义仅是 same-`c` actual alpha 至少产生 10% 的相对 calibration shift；不得称为领域通用安全阈值。Freeze A 必须在 E2 前锁定该数值。若作者要使用其他值，必须在 v3.2 正文中给出一个唯一数值和独立于 `D_norm_confirm` outcomes 的依据，不能留下运行时任选项。

### 4.3 修正“点估计过门槛 + CI 排除 0”的错误规则

v3.1 的以下逻辑不足以证明 minimal relevant effect：

```text
point estimate >= delta_min
and CI excludes 0
```

v3.2 必须改为置信界直接越过实质门槛。

P1 默认确认规则：

```text
H0: delta_select_tw <= delta_P1_min
H1: delta_select_tw >  delta_P1_min

pass only if the preregistered one-sided 95% prompt-bootstrap
lower confidence bound is > delta_P1_min
```

同时报告 two-sided 95% CI、point estimate 和 ratio。不得用 two-sided CI 排除 0 再加点估计门槛代替上述检验。

`dominates calibration` 是比 `materially changes calibration` 更强的措辞。只有 `ratio_select_tw` 的预注册下置信界超过 1.5，或另一个在 Freeze A 明确且有置信区间支持的 dominance criterion 通过时，才能使用 `dominate`。否则只能使用 `materially changes`、`high leverage` 或对应的 null 结论。

### 4.4 P2 使用两个已生成 anchors，不增加默认 generation budget

E5 保留现有完整逻辑矩阵：

```text
2 estimators x 2 anchors x N_prompt x N_vector
```

其中：

```text
P2-U:
RD_unsafe_A = P(unsafe | mu_all_tw, c_A)
              - P(unsafe | mu_content_tw, c_A)

P2-B:
RD_broken_T = P(broken | mu_all_tw, c_T)
              - P(broken | mu_content_tw, c_T)
```

要求：

- `c_A/c_T` 只由 independent screening 和冻结的 all-token mapping 确定；
- 两个 contrasts 均使用 paired prompt-vector observations；
- P2-U/P2-B 使用 Holm，报告 marginal RD、adjusted CI/p-value 和两向 clustered/bootstrap sensitivity；
- 完整四分类分布在四个 cells 全量报告；
- `estimator x anchor` interaction 属于 K1，不在结果可见后决定是否升级为 primary；
- 如果 unsafe 太稀而最大可承受 N 无法提供预定精度，必须收窄安全主张，不得用 broken 替代 unsafe attack success。

### 4.5 P2 的实质效应语言

保留 v3.1 已声明的 broken practical margin `0.10` 时，只有 adjusted CI 完全位于 `>=0.10` 或 `<=-0.10` 一侧，才能声称 broken effect 达到该实质门槛。若 adjusted CI 仅排除 0，则只能声称存在非零差异并报告 compatible range。

unsafe 若没有可辩护的预注册 practical margin，不强行虚构一个数值；只做 Holm-adjusted difference-from-zero inference 和 CI estimation。任何 equivalence/no-material-effect claim 都必须有预冻结 margin 和相应 power。

结果措辞必须按证据分支：

| 结果 | 允许表述 |
|---|---|
| P2-U 与 P2-B 均支持且方向符合预注册解释 | calibration rule altered the tested joint unsafe/integrity profile at two preregistered operating points |
| 仅 P2-U 支持 | calibration rule altered unsafe probability at the tested attack-neighborhood point |
| 仅 P2-B 支持 | calibration rule altered collapse probability at the tested transition point |
| 两者均不支持 | no confirmatory behavioral difference was detected within the tested support；同时给 CI |

默认两点结果不得写成已识别完整连续 operating curve。

---

## 5. P0：修正统计层级与功效设计

### 5.1 Qwen-only matched model

P2 的 Qwen-only binary models 默认写为：

```text
logit P(y=1) = fixed effects
               + (1 | prompt_id)
               + (1 | vector_id)
               + (1 | prompt_id:vector_id)
```

fixed effects 至少包括 estimator、categorical anchor 和 estimator x anchor。P2-U/P2-B 可以通过该模型的 marginal standardization 得到，但必须报告 estimand 如何从 conditional model 转换为 marginal probability/RD。

### 5.2 Cross-model K2 必须加入 model-specific prompt heterogeneity

v3.1 缺少 `(model_id:prompt_id)`，不能充分表示同一 semantic prompt 在不同模型上的特异难度。v3.2 默认 cross-model binary model 改为：

```text
logit P(y=1) = fixed effects
               + (1 | prompt_id)
               + (1 | model_id:prompt_id)
               + (1 | model_id:vector_id)
               + (1 | model_id:prompt_id:vector_id)
```

其中：

- 相同 semantic prompt 可共享 `prompt_id`；
- model-specific prompt deviations 由 `model_id:prompt_id` 表示；
- vector 始终 nested within model；
- prompt-vector pair 项表示同一 pair 在多个 nonzero anchors/arms 中重复；
- 不把 residual pair variation 当成独立 replicate。

random slope 只可作为 Freeze B 预注册 sensitivity，并通过 convergence/coverage simulation 判断是否可稳定估计。不得按显著性选择 random-effects structure。

### 5.3 Fallback 顺序

v3.2 必须给出确定性 fallback trigger，例如 convergence warning、boundary/singular fit 和 variance component tolerance。推荐顺序：

1. 完整预注册 GLMM；
2. 若 full model singular，使用预注册的 reduced random-effects model，但不得首先删除 `model:prompt`；
3. pair-level paired contrasts + prompt/vector two-way cluster bootstrap；
4. prompt-level marginal paired bootstrap 作为最保守 sensitivity；
5. 每种方法都报告触发原因，不从多个结果中选择最有利 p-value。

若 two-way bootstrap 在 20 个 vector clusters 下覆盖不足，必须使用 small-cluster correction、wild cluster bootstrap 或把 vector 视为 fixed tested conditions并缩窄推广范围。具体方法在 Freeze B 唯一锁定。

### 5.4 P1 必须有独立的前瞻性 precision/power 论证

在 Freeze A 前，使用 historical data、`D_forensic` 或与 `D_norm_confirm` 不重叠的 pilot，完成 P1 cluster-bootstrap power/precision simulation。不得读取 `D_norm_confirm` outcomes。

至少模拟：

```text
n_harmful/n_benign candidate sizes
prompt-cluster variance and length heterogeneity
delta_select_tw around 0.10 and historically plausible larger effects
missing/unresolved span rates
one-sided lower-bound pass probability
```

默认 100+100 只是 planning size。若其不足以对 `delta_P1_min` 达到 0.80 power 或预定 CI precision，必须在 Freeze A 前增加 norm prompts或将 P1 改为 estimation-only。该变化不计入 generation budget，但要更新 records/storage 预算。

### 5.5 Behavior power 必须匹配新的 P2 family

Freeze B 前的 simulation 必须同时覆盖：

- P2-U/P2-B 的 Holm family；
- prompt、vector、prompt-vector pair variance；
- unsafe/broken prevalence 和 within-pair correlation；
- GLMM singular/nonconvergence rate；
- 20-30 vector clusters下的 CI coverage；
- P1 fixed-sequence gate；
- K2 global interaction的 precision或最小可识别范围。

`50 prompts x 20 vectors` 仍只是 planning configuration。若 unsafe 的有效事件数不足，不得仅依靠总 trajectory 数声称功效充分。

---

## 6. P0：第二 vector family 必须成为 paper-level 完成条件

### 6.1 不再保留模糊的条件式补丁

v3.1 的 `construct one behavior-informed direction` 不足以直接执行。v3.2 必须在 Freeze B 前形成以下二选一的审计结论：

1. **Cross-reference path**：Paper 1 其他 Stage 已完成独立、非随机或 behavior-informed vector family，并满足第 6.2 节全部条件；v3.2 保存 artifact path、protocol/hash、split关系和可比较 endpoints，新增 generation 为 0；
2. **Stage 3 execution path**：没有合格 cross-reference，则必须执行一份已完整定义的第二 family protocol；若算法仍未定义，v3.2 必须明确 `Freeze B blocked for paper-level generalization`，不能留下“届时构造一种方向”的自由度。

无论采用哪一路径，Paper 1 在投稿前都必须至少有一个 random unit vector 之外的 activation-steering family。否则全文只能定位为 random-perturbation calibration/collapse audit，不得推广到 activation steering attacks 一般。

### 6.2 合格第二 family 的最低 manifest

必须明确并冻结：

- vector construction algorithm 和公式；
- construction prompts/contrast pairs 的来源、版本和 split；
- 与 norm/screen/behavior/attention confirmation prompts 的不重叠规则；
- target layer、token pooling、centering、whitening或无 whitening；
- normalization 和 sign determination；
- 一个确定性 direction 还是可推广的 direction population；
- 多 direction 时的 seed/bootstrap/partition 生成规则；
- 不根据 random-vector confirmation outcomes筛选方向；
- low/transition/high actual-alpha或rho anchors 的独立 screening/freeze；
- 四分类、unsafe/broken、dose geometry 和 failure logging；
- 对应统计单位和可推广范围。

若方法只产生一个确定性 direction，不得把 prompt responses 伪装成 20 个 direction clusters，也不得作 vector-population inference。

### 6.3 预算

若缺少 cross-reference，保留 v3.1 的 planning 范围：

```text
30 prompts x 20 independently constructed directions x 3 anchors = 1,800
hard cap: 50 x 20 x 3 = 3,000
```

只有方法确实产生至少 20 个独立、预冻结 directions 时才能使用该公式。确定性单方向方法必须按真实 trajectory 数重算。v3.2 必须分别列出：

- cross-reference path total；
- second-family execution path total；
- 默认 random-family mandatory total；
- human annotations 与 generated trajectories。

不得在第二 family 缺失时继续把约 `20,784` 描述为投稿级完整预算。

---

## 7. P0：补齐 prompts、decoding 和运行随机性

### 7.1 Prompt sampling frame

仅保存 prompt hash 不足以定义目标总体。v3.2 必须要求每个 split manifest 保存：

```text
dataset/source name and version
license and retrieval date
language and harm/benign taxonomy
category quotas and sampling probabilities
inclusion/exclusion rules
exact and semantic dedup method/model/threshold
prompt normalization rules
cross-split and vector-construction leakage audit
```

必须说明：

- `D_norm_confirm` 为什么代表 calibration population；
- `D_behavior_confirm` 代表哪些攻击类别、语言和难度；
- `D_benign_confirm` 的任务类型与 harmful set 是否需要长度/格式匹配；
- semantic-near-duplicate 判定使用的模型、阈值和人工复核规则；
- 未覆盖语言/领域不能进入 generalization claim。

### 7.2 Primary decoding protocol

v3.2 默认把 confirmatory behavior decoding 固定为 deterministic greedy：

```text
do_sample = false
num_beams = 1
```

并在 Freeze B 锁定 max new tokens、EOS/stop strings、chat-template generation prompt、KV-cache、dtype/backend 和所有 generation fields。与历史 sampling artifacts 的比较只能是 descriptive，除非另有 matched replication。

若作者必须使用 stochastic sampling，则 v3.2 不能同时保留上述 greedy 默认；必须改为唯一的 sampling protocol，并增加：

- common random numbers / paired RNG seeds across estimator arms；
- decode seed 作为真实重复维度或固定测试条件；
- sampling variance进入 power model；
- clean output不得跨不同 seeds复制；
- 预算按真实 decode repetitions重算。

目标文件中不能同时留下 greedy/sampling 两套任选主分析。

### 7.3 Missing、failed 和 exclusion

Freeze A/B 必须区分：

- model generation failure；
- runner/infrastructure failure；
- span/target mapping missing；
- judge parse failure；
- policy label uncertainty；
- max-token truncation；
- genuinely empty/broken output。

技术失败不得自动当作 broken；模型产生的空输出可以按冻结 rubric 判 broken。重跑资格必须由 config hash和 failure type决定。所有 denominator、重跑和排除数量按 arm 报告。

---

## 8. P1：Judge-human validation 修订

### 8.1 正确区分 agreement 与 gold validation

删除或改写 `adjudicated Krippendorff alpha`。正确流程是：

1. 两名 human annotators 在 adjudication 前独立、盲标；
2. raw agreement 和 Krippendorff alpha 从这两份原始标签计算；
3. disagreement 由第三人 adjudication；
4. adjudicated consensus 作为 automated judge 的 validation gold；
5. macro-F1、per-class precision/recall 和 confusion matrix相对该 gold计算。

不得在 adjudication 后的共识标签上计算 inter-rater agreement。

### 8.2 抽样、权重和 CI

`D_judge_valid>=360` 只能称最低 planning total，不是自动充分的样本量。v3.2 必须：

- 在 Freeze B 前规定 model、anchor、estimator/rendering arm、domain 和 predicted class 的抽样概率；
- 对 rare unsafe/broken 可过采样，但报告 inverse-probability/prevalence-weighted总体 metrics；
- 同时报告 unweighted stratified metrics；
- CI 至少按 prompt cluster，必要时同时反映 vector和sampling weight；
- 为 broken recall、unsafe recall和每模型最低 recall规定目标 CI precision或最低 gold count；
- 若 360 无法满足，增加 human annotations，而不是把更多自动 judge outputs当作人工验证 N。

### 8.3 失败后果

保留 v3.1 的失败降级原则，但写得更明确：

- raw inter-rater alpha 不达门槛：rubric validity不足，相关主张降级并报告 ambiguity；
- automated judge 的 broken recall失败：P2-B 在人工 gold子集上重估或降级；
- unsafe recall失败：P2-U/K1 在人工 gold子集上重估或降级；
- 任一 model-specific recall失败：不得对该模型使用未经校正的自动 judge作为确认性标签；
- 不得在 `D_judge_valid` 上调 prompt 后继续称其为 held-out validation。

必须冻结 automated judge 的 model/revision、system prompt、decoding、output schema、metadata blinding 和 parse/failure rule。

---

## 9. P1：Rendering、cell reuse、attention 与 multiplicity 收尾

### 9.1 Rendering 2x2 的 support rule

保留 v3.1 的 rendering-package 2x2，但 Freeze B 必须确认 `alpha0/alpha1` 在 T0/T2 两个 package 的可运行支持内。若任一 cell 超出 screening support：

1. 只允许在 confirmation 前执行一次预注册 rendering-support rescue；
2. rescue 不进入 confirmation inference；
3. 仍不支持时，整个 2x2 降为 partial/descriptive，不得只删掉不方便的 cell；
4. 不得把 package contrast归因于单个 newline/header token。

### 9.2 Cell reuse 必须由身份 hash 决定

`mu_special_drop0` 与 `mu_all_tw` 不得仅凭名称或预期等价自动复用。只有以下字段全部相同才能去重：

```text
checkpoint/tokenizer/template/rendered IDs
prompt/vector IDs
hook/layer/phase/cache semantics
exact injected alpha after dtype conversion
generation config and RNG state
selected-token mask and computed mu when relevant
code/config hash
```

若 `mu_special_drop0 != mu_all_tw` 或 injected alpha/config 不同，必须运行独立 cell并重算预算。Same-alpha identity QA 应注入同一个预计算 alpha tensor/scalar，避免仅因浮点乘法路径不同产生假失败。

### 9.3 Attention 保持 secondary

保留 v3.1 的两步 target freeze、missing-target、position-matched keys、teacher-forced replay 和 prompt-level inference。同步补充：

- attention 结果不参与 P1/P2 Gate；
- mapping coverage failure 是有效结果，不以最高 norm/attention token替代；
- head/layer families 的校正方法在 Freeze B 唯一指定；
- 无 intervention 时始终使用 association language；
- attention null 不允许从主 artifact 中删除。

### 9.4 Secondary multiplicity 不得保留“任选”

删除 `simultaneous CI、Holm/BH-FDR or effect-size/CI only` 这种未决定表述。v3.2 默认指定：

| family | 默认处理 |
|---|---|
| P1 | 单一 one-sided test against `delta_P1_min` |
| P2-U/P2-B | two-sided Holm family |
| K1 full multinomial/profile | global model或cluster bootstrap；component CIs标 secondary |
| K2 | 一个 global model x categorical-rho test；anchor-wise simultaneous CIs |
| rendering 2x2 | 预定主 contrasts 内 Holm；interaction 单独标 key secondary |
| harmful/benign | 一个预定 domain x dose interaction/model family |
| all-layer norm | simultaneous bands |
| attention heads/layers | prompt-level主 contrast + BH-FDR；其余 effect/CI only |
| exploratory/extra-layer | effect size与CI，不作确认性显著结论 |

若采用不同方法，目标文件必须逐 family 给出唯一方法，不能留到看到 outcomes 后选择。

---

## 10. Freeze Architecture 与执行顺序

### 10.1 Freeze A 必须新增的内容

`measurement_freeze.json` 除 v3.1 已有字段外，增加：

- P1 target calibration population和50:50 stratified weighting；
- stratified prompt-cluster bootstrap算法；
- `delta_P1_min=0.10` 或唯一替代值及独立依据；
- one-sided lower-bound test；
- P1 prospective power/precision result和最终 norm N；
- dominance terminology gate；
- prompt sampling frame与dedup规则；
- primary mu aggregation 的精确伪代码或测试向量。

### 10.2 Freeze B 必须新增的内容

`behavior_freeze.json` 除 v3.1 已有字段外，增加：

- P2-U/P2-B 和 Holm procedure；
- `c_A/c_T`、support audit及两点结果措辞分支；
- GLMM中的 `model:prompt` 项；
- full/reduced/fallback trigger；
- primary decoding protocol和全部 RNG 规则；
- exact prompt source/category quotas；
- second-vector-family cross-reference或完整 protocol；
- judge raw agreement与adjudicated gold规则；
- secondary family逐项 multiplicity method；
- cell identity/dedup hash规则；
- rendering 2x2 support decision。

### 10.3 推荐执行顺序

```text
P0   archive source/manifests and complete E0
P1   define prompt sampling frames and run P1-only external power simulation
P2   write/hash Freeze A
P3   run E1 and E2 under Freeze A
P4   complete descriptive E3 remapping
P5   run independent random-family behavior screening
P6   complete second-family paper-level audit/construction/screening
P7   freeze decoding, judge, support, N, P2 family and write/hash Freeze B
P8   run mandatory P2/K1/K2, benign and required second-family confirmation
P9   run strict attention association
P10  execute one-at-a-time preregistered secondary blocks
P11  human validation and locked final analysis
```

第二 family 的算法和 construction split 必须在任何 random-family confirmation outcomes 可见前锁定。若只有 cross-reference，应在 P6 完成 hash/independence audit。

---

## 11. 预算与 Block Registry 重算要求

v3.2 不得机械保留 v3.1 的 `20,784`。必须先验证以下事实：

1. P2 仍使用既有两个 estimator x 两个 anchor cells，因此本次将 unsafe 纳入 P2 不增加 generation；
2. historical bridge 是否真的能与 all-token cell去重；
3. rendering 2x2 是否需要 rescue screening；
4. second family 是 cross-reference、单 direction还是20-direction population；
5. P1 norm sample size是否变化；
6. primary decoding是否引入多个 stochastic seeds；
7. judge-human validation N是否超过360。

预算表必须分开列出：

```text
vector-conditioned generated trajectories
vector-free clean trajectories
stochastic decode replicates, if any
unjudged same-alpha QA
non-generation teacher-forced attention trajectories
automated judged responses
human-annotated responses
norm token records/storage
```

必须给出至少两个总计：

- `paper already has qualified second family`；
- `Stage 3 must execute second family`。

Block Registry 中每个 block 必须有 split、start condition、freeze dependency、expected cells、真实统计单位、stop rule、证据等级和 failure consequence。Missing expected cell 时 aggregation 继续 non-zero exit。

---

## 12. 必须同步替换的 v3.1 表述

| v3.1 表述/设计 | v3.2 必须修改为 |
|---|---|
| calibration anomaly隐含提升攻击者能力 | evaluator-facing measurement validity；完整攻击者可补偿actual dose |
| P2只以`broken@c_T`为primary，unsafe为K1 | P2-U=`unsafe@c_A`与P2-B=`broken@c_T`组成Holm family |
| 两点证据称 operating-regime shift | 默认称 tested operating points上的joint profile；完整curve需dense evidence |
| `delta_P1_min`由历史grid间距计算 | 默认固定0.10，或正文给出唯一独立依据的替代值 |
| 点估计过MRE且CI排除0 | CI bound必须直接越过MRE，或不作MRE claim |
| cross-model GLMM无`model:prompt` | 加入model-specific prompt heterogeneity |
| P1固定200 prompts但无power | Freeze A前独立P1 power/precision |
| second family为模糊条件式 | paper-level mandatory cross-reference或完整可执行protocol |
| prompt只保存source/hash | 定义sampling frame、quota、dedup、language/category和leakage audit |
| main decoding仅写generation config | 唯一冻结greedy或sampling；默认greedy |
| `adjudicated alpha` | raw independent labels算alpha；adjudicated consensus作gold |
| 360 human labels自动充分 | 按class/model precision和gold count确定最终N |
| secondary使用Holm/BH-FDR/CI任选 | 每个family预先指定唯一方法 |
| historical/all-token cell默认复用 | 仅identity hash一致时复用，否则重算预算 |
| 约20,784为完整投稿预算 | 按second-family/decoding/dedup真实状态给分支预算 |

---

## 13. v3.2 推荐章节结构

Codex 可沿用 v3.1 的25章结构，建议调整如下：

1. Executive Summary and Claim Boundary
2. Threat Model: Adversary, Evaluator, and Security Objective
3. Historical Observations as Hypothesis-Generating Evidence
4. Hierarchical Claims and Joint Security/Integrity Endpoints
5. Steering, Actual Alpha, Rho, and Dose Geometry
6. Evidence Levels and Freeze Architecture
7. Models, Vector Families, Prompt Sampling Frames, and Independence
8. Rendering, Padding, Span Annotation, and Estimators
9. E0 Tool QA
10. E1 Historical Forensic Reconstruction
11. E2 Held-out Measurement Confirmation
12. E3 Descriptive Existing-Curve and Ranking Audit
13. E4 Strict Attention Association
14. E5 Two-Anchor Matched Protocol Confirmation
15. E6 Gate-Independent Three-Model Categorical-Dose Confirmation
16. Rendering-Package Factorial, Phase Controls, and Benign Integrity
17. Behavior Labels and Judge-Human Validation
18. P1/P2 Power, Precision, and Sample-Size Freeze
19. Statistical Analysis and Multiplicity Plan
20. Vector-Family Coverage, Gates, Budget, and Block Registry
21. Security Relevance, Generalization, and Threats to Validity
22. Artifacts, Figures, and Reproducibility
23. Allowed and Forbidden Claims
24. Freeze and Acceptance Checklist
25. Execution Priority

标题可以微调，但所有内容必须在目标文件中可找到，且不要求执行者回看本任务书。

---

## 14. 允许结论与禁止表述

### 14.1 允许

- 结构/template token selection 在冻结 Qwen calibration population 中对 `mu` 有或没有超过预设门槛的影响；
- same-`c` calibration rule 在两个预注册 operating points上改变或未改变 unsafe/broken probabilities；
- 当相应两个 contrasts均支持时，tested joint unsafe/integrity profile发生变化；
- nominal-`c` 与 actual-alpha/rho 表示下的 ranking稳定、改变或不确定；
- 三个受测模型在共同 categorical anchors 上存在或不存在 residual model-associated differences；
- random unit vectors与已审计第二 vector family的结果一致或不一致；
- rendering package、domain和frozen attention target存在或不存在预注册关联/interaction；
- null、mapping failure、rare-event uncertainty和judge failure限制相应结论。

### 14.2 禁止

- 把 calibration mismatch写成已知actual alpha攻击者的新能力；
- 只凭 broken change声称攻击成功或完整 unsafe-to-collapse regime移动；
- 把两个 anchors写成完整连续curve或精确threshold；
- 用点估计超过MRE且CI排除0声称统计上超过MRE；
- 把 random unit vectors推广到所有 activation steering；
- 在第二 family仍未定义时声称外部有效性问题已解决；
- 忽略 model-specific prompt heterogeneity后作架构固有结论；
- 把 copied clean、同seed跨模型vector或重复decode当独立样本；
- 从多个GLMM/fallback/multiplicity方法中按结果择优；
- 把 adjudicated consensus的完全一致当作inter-rater reliability；
- 未定义 sampling frame就推广到全部 harmful/benign prompts；
- 未冻结 RNG 时把 stochastic outputs当作严格paired；
- 默认复用并不完全相同的 historical/current cells；
- 由 hidden norm/attention association推出 Attention Sink导致collapse；
- 把 white-box additive hook结果推广到普通remote API威胁。

---

## 15. Codex 交付前验收清单

- [ ] v1、v2、v3、v3.1和全部已有revision briefs均未修改
- [ ] 新建`writing/paper1_attention_sink_mu_experiment_design_v3_2.md`
- [ ] v3.2可独立执行，不依赖读者回看本任务书
- [ ] Threat Model区分adversary与evaluator，并承认完整攻击者可补偿actual dose
- [ ] 贡献定位为security-evaluation validity/reproducibility
- [ ] P1 -> P2固定序贯保留
- [ ] P2-U unsafe@c_A与P2-B broken@c_T组成Holm family
- [ ] 两个P2 contrasts使用现有四个logical cells，未虚增或漏算预算
- [ ] 不再仅凭broken声称安全operating profile已确认
- [ ] 两点结果未被写成完整连续curve
- [ ] P1 target population和50:50 stratified bootstrap可执行
- [ ] `delta_P1_min`不再由历史grid spacing推导
- [ ] MRE claim使用CI bound直接越过margin
- [ ] `dominate`与`materially changes`有不同证据门槛
- [ ] P1在Freeze A前完成独立power/precision论证
- [ ] Qwen GLMM保留prompt、vector和prompt-vector pair
- [ ] cross-model GLMM加入`model:prompt`
- [ ] fallback trigger、顺序和small-cluster处理唯一
- [ ] power simulation匹配P2 Holm family和实际random-effects structure
- [ ] second vector family有合格cross-reference或完整可执行protocol
- [ ] second family缺失时不会继续作activation steering一般化结论
- [ ] deterministic direction未被伪装为20个vector clusters
- [ ] 每个prompt split有sampling frame、quota、dedup和leakage audit
- [ ] primary decoding唯一选择greedy或sampling；默认greedy已完整冻结
- [ ] 若sampling，paired seeds、decode variance和预算已同步
- [ ] technical failure与model-generated broken已区分
- [ ] raw independent human labels用于agreement/alpha
- [ ] adjudicated consensus仅作为judge validation gold
- [ ] human validation抽样权重、cluster CI、关键class gold count和失败后果明确
- [ ] rendering 2x2有共同support/rescue/downgrade规则
- [ ] cell reuse只由完整identity hash决定
- [ ] attention仍为secondary association且null/mapping failure保留
- [ ] 每个secondary family有唯一multiplicity方法
- [ ] Freeze A/B新增字段与执行顺序一致
- [ ] budget区分generation、clean、sampling replicate、attention、judge和human annotation
- [ ] 预算给出second-family cross-reference与execution两种总计
- [ ] block registry、统计计划、主图、claims和验收清单完全一致
- [ ] 所有未定实体都有冻结时点、允许输入、算法和降级规则
- [ ] Allowed/Forbidden Claims与实际识别能力一致

---

## 16. 最终交付要求

Codex 最终只需交付：

1. `writing/paper1_attention_sink_mu_experiment_design_v3_2.md`；
2. 一段简短变更摘要，至少说明如何修复：
   - 攻击者能力与evaluator-facing security contribution的错位；
   - P2 broken主终点与unsafe攻击目标的错位；
   - 单anchor不足以支持operating-profile主张；
   - practical threshold检验规则；
   - cross-model `model:prompt`缺失；
   - P1前瞻性power缺失；
   - 第二vector family不可执行；
   - prompt sampling frame和decoding随机性未冻结；
   - judge agreement/adjudication混淆；
   - secondary multiplicity、cell reuse和预算分支不明确。

除非用户另有明确要求，不修改实验代码、已有 artifacts、任何旧版设计、Paper 1其他文档或运行环境。
