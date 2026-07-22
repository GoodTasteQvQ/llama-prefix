# Paper 1 Stage 3 实验设计 v2 -> v3 迭代规格

文档用途：本文件是交给 Codex 的修改任务书，不是新的实验协议正文。  
源文件：`writing/paper1_attention_sink_mu_experiment_design_v2.md`  
参考文件：`writing/paper1_attention_sink_mu_experiment_design.md`  
目标文件：`writing/paper1_attention_sink_mu_experiment_design_v3.md`  
修改方式：保留 v1、v2 原文件不变，以 v2 为骨架新建 v3。  
目标标准：IEEE TDSC Regular Paper 的确认性实验、统计推断、可复现性和 claim boundary 标准。

---

## 1. 给 Codex 的执行指令

请完整阅读 v1、v2 和本迭代规格，然后生成一份自洽、可直接冻结执行的 v3 实验协议。不要只在 v2 末尾追加勘误，也不要保留已被本规格否定的旧矩阵或旧统计口径。

v3 必须做到：

1. 保留 v2 的 forensic-first 主线、actual-alpha 重映射、精确 rendering/padding 重建和 Gate 驱动资源分配。
2. 恢复 v1 中更严格的跨模型最低确认、crossed-design 统计模型、功效分析和 per-step dose geometry。
3. 修复 estimator 对照中“token selection、prompt aggregation、trimming 同时变化”的核心混杂。
4. 明确 discovery、screening、confirmation 三类数据的边界，并给出真正使用 held-out confirmation split 的主矩阵。
5. 将 Gate 限定为资源调度机制。Gate 可以决定是否扩展 secondary experiments，但不能决定是否报告负结果，也不能替代主假设的最低确认实验。
6. 区分三种证据强度：历史重建/描述性证据、匹配条件下的 protocol effect、模型机制因果证据。
7. 删除所有无法由 v3 实验直接支持的强结论。

不要修改代码，不要启动实验，不要虚构已有结果。v3 中尚未确定的参数必须写出冻结方法和决策规则，不能用“视结果而定”代替。

---

## 2. v3 的推荐定位

v3 的核心问题应收敛为：

> A recurrent structural-token activation outlier can distort a Rogue-style activation-norm calibration statistic, thereby changing the mapping from a nominal multiplier `c` to the actual intervention magnitude `alpha`. We test whether this implementation-sensitive rescaling explains observed shifts in attack-to-collapse operating points, and determine which parts of the phenomenon are model-specific.

该定位包含三个层级，必须分开：

1. **测量层**：结构 token 是否对某种 `mu` 估计器具有高杠杆。
2. **协议层**：由于 `alpha=c*mu`，估计器差异是否改变相同 `c` 所代表的实际剂量和行为结果。
3. **模型层**：控制 actual alpha、相对剂量和方向几何后，模型间是否仍有不同 collapse sensitivity。

Attention Sink 只作为 secondary mechanistic question。没有 attention intervention 时，最高只能使用 `attention-sink-associated structural-token outlier`，不能使用 `Attention Sink causes collapse`。

---

## 3. 必须修复的 P0 问题

### 3.1 将 estimator 拆成正交因素

当前 v1/v2 的主 estimator 对照同时改变 token selection、prompt weighting 和 trimming，无法把 `mu` 差异归因于结构 token。v3 必须把三类变化拆开。

对 prompt `p`、token `t` 的 norm 记为 `n[p,t]`。先固定两个互斥 token 集：

```text
V_p = 该 prompt 中所有 valid、non-padding、通过统一 special-token 规则的 tokens
C_p = V_p 中属于 system/user semantic content spans 的 tokens
```

confirmatory estimator 至少包含：

| ID | token selection | prompt 内聚合 | prompt 间聚合 | 用途 |
|---|---|---|---|---|
| `mu_all_tw` | `V_p` | 不先聚合 | 所有 token 等权 | all-token reference |
| `mu_content_tw` | `C_p` | 不先聚合 | 所有 token 等权 | 结构 token exclusion 主对照 |
| `mu_all_pb` | `V_p` | prompt mean | prompts 等权 | prompt weighting 对照 |
| `mu_content_pb` | `C_p` | prompt mean | prompts 等权 | selection × aggregation 分解 |
| `mu_content_trim10_pb` | `C_p` | 10% trimmed mean | prompts 等权 | robust sensitivity |
| `mu_content_median` | `C_p` | median | prompts 等权或报告 prompt distribution | appendix sensitivity |

主结构效应必须定义为同 aggregation 下的 selection contrast：

```text
delta_select_tw = (mu_all_tw - mu_content_tw) / mu_content_tw
delta_select_pb = (mu_all_pb - mu_content_pb) / mu_content_pb
```

aggregation effect 必须在同 selection 下计算：

```text
delta_agg_all = (mu_all_tw - mu_all_pb) / mu_all_pb
delta_agg_content = (mu_content_tw - mu_content_pb) / mu_content_pb
```

trimming 只能作为 robust sensitivity，不能与 structural exclusion 混成一个主因果对照。

历史 fidelity estimators 继续保留：

```text
mu_special_drop0
mu_public_absolute5
mu_valid_absolute5
mu_first5_non_special
```

但必须单独标为 `historical/protocol-fidelity estimators`。它们用于解释 `413/653/59.5`，不能替代上述 confirmatory factorial decomposition。

行为实验只允许使用预注册的两类对照：

1. **Structural-selection contrast**：`mu_all_tw` vs `mu_content_tw`。
2. **Historical protocol contrast**：`mu_special_drop0` vs `mu_first5_non_special`，两者保持相同 token-weighted aggregation。

不要让 prompt balancing 或 trimming 进入这两个行为主对照。

### 3.2 真正落实 held-out confirmation

v3 必须重写 prompt split，至少包含：

| split | 建议规模 | 用途 | 约束 |
|---|---:|---|---|
| `D_forensic` | historical 100 | 精确重建旧结果 | 保持历史顺序和内容 |
| `D_norm_confirm` | 100 harmful + 100 benign | 在 current model line 确认 recurrence、leverage、全层 profile | 不用于历史规则发现；运行前冻结 |
| `D_behavior_screen` | 30 harmful | 检查 alpha 范围、运行稳定性和方差 pilot | 不进入主效应估计 |
| `D_behavior_confirm` | 50 harmful，功效不足时按预案增加 | 冻结后的行为主检验 | 不参与 estimator/anchor 选择 |
| `D_benign_confirm` | 至少 30 benign | selected-condition integrity | 与 calibration/attention 分离 |
| `D_attention_confirm` | 32，16 harmful + 16 benign | strict attention confirmation | 与 `D_norm_confirm`、行为集完全不重叠 |

要求：

- exact 和 semantic-near-duplicate 去重覆盖所有 current splits；
- prompt category、版本、SHA256 和抽样 seed 在运行前冻结；
- 结构 token target、template-relative position、attention controls 必须从历史 forensic evidence 预先定义，不能在 `D_attention_confirm` 上重新挑选；
- `D_behavior_screen` 只能用于范围与方差估计，不得贡献 confirmatory effect estimate、p-value 或最终 CI；
- v3 必须写出 `D_behavior_confirm` 的实际矩阵，不能只在 split 表里声明它存在。

### 3.3 恢复 Gate-independent 的三模型最低确认

Qwen 可以是机制发现和主要验证模型，但 Qwen2.5、Llama3.1、Mistral 都必须完成一个最低的 cross-model dose confirmation，不受 structural-leverage Gate 控制。

三模型最低确认至少包含：

- current formal layer；
- `decode_only`；
- clean baseline；
- 至少三个冻结的非零 dose anchors，覆盖 attack、transition 和 high/collapse 邻域；
- 相同的 prompt sampling protocol 和 vector construction protocol；
- `broken/refusal/safe/unsafe`、repetition、length、EOS 和 leakage；
- actual `alpha`、dimension-normalized dose 和 token-level relative dose。

跨模型主横轴应预先定义为：

```text
rho_l = alpha_l / median_content_norm_l
```

其中 `median_content_norm_l` 只能由独立 `D_norm_confirm` 计算。共同 `rho` 网格应由历史数据的共同 support 和 screening 数据冻结，不能根据 confirmation 结果移动。

如果 Llama/Mistral 没有 structural leverage：

- 可以跳过它们的完整 estimator behavior expansion；
- 不能跳过最低 dose-confirmation；
- 只能写“structural calibration pathology 未跨模型复现”，不能写“该模型不存在 calibration sensitivity”。

### 3.4 明确 screening 和 confirmation 的行为矩阵

Qwen E5 应拆成：

1. **Range/variance screening**：使用 `D_behavior_screen`，只做 alpha 范围、安全上限和功效参数估计。
2. **Frozen confirmation**：使用 `D_behavior_confirm`，运行所有冻结的 primary contrasts。

confirmation 前必须冻结：

- estimator IDs；
- template IDs；
- vector manifest；
- dose anchors；
- primary/secondary endpoints；
- curve model和 knots；
- equivalence margins；
- sample size；
- exclusion/failure rules；
- multiple-testing families。

确认矩阵至少包括：

```text
Qwen structural-selection contrast:
  2 estimators x >=2 same-c anchors x D_behavior_confirm x vector pool

Qwen historical-protocol contrast:
  2 estimators x selected same-c anchor(s) x D_behavior_confirm x vector pool

Alpha-matched identity:
  小规模 QA；不作为独立行为实验重复完整矩阵

Template 2x2:
  T0/T1 x alpha0/alpha1 x D_behavior_confirm x vector pool
```

历史超范围 alpha 只保留小型 forensic behavior cell，不进入主确认矩阵。

### 3.5 修复统计功效和 cluster 数问题

不能把 `30 prompts x 10 vectors=300` 当作 300 个独立观测。prompt 和 vector 都是 crossed clusters。

v3 必须规定：

1. 功效模拟使用真正包含多个 prompts 和多个 vectors 的 screening/pilot；single-prompt full1000 只能估计 vector variation，不能估计 prompt variation。
2. 若要把 vector 推断推广到 vector population，confirmation 原则上至少使用 20 个独立 vector clusters；最终数量由预注册功效模拟决定。
3. 如果资源限制只能使用 10 vectors，则必须把 vectors 视为固定条件，主结论限定为该 frozen vector set，不能声称 vector-population generalization。
4. 主分析使用 crossed random-intercept logistic model 或预注册 GEE，并报告 prompt/vector two-way clustered 或 small-cluster-robust CI。
5. 模型不收敛时的 fallback 必须提前指定，例如 paired aggregation 后的 prompt bootstrap 和 vector-level sensitivity，而不是看到结果后选择方法。
6. confirmation sample size 在查看 confirmation outcomes 前冻结。
7. 如需扩样，使用预注册的 blinded sample-size re-estimation 或独立 replication batch；不要根据 effect direction、p-value 或“接近显著”继续加样。

### 3.6 恢复完整的 dose geometry

v3 应从 v1 恢复每个 steered step 的以下指标：

```text
alpha
pre_hook_l2
post_hook_l2
relative_dose_r = alpha / pre_hook_l2
norm_ratio = post_hook_l2 / pre_hook_l2
vector_alignment = cos(h, v_hat)
cosine_drift = 1 - cos(h, h + alpha*v_hat)
generated_steered_call
```

序列级可报告 mean/max relative dose 和 nominal cumulative exposure，但累计量只能作为诊断指标，不能解释为线性因果剂量。

仅按 raw alpha 或 `L2/sqrt(d)` 对齐不足以证明模型具有独立敏感性。跨模型结论必须同时考虑 relative dose、vector alignment 和 hook point。

---

## 4. actual-alpha 证据的重新分级

v3 必须把 E3/E5 的证据分成三类。

### 4.1 Existing-curve remapping：描述性/解释性

历史曲线转为 actual alpha 很重要，但不同版本可能同时改变：

- checkpoint/tokenizer/template；
- prompt/vector pool；
- hook/phase semantics；
- dtype/library version；
- vector normalization。

因此曲线在 alpha 轴上重新对齐只能写：

> The remapping is consistent with calibration-induced rescaling.

不能仅凭该分析写：

> The shift is causally or primarily explained by `mu`.

只有共同 alpha support 内的结果可以比较；不允许外推 transition 或 peak。

### 4.2 Matched protocol bridge：protocol-level causal evidence

新增一个最小 matched bridge：

- 同 checkpoint、template、prompt、vector、layer、schedule、decode config；
- 仅替换预注册 calibration rule，因此改变 `mu` 和 same-c 下的 alpha；
- 同时完成 same-c contrast 和 same-alpha identity QA。

该实验允许声称：

> The calibration rule causally changes the intervention dose associated with the same nominal multiplier and thereby shifts behavior under an otherwise matched protocol.

### 4.3 Attention/model mechanism：需要额外干预

same-alpha identity 只证明 runner/config 一致，不证明结构 token 或 Attention Sink 直接导致 collapse。没有 attention intervention 时，attention 结果保持关联性措辞。

---

## 5. Strict Attention 的修改要求

保留 v2 的 position-matched controls，并补充 v1 的 clean/steered teacher-forced comparison。

设计要求：

- `D_attention_confirm` 与 norm/behavior 数据完全不重叠；
- target token 和 template-relative position在查看该 split 前冻结；
- clean prefill；
- clean decode 前 32 steps；
- 如果论文讨论 attention 与 collapse 的关系，加入 frozen transition alpha 下的 teacher-forced steered replay；
- equal-count、position-matched nonstructural keys 为主对照；
- uniform causal-mask expectation 只作 secondary reference；
- head 不是独立样本，先在 prompt 内汇总，再以 prompt 为推断单位；
- 报告 per-head distribution、target rank、top-1 fraction、entropy 和 high-norm/attention overlap；
- eager/production logits parity 必须先通过。

若只完成观测性 attention：

```text
允许：attention-sink-associated structural-token outlier
禁止：Attention Sink causes/contributes to collapse
```

如果没有 attention enrichment，删除标题和正文中暗示 Attention Sink 已成立的措辞，将该部分改成概念排除性结果。

---

## 6. Template 2x2 的精确定义

保留 v2 的 template direct/indirect 2x2，但补充以下定义：

```text
mu0 = T0 在独立 calibration split 上的预注册 estimator
mu1 = T1 在同一独立 calibration split 上的同一 estimator
c_transition = 在查看 D_behavior_confirm 前冻结
alpha0 = c_transition * mu0
alpha1 = c_transition * mu1
```

四组继续为：

| group | template | alpha |
|---|---|---:|
| A | T0 | `alpha0` |
| B | T1 | `alpha0` |
| C | T0 | `alpha1` |
| D | T1 | `alpha1` |

必须报告：

- `B-A`：alpha0 下 template direct effect；
- `D-C`：alpha1 下 template direct effect；
- `C-A`：T0 下 dose effect；
- `D-B`：T1 下 dose effect；
- template × alpha interaction。

`D-A` 只能称为 combined contrast，不能当作 mediation effect。若要使用 causal mediation 术语，必须另行陈述 identification assumptions；默认不使用 mediation claim。

所有组必须使用同一 vector manifest。v3 还必须说明 steering vectors 的提取数据、构造、符号、归一化、层对齐和是否与 calibration/behavior prompts 独立。

---

## 7. 行为终点与 judge 修改要求

`broken_rate` 可以继续作为 primary endpoint，但 v3 必须给出可复现的操作定义和标签优先级。

至少明确：

- unsafe 且重复/乱码时如何归类；
- refusal 很短时为何不自动归为 broken；
- EOS、空输出、特殊 token 泄漏、控制字符、循环重复的判定阈值；
- 四分类是否互斥，以及冲突时的优先级；
- objective diagnostics 与 LLM judge 不一致时如何处理。

主表同时报告：

```text
unsafe / refusal / safe / broken
3-gram repetition
special-token leakage
garbled/control-character flag
generated length
EOS/stop reason
```

人工验证继续采用双人盲标和第三人 adjudication。judge prompt 修改只能在开发集上进行，最终 macro-F1、unsafe recall、broken recall 和 per-model confusion matrix 必须来自新的 held-out validation sample。

---

## 8. 曲线模型与多重检验

v3 应恢复并精确化 v1 的统计模型：

### 8.1 Collapse curve

- 主模型：binomial GEE 或 crossed random-effect logistic model；二者择一作为 primary，另一种为 sensitivity；
- dose：预注册 restricted cubic spline，knots 在 confirmation 前冻结；
- 分别拟合 raw `c`、actual `alpha`、`rho` 和 token-level relative dose；
- 报告 `c_50`、`alpha_50`、`rho_50` 及 clustered CI；
- 若测试范围内未达到 0.5，报告 `not reached within tested range`，不得外推；
- 模型特异性以 `model x dose` interaction 和阈值差为依据。

### 8.2 ASR peak

ASR 可能非单调。`c_peak/alpha_peak` 必须标为 secondary，并提前定义：

- 使用离散测试网格最大值还是冻结曲线的预测最大值；
- ties 的处理；
- bootstrap CI；
- version curve distance 的具体度量；
- equivalence/alignment margin。

不得根据图形在离散点、二次曲线和 spline 之间事后选择最有利的 peak。

### 8.3 Primary families

v3 必须把每个 family 展开为具体 contrast，而不是使用“cross-model presence/absence”一类模糊名称。建议 primary families：

1. Qwen `mu_all_tw` vs `mu_content_tw` 的 selection effect；
2. Qwen matched same-c structural-selection behavior effect；
3. historical protocol matched bridge 的 same-c behavior effect；
4. Qwen template 2x2 的两个 direct contrasts 和 interaction；
5. 三模型共同 `rho` support 上的 model × dose interaction；
6. harmful/benign collapse direction consistency。

family 内使用 Holm correction。全层、额外 estimators、attention heads 和额外 layers 属于 secondary，使用 simultaneous bands、BH-FDR 或只报告 effect size/CI。

所有 equivalence margins 必须给出数值和依据，并在 confirmation 前冻结。

---

## 9. Gate 的正确用途

v3 的 Gate 应按以下原则重写：

| Gate | 可以决定 | 不可以决定 |
|---|---|---|
| Tool validity | 是否开始正式实验 | 忽略失败 QA |
| Structural leverage | 是否扩展 estimator behavior/attention | 是否报告该模型负结果 |
| Attention enrichment | 是否做跨模型 attention 或 intervention | 是否把 hidden norm 改称 Attention Sink |
| CI precision | 是否启动预注册 replication batch | 按 p-value 临时加样 |
| Cross-model leverage | 是否增加完整 estimator matrix | 是否跳过最低 dose-confirmation |

E2 的 `ratio lower CI >1.5` 或 `top1 share >50%` 只能作为资源 Gate，不是领域通用 outlier 定义，也不能被包装成 confirmatory significance threshold。必须解释 1.5 和 50% 的来源；若无外部依据，应称为 operational expansion criteria。

---

## 10. TDSC 安全贡献与外部有效性

v3 必须新增一节“Security relevance and scope”，回答：

1. 谁会使用 `alpha=c*mu` 的 calibration protocol：攻击者、评测者还是 steering 方法开发者？
2. 该实现是否来自公开 Rogue-style protocol，还是本项目特有变体？
3. calibration drift 会改变什么安全结论：ASR 排名、attack-to-collapse transition、模型比较，还是复现实验的一致性？
4. 哪些结果只是 Qwen/template-specific implementation pathology？
5. 哪些结果能够推广到 additive unit-norm activation steering？
6. 哪些结果不能推广到其他 steering 方法、其他向量构造或所有 LLM？

主贡献不能停留在“`alpha=c*mu`，所以更大的 `mu` 产生更大的 alpha”这一数学必然关系。必须用 matched bridge 和跨模型最低确认展示该标定差异足以改变实际安全评估结论。

建议将最终贡献写成 measurement validity / reproducibility finding，而不是新防御：

> Calibration statistics used by activation-steering evaluations can be dominated by template-specific activation outliers, making nominal strength multipliers incomparable across implementations. Reporting and matching actual intervention dose changes the interpretation of attack and collapse thresholds.

---

## 11. v3 推荐章节结构

Codex 生成 v3 时建议采用以下顺序：

1. 执行摘要与 claim boundary
2. 已有历史观察：明确标为 hypothesis-generating
3. 研究问题、预注册假设和 primary endpoints
4. 术语、steering、actual alpha、relative dose 和 dose geometry
5. Historical forensic line 与 current confirmatory line
6. 模型、vectors、prompt splits 和独立性约束
7. Rendering、padding、span annotation 与工具 QA
8. Historical fidelity estimators 与 confirmatory factorial estimators
9. E0：工具正确性
10. E1：历史异常重建
11. E2：held-out structural leverage confirmation
12. E3：existing curves 的描述性 actual-alpha remapping
13. E4：strict attention confirmation
14. E5：matched protocol bridge 与 Qwen confirmatory behavior
15. E6：三模型 Gate-independent dose confirmation
16. Template 2x2、phase controls 和 benign integrity
17. 样本量、功效和统计预案
18. Gate、资源预算和停止规则
19. Artifact、图表和可复现性
20. 允许结论、禁止表述和 threats to validity
21. 最终验收清单

---

## 12. 需要从 v1 恢复的内容

从 v1 恢复并适配到 v3：

- prompt/vector crossed design；
- prompt/vector two-way inference；
- GEE 或 crossed random-effect logistic model；
- restricted cubic spline 与 threshold CI；
- per-step `pre_hook_l2/post_hook_l2/vector_alignment/cosine_drift`；
- 三模型最低行为确认；
- harmful/benign direction consistency；
- `not reached within tested range` 规则；
- objective collapse diagnostics；
- judge-human held-out validation；
- null results 和失败 runs 的完整保留。

不要恢复：

- 25,200 generations 的完整笛卡尔积；
- 三模型所有 estimators × 所有 layers × 所有 schedules；
- 在 structural leverage 为负时仍展开大规模 attention；
- 无有效 Track B 剂量依据的 `alpha=0-2` direct-effect 对照。

---

## 13. 资源预算原则

v3 不应先写死一个看似精确但没有 power basis 的总 generation 数。

预算分三层：

1. **必做非生成工作**：E0、E1、E2、全层 norm、existing-curve remapping。
2. **必做确认生成**：Qwen frozen primary contrasts、三模型最低 dose-confirmation、selected benign checks。
3. **Gate 后扩展**：跨模型 estimator behavior、额外层、跨模型 attention、attention intervention。

每个 block 必须列：

- prompts 数；
- vectors 数；
- cells 数；
- generation 上限；
- 是否进入 primary inference；
- 启动条件；
- 停止条件。

总预算应在 multi-prompt/multi-vector power simulation 后给出。若 v3 暂时无法取得 variance estimates，使用区间预算并明确 `to be frozen after blinded screening`，不要伪造精确功效。

---

## 14. v3 必须保留的 claim boundaries

允许：

- structural/template tokens 对特定 calibration estimator 具有高杠杆；
- calibration rule 改变 same-c 对应的 actual alpha；
- matched protocol 下，该剂量变化导致行为 operating point 平移；
- actual-alpha/relative-dose 重映射使历史差异缩小或仍然存在；
- structural-token activation outlier 与 attention concentration 相关或不相关；
- structural pathology 可能是 tokenizer/template/model-specific。

禁止：

- 由 hidden norm 直接推出 Attention Sink；
- 由 same-c estimator 对照推出结构 token 直接导致 collapse；
- 把 same-alpha identity QA 当成模型机制证据；
- 用历史曲线重映射单独声称 `mu` 是唯一或主要原因；
- 将 three-model observation 推广到所有 LLM；
- 在没有共同 dose support 时比较 threshold；
- 将 `0/N` 写成风险为零；
- 将 structural filtering 称为新防御；
- 将 Qwen left-padding bug 推广到使用正确 right padding 的模型；
- 将 screen 数据和 confirmation 数据合并后报告 confirmatory CI。

---

## 15. Codex 交付前验收清单

生成 v3 后，Codex 必须逐项自检：

- [ ] v1、v2 文件未被修改
- [ ] v3 是独立完整协议，不依赖读者回看本迭代规格才能执行
- [ ] historical facts 明确标为 hypothesis-generating
- [ ] historical fidelity estimators 与 confirmatory estimators 分开
- [ ] selection、aggregation、trimming 已正交拆分
- [ ] 主 structural contrast 保持相同 aggregation
- [ ] `D_behavior_confirm` 有明确矩阵且真正进入主分析
- [ ] `D_attention_confirm` 与 norm/behavior 数据不重叠
- [ ] screening 不进入 confirmatory effect estimate
- [ ] 三模型最低 dose-confirmation 不受 leverage Gate 控制
- [ ] vector construction/provenance/normalization/independence 已定义
- [ ] 功效模拟包含 prompt 和 vector 两个方差分量
- [ ] 10-vector cluster 限制已修复或明确限制推断范围
- [ ] confirmation sample size 和扩样规则不会形成 outcome-driven optional stopping
- [ ] curve model、knots、threshold 和 common support 已定义
- [ ] primary families、Holm correction 和 equivalence margins 已明确
- [ ] per-step dose geometry 已恢复
- [ ] existing-curve remapping 被标为描述性证据
- [ ] matched protocol bridge 被明确列为 protocol-level causal evidence
- [ ] Attention 结论保持关联性边界
- [ ] broken 标签定义和优先级可复现
- [ ] benign integrity 与 judge-human validation 已保留
- [ ] Gate 只用于资源调度，不用于删除负结果
- [ ] Security relevance and scope 已单列
- [ ] 预算按必做确认与 Gate 后扩展分层
- [ ] 允许/禁止结论与实际实验能力一致
- [ ] 所有 TBD 都有冻结时点和决策规则

---

## 16. 最终交付要求

Codex 最终只需交付：

1. `writing/paper1_attention_sink_mu_experiment_design_v3.md`；
2. 一段简短变更摘要，说明 v3 如何修复：
   - estimator 混杂；
   - held-out confirmation 缺失；
   - cross-model Gate 造成的外部有效性问题；
   - vector cluster 与功效问题；
   - actual-alpha 证据强度越界；
   - Attention 因果措辞越界。

除非另有明确要求，不修改实验代码、已有 artifacts、v1/v2 文档或其他 Paper 1 文件。
