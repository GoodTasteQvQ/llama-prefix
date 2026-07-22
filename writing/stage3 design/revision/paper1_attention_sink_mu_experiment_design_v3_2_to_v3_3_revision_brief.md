# Paper 1 Stage 3 实验设计 v3.2 -> v3.3 迭代规格

文档用途：本文件是交给 Codex 的修改任务书，不是新的实验协议正文。  
源文件：`writing/paper1_attention_sink_mu_experiment_design_v3_2.md`  
参考文件：`writing/paper1_attention_sink_mu_experiment_design_v3_1_to_v3_2_revision_brief.md`、`writing/paper1_tdsc_readiness_audit.md`  
目标文件：`writing/paper1_attention_sink_mu_experiment_design_v3_3.md`  
修改方式：保留 v1、v2、v3、v3.1、v3.2 和全部已有 revision brief 不变；以 v3.2 为骨架，新建一份可独立冻结和执行的 v3.3。  
目标标准：IEEE TDSC Regular Paper 对 estimand、security relevance、confirmatory inference、vector-family validity、judge validation、复现性和 claim boundary 的要求。

---

## 1. 给 Codex 的执行指令

请完整阅读源文件、参考文件和本迭代规格，然后生成一份自洽、可直接冻结执行的 v3.3 实验协议。不得在 v3.2 末尾追加补丁或勘误；必须把本规格整合进执行摘要、P1/P2/K2、vector-family protocol、decoding、judge validation、功效分析、统计计划、预算、主图、允许结论和验收清单等对应章节。

执行时必须遵守：

1. 不修改 v1、v2、v3、v3.1、v3.2、已有 revision brief、实验代码或历史 artifacts。
2. 不运行实验、不启动模型生成、不虚构数据集、功效、方差、事件率、judge 性能、provenance 或已有第二向量族。
3. 保留 v3.2 已正确建立的 evaluator-facing contribution、P1 -> P2 fixed sequence、Freeze A/B、categorical dose、vector-free clean、dose geometry、identity hash、failure taxonomy、attention association boundary 和 append-only amendment；本规格另增加一个不改写 A/B 的 human-validation sample lock。
4. 本规格中的 P0 修改必须真正进入主设计；不能只在 Threats to Validity 中承认问题。
5. 所有统计检验必须有唯一 endpoint、estimand、抽样单位、模型或 bootstrap、multiplicity family、功效目标和失败降级。
6. 所有尚未确定的实体必须有唯一冻结时点、允许输入、确定性算法和失败后果；禁止“根据结果选择最佳方法”。
7. 统计模型、功效模拟、block registry、预算、主图、claims 和验收清单必须使用同一组 endpoints、anchors、N 和证据等级。
8. 若本规格与 v3.2 冲突，以本规格为准；若本规格未涉及，保留 v3.2 中更保守、更可审计的规则。
9. 目标协议必须独立可读。执行者不应为了理解 v3.3 的关键算法而回看本任务书。

Codex 交付时只创建目标文件并给出简短变更摘要。除非用户另行要求，不实现代码、不运行测试、不修改其他文档。

---

## 2. v3.3 的总体定位与优先级

### 2.1 保持不变的论文定位

v3.3 继续将核心贡献定位为：

```text
security-evaluation measurement validity and reproducibility
```

必须继续承认：已知 `mu` 且可自由选择 actual `alpha` 的完整 white-box operator 可以补偿 calibration mismatch。本研究不声称发现新的攻击能力，而是审计 nominal-`c` evaluation 如何产生不可比剂量、错误排序、错误安全边界或不可复现实验。

不得弱化以下边界：

- `broken` 是 integrity loss，不是 attack success；
- 两个 P2 anchors 不识别完整连续 curve；
- `rho` 不是完全等效剂量；
- attention 只支持 association；
- white-box hook 不推广到 remote API；
- random family 和一个 Qwen-only contrastive family不能代表所有 activation steering。

### 2.2 本轮迭代目标

v3.3 不追求继续扩张实验矩阵，而是关闭 v3.2 的六个方法学缺口：

1. 统一所谓“50:50 calibration population”与 pooled-token estimand；
2. 区分 P2 的 difference-from-zero inference、practical-claim threshold 和功效目标；
3. 为 K2 指定唯一、无歧义的 unsafe/broken multiplicity family；
4. 使第二 vector family 的名称、数据资格、matched comparison 和统计模型真正可执行；
5. 增加一个有界的 stochastic-decoding robustness block，避免把 greedy 结果默认为 decoder-independent；
6. 修正 human validation 的顺序停止和 annotation 成本口径。

### 2.3 论文级确认链

保留：

```text
P1 Measurement primary
  -> P2 Matched protocol primary family

K1 Full outcome-profile secondary
K2 Cross-model unsafe/integrity interaction family
V2 Vector-family robustness secondary
```

其中：

- `P1` 仍是 Qwen frozen formal layer 上的 `delta_select_tw`；
- `P2-U` 仍是 `unsafe@c_A`；
- `P2-B` 仍是 `broken@c_T`；
- `P2-U/P2-B` 仍构成 two-sided Holm family；
- `K2` 改为明确定义的 `K2-U/K2-B` 两成员 Holm family；
- 第二 family 的跨 family 结果记为 `V2-U/V2-B`，不与 P1/P2 并列为 primary。

---

## 3. P0：统一 P1 target protocol 与 pooled-token estimand

### 3.1 删除不精确的“50:50 token mixture”含义

v3.2 同时声称：

```text
50:50 harmful/benign prompt-stratified mixture
```

以及：

```text
all selected tokens equal weight
```

当 harmful 与 benign prompts 的 token 长度不同，pooled-token estimator 中两个 domain 的实际权重不等于 0.5/0.5。因此 v3.3 不得再把 P1 primary 简写为“50:50 calibration population”而不说明权重层级。

v3.3 必须改称：

```text
equal-prompt-stratum calibration sampling protocol
with a pooled-token primary functional
```

准确含义是：harmful/benign 各抽取相同数量 prompts，但 primary `mu_*_tw` 对抽中 corpus 的所有 selected tokens 等权。50:50 只描述 prompt allocation，不描述 token contribution。

### 3.2 保留 primary estimator，但写出精确公式

为保持与历史 calibration rule、E2 和 P2 的兼容性，v3.3 保留 pooled-token primary：

```text
mu_g_tw =
  sum_s sum_p_in_s sum_t_in_g(p) norm[p,t]
  ------------------------------------------------
  sum_s sum_p_in_s |g(p)|

g in {V, C}

delta_select_tw = (mu_all_tw - mu_content_tw) / mu_content_tw
```

其中 `s` 为 harmful/benign stratum。必须明确：每个 stratum 对 numerator/denominator 的贡献由实际 selected-token count 决定。

同时报告 realized token shares：

```text
w_g,s = total selected tokens from stratum s under token set g
        / total selected tokens under token set g
```

至少报告 `w_V,harmful`、`w_V,benign`、`w_C,harmful` 和 `w_C,benign`，使读者可以判断长度构成对 pooled estimator 的影响。

### 3.3 增加 equal-domain sensitivity，不替换 primary

v3.3 增加一个预注册 secondary sensitivity：

```text
mu_g_tw_equal_domain =
  0.5 * mu_g_tw_harmful + 0.5 * mu_g_tw_benign

delta_select_tw_equal_domain =
  (mu_all_tw_equal_domain - mu_content_tw_equal_domain)
  / mu_content_tw_equal_domain
```

该 sensitivity 回答“若 domain-level token means 等权，结论是否改变”。不得在看到结果后将它升级为 primary，也不得把 prompt-balanced estimator与 equal-domain token estimator混为一谈。

### 3.4 Bootstrap 必须匹配上述 functional

P1 primary bootstrap 保持 stratified prompt-cluster bootstrap：

1. harmful 与 benign strata 内分别按 prompt 有放回抽取冻结数量；
2. 每个 replicate 拼接抽中的 token records；
3. 从 numerator/count 重新计算 pooled-token `mu_all_tw`、`mu_content_tw` 和 `delta_select_tw`；
4. 不先计算 prompt ratios 再平均；
5. 同一 replicate 另外计算 realized token shares 和 equal-domain sensitivity；
6. token、layer和position不是独立抽样单位。

P1 检验仍为：

```text
H0: delta_select_tw <= 0.10
H1: delta_select_tw >  0.10
```

one-sided 95% lower bound 必须直接超过 0.10。equal-domain sensitivity只报告 effect/CI，不进入 P1 gate。

### 3.5 必须同步修改的位置

Codex 必须同步修改：

- Executive Summary 中的 P1 简称；
- P1 target population/estimand；
- Freeze A 字段；
- prompt sampling frame；
- estimator 表；
- P1 bootstrap pseudocode；
- power simulation；
- main figures/tables；
- generalization/threats；
- allowed/forbidden claims；
- acceptance checklist。

---

## 4. P0：对齐 P2 检验、实质语言与功效设计

### 4.1 明确两个不同的证据问题

v3.3 必须区分：

1. **difference-from-zero inference**：tested point 上是否检测到 estimator-induced outcome difference；
2. **practical-effect claim**：CI 是否足以排除小于预定阈值的效应。

P2 confirmatory family 保持：

```text
P2-U: H0 RD_unsafe_A = 0
P2-B: H0 RD_broken_T = 0
```

两个 two-sided tests 用 Holm 控制 FWER `0.05`，并报告 synchronized max-T family-wise CIs。P2 family 的显著性功效必须对应这两个 zero-null tests，不能把它描述成“证明超过 practical threshold 的功效”。

### 4.2 重新命名 P2-B 的 0.10

将 v3.2 的模糊 `practical margin` 改称：

```text
m_B = 0.10 absolute RD practical-claim threshold
```

解释规则：

- Holm 支持、但 family-wise CI 仍包含 `[-0.10, 0.10]` 中的值：只称 detected nonzero difference；
- family-wise CI lower bound `>0.10`：可称 positive broken-rate effect exceeded the preregistered practical-claim threshold；
- family-wise CI upper bound `<-0.10`：可称 negative effect exceeded the threshold in the opposite direction；
- point estimate `>=0.10` 且 CI排除0仍不足以作 exceed-threshold claim。

不得称 `m_B` 为领域通用安全阈值。

### 4.3 P2-U 不虚构无依据的 margin

P2-U 默认仍不设置任意 practical margin。必须报告：

```text
absolute RD
risk ratio when estimable
arm-specific unsafe probabilities
Holm/max-T CI
cluster-aware upper CI for rare events
```

若 P2-U 仅统计显著但效应很小，只允许写：

```text
a difference was detected at the tested attack-neighborhood point
```

不得仅凭任意小的显著 RD 写 `material security impact`。若作者未来希望对 P2-U 作 practical-threshold claim，必须在 Freeze B 前另给唯一 `m_U`、独立安全依据和对应功效；v3.3 默认不增加该阈值。

### 4.4 功效模拟必须拆成 detection 与 claim probability

P2/K2 simulation 中必须分别报告：

#### A. Confirmatory detection operating characteristics

```text
P2-B: Holm rejection probability at true RD in {0.05, 0.10, 0.15}
P2-U: Holm rejection probability and expected CI half-width
       at true RD in {0.05, 0.10, 0.15}
```

保持 v3.2 的最低选择目标：P2-B 在 true RD=0.10 时，对 zero-null 的 Holm family power `>=0.80`。必须明确它是 detection power，不是“证明 RD>0.10”的功效。

#### B. Practical-claim probability

对 P2-B 另外模拟：

```text
Pr(family-wise lower CI > 0.10)
at true RD in {0.10, 0.15, 0.20, 0.25}
```

这组结果用于说明设计对 exceed-threshold claim 的能力。不得要求 true RD=0.10 时有80%概率让 lower CI 超过0.10，因为该目标在边界点上定义错误。

P2-U 继续以 expected adjusted-CI half-width `<=0.05` 为 planning precision 目标；若 rare unsafe 使该目标在最大 P/V 下仍不满足，P2-U 必须在 Freeze B 标为 precision-limited/estimation-only。

### 4.5 联合 profile 的措辞

结果分支保持，但增加 `materially` 限制：

| 结果 | 允许措辞 |
|---|---|
| P2-U/P2-B均Holm支持且方向为正 | changed the tested joint unsafe/integrity profile at two preregistered points |
| 上述条件成立且P2-B CI越过`m_B` | broken component exceeded the preregistered practical-claim threshold |
| 只有P2-U支持 | changed unsafe probability at the tested attack-neighborhood point |
| 只有P2-B支持 | changed collapse probability at the tested transition point |
| 显著但方向相反 | changed the tested component in the opposite direction |
| 均不支持 | no confirmatory difference detected within tested support；报告compatible range |

默认不得写 `materially altered joint security profile`，因为 P2-U 没有预注册 practical threshold。

---

## 5. P0：消除 K2 endpoint 与 multiplicity 歧义

### 5.1 将 K2 明确定义为两成员 family

删除所有含糊的：

```text
one global model x categorical-rho test
```

改为：

```text
K2-U: global model x categorical_rho interaction for unsafe
K2-B: global model x categorical_rho interaction for broken
```

`K2-U/K2-B` 构成一个 two-sided Holm family，family-wise alpha `0.05`。K2 是 key secondary，不进入 P1->P2 gate，但不得用两个未校正的 global tests 冒充一个检验。

### 5.2 模型结构

unsafe 与 broken 分别拟合 v3.2 的 cross-model model：

```text
logit P(y=1) = model_id * categorical_rho
               + (1 | prompt_id)
               + (1 | model_id:prompt_id)
               + (1 | model_id:vector_id)
               + (1 | model_id:prompt_id:vector_id)
```

其中：

- `K2-U` 的 `y=unsafe`；
- `K2-B` 的 `y=broken`；
- 相同 semantic prompt保留 shared prompt effect和model-specific prompt effect；
- vector ID继续 nested within model；
- pair effect表示同一model/prompt/vector跨anchors重复。

GLMM fallback trigger/order、Webb wild bootstrap 和 fixed-tested-vector downgrade 保持 v3.2 的确定性规则。

### 5.3 Anchor-wise contrasts 与四分类

只有在对应 endpoint 的 global test之外，才报告：

- endpoint-specific anchor-wise model contrasts；
- endpoint内 max-T simultaneous CIs；
- full four-class multinomial profile作为 K1/K2 descriptive complement。

不得把 multinomial descriptive profile误写成 K2 confirmatory global test。broken threshold bracket仍只属于 K2-B/integrity描述；unsafe不使用`rho_50`术语。

### 5.4 功效与主图同步

Power simulation 必须分别给出 K2-U/K2-B 在预定 interaction scenarios 下的 power或最小可识别范围，并反映Holm。若功效不足，K2保持 estimation language。

主图、统计表、Freeze B、multiplicity table、allowed claims 和 checklist 中都必须出现 `K2-U/K2-B`，不能在其他章节又退回单一 K2 test。

---

## 6. P0：补全第二 vector family 的资格与 matched comparison

### 6.1 数据资格仍是硬阻塞条件

保留 v3.2 的二选一：

1. qualified cross-reference path；
2. Stage 3 construction/execution path。

对于 Stage 3 path，`data/safe_pairs.json` 在缺少以下字段时只能称 candidate pool：

```text
source and version
license
retrieval date
pair provenance
harm/benign taxonomy
pairing rationale
normalization and dedup manifest
cross-split leakage audit
```

任一关键字段缺失、eligible pairs少于构造要求或无法形成20个valid confirm directions时，Freeze B 必须写：

```text
blocked_for_paper_level_generalization
```

不得通过降低manifest要求或使用confirm outcomes补选pairs来解除阻塞。

### 6.2 修正 family 名称和因果含义

v3.2 的默认构造基于 harmful-vs-harmless **prompt activations**，不是基于真实 refusal/compliance response states。因此 v3.3 统一称其为：

```text
prompt-domain contrastive harmful-vs-benign direction family
```

除非实际构造改为同一 harmful prompt 的 behavior-labeled response-state contrast，否则不得称：

- compliance direction；
- refusal direction；
- behavior-informed attack direction；
- jailbreak direction。

保留几何构造：

```text
z_i_harm = z_l(harmful_i)
z_i_benign = z_l(benign_i)
d_i = z_i_harm - z_i_benign
r_j = mean_i(d_i)
v_j = -r_j / ||r_j||_2
```

负号只表示朝 construction representation 中的 benign-prompt side 注入。projection sign check是几何QA，不证明该方向会增加compliance、unsafe或safe behavior。

### 6.3 冻结 matched cross-family comparison

V2 confirmation 必须与 random family 使用相同：

- Qwen checkpoint/template/formal layer/hook；
- decode-only semantics与generation config；
- `rho_A/rho_T/rho_H` 三个anchors；
- `D_second_confirm=30` prompts；
- 四分类judge/rubric；
- dose geometry和failure rules。

Random comparison arm必须使用：

```text
the same frozen 20 random V_confirm directions
restricted to D_second_confirm
```

这些 random responses 原则上从 E6 Qwen cells 按identity hash复用。若hash不一致则按真实cell重跑并更新预算。不得将 random family 的50-prompt estimates直接与 V2 的30-prompt estimates比较而称 matched family effect。

两个family各20 directions。random direction ID和contrastive direction ID没有一一几何配对；统计中 direction必须 nested within family。

### 6.4 V2 endpoints、模型和 multiplicity

定义：

```text
V2-U: global family x categorical_anchor interaction for unsafe
V2-B: global family x categorical_anchor interaction for broken
```

`V2-U/V2-B` 使用 Holm，属于一个 key-secondary family。full multinomial profile和component CIs为secondary complement。

默认模型：

```text
logit P(y=1) = family * categorical_anchor
               + (1 | prompt_id)
               + (1 | family:direction_id)
               + (1 | prompt_id:family:direction_id)
```

其中 `y` 分别为unsafe或broken。必须明确：

- direction IDs nested within family；
- random与contrastive directions不伪装成paired direction IDs；
- shared prompt形成跨family matched prompt support；
- prompt-direction pair跨anchors重复；
- 少于30 directions/family时使用Webb-weight wild cluster sensitivity；
- coverage不足时只对fixed tested directions作结论。

fallback 顺序与 P2/K2 一致：先删除最高阶 pair intercept，再做 prompt/direction multiway wild bootstrap，最后prompt-level marginal bootstrap。不得按p-value选择模型。

### 6.5 V2 power/precision 与结论范围

Freeze B 前必须模拟 V2-U/V2-B 在 planning `30 prompts x20 directions x3 anchors` 下的 interaction precision、singularity和cluster coverage。该模拟默认用于判断可识别范围，不强制把 V2 升为 confirmatory primary。

允许结论仅为：

```text
the tested random and prompt-domain contrastive direction-generation
protocols showed compatible/different unsafe-integrity profiles
within the frozen Qwen support
```

即使 V2 与 random family一致，也不能推广到所有contrastive vectors、所有activation-steering directions或其他模型。

---

## 7. P1：明确 GLMM marginal standardization 的目标

### 7.1 P2 estimand 与 raw paired estimate

P2 的主estimand继续是冻结 prompt/vector target frame 上的 marginal RD。每个contrast必须同时报告直接paired empirical RD：

```text
RD_raw = mean_over_frozen_prompt_vector_pairs(
           y_all_token - y_content_token
         )
```

raw estimate的cluster CI由同步prompt/vector two-way bootstrap或wild bootstrap得到。它用于透明展示，不替代预注册GLMM主推断。

### 7.2 GLMM standardization 不得留下两种解释

v3.3 必须明确 primary model-based RD 是 population-average marginal contrast，不是某个“平均cluster”的conditional logit contrast，也不是任意使用empirical-Bayes random effects的平均。

默认算法：

1. 拟合冻结GLMM；
2. 对每个anchor和estimator arm保留相同fixed design；
3. 从拟合的prompt、vector、pair random-effect分布联合Monte Carlo抽样；
4. 在同一Monte Carlo draw内，对两个estimator counterfactual使用相同random-effect draw；
5. 将 inverse-logit probabilities 对random effects和冻结target frame平均；
6. 两arm相减得到marginal RD；
7. Monte Carlo seed、draw count和误差容忍度在Freeze B锁定；默认至少10,000 draws、seed42；
8. max-T parametric bootstrap每次重拟合模型并重复完整standardization。

若该算法在simulation中coverage不合格，必须在Freeze B预先降级为pair-level multiway bootstrap primary；不得在结果可见后根据p-value切换。

### 7.3 K2/V2 同步

K2和V2若报告model-based marginal probabilities/RDs，必须使用同一随机效应积分原则。不得在P2积分random effects、K2却设为0、V2又使用BLUPs而仍称结果可比较。

---

## 8. P1：增加有界 stochastic-decoding robustness

### 8.1 Primary greedy 保持不变

所有 P1/P2/K1/K2/V2 confirmatory behavior 仍唯一采用 v3.2 的 greedy512 protocol。不得将 stochastic outputs并入 primary estimates、anchors、power nuisance或judge-validation prevalence。

### 8.2 新增固定最小块

为检验 P2 结论是否完全依赖 greedy decoding，v3.3 增加一个 Qwen-only key-secondary block：

```text
2 estimators
x 2 P2 anchors
x 20 prompts
x 5 random V_confirm vectors
x 3 paired decode seeds
= 1,200 generated/judged responses
```

确定性subset规则：

- `D_stochastic_robustness`：从 `D_behavior_confirm` 按相同harm-category quota、seed42在outcomes前抽20 prompts；
- `V_stochastic_robustness`：对 `V_confirm` identity SHA256排序后取前5个；
- decode seeds固定为 `{101, 202, 303}`；
- 四个logical cells对同一prompt/vector/seed使用common random numbers。

唯一 sampling config：

```text
do_sample = true
temperature = 0.7
top_p = 0.9
top_k kwarg omitted
num_beams = 1
max_new_tokens = 512
use_cache = true
custom stop strings = none
```

模型特定EOS/PAD/template字段与greedy primary相同。若backend不能保证seed repeatability，E0失败并阻止该secondary block，不影响已冻结greedy primary身份，但必须报告`stochastic_backend_not_reproducible`。

### 8.3 统计单位与解释

三个seeds是同一prompt/vector intervention的repeated decode conditions，不是新的prompt或vector clusters。报告：

- seed-specific四分类与objective diagnostics；
- 先在prompt/vector内对seeds平均后的P2-U/P2-B RD；
- prompt/vector two-way bootstrap；
- greedy vs stochastic effect compatibility CI；
- 不作新的confirmatory p-value family。

允许结论只限于该Qwen、两个anchors、random-vector subset和固定sampling config。即使结果一致，也不能声称decoder-independent。

---

## 9. P1：修正 human validation 的样本与成本定义

### 9.1 删除 gold-dependent 自动扩样

v3.2 的 `360 -> 每轮60 -> 最多720` 规则根据观察到的gold counts和CI决定是否继续，普通Wilson/bootstrap区间未处理该顺序停止。v3.3 默认改为固定：

```text
N_human_items = 720 response items
```

在任何human gold label可见前，通过第10.3节的独立 sample lock 一次性冻结全部720个identity和inclusion probabilities。不得在360条gold结果可见后提前停止并继续使用普通固定样本CI。360可以作为内部进度点，但不能作正式stop rule。

若资源上无法承受720，必须在Freeze B前把固定N改成一个唯一更小值，并预先降级per-model critical-class precision claim；不得恢复gold-dependent optional stopping。

### 9.2 抽样与权重

保留 v3.2 的 predicted-class oversampling、model/anchor/arm/domain分层和inverse-probability weighting。Freeze B必须在任何behavior confirmation outcome可见前固定抽样算法；正式responses与locked automated predictions生成后，必须在抽取human labels前由该算法确定并锁定：

- target quotas；
- stratum inclusion probabilities；
- identity-hash抽样顺序；
- empty stratum redistribution；
- prompt-cluster weighted bootstrap；
- vector-aware sensitivity；
- duplicate-response prohibition。

unsafe/broken gold不足50 overall或每模型不足15时，不再自动扩样；直接按冻结规则降级对应claim。

### 9.3 区分 response items 与 annotation assignments

所有预算和文字统一使用：

```text
N_human_items = number of sampled model responses
N_primary_annotation_assignments = 2 * N_human_items
N_adjudication_assignments = number of raw disagreements sent to third annotator
N_total_annotation_assignments =
  2 * N_human_items + N_adjudication_assignments
```

因此默认至少有：

```text
720 human items
1,440 primary annotation assignments
+ adjudication assignments
```

不得再把“360-720 human annotations”写成总人工工作量。

### 9.4 Agreement、gold和失败后果保持

继续要求：

1. 两名annotators独立盲标；
2. raw labels计算nominal Krippendorff alpha；
3. 第三人只裁决disagreements；
4. adjudicated consensus作为judge gold；
5. judge metrics相对gold计算；
6. 不计算`adjudicated alpha`；
7. broken/unsafe/model-specific recall失败时按endpoint/model降级或在human gold子集重估。

---

## 10. Freeze Architecture 与执行顺序修订

### 10.1 Freeze A 新增字段

Freeze A 必须增加：

- equal-prompt-stratum / pooled-token target wording；
- pooled-token exact formulas；
- realized domain token-share reporting；
- equal-domain sensitivity公式；
- bootstrap中primary与sensitivity的重算伪代码；
- P1 power artifact是否匹配pooled-token functional。

### 10.2 Freeze B 新增字段

Freeze B 必须增加：

- P2 detection vs practical-claim language；
- `m_B=0.10`的确切地位；
- P2 practical-claim probability simulation；
- `K2-U/K2-B` Holm family；
- V2 qualified dataset/manifest hash或block status；
- prompt-domain contrastive family名称和claim boundary；
- V2 matched random subset、model、fallback和power artifact；
- GLMM random-effect integration algorithm/seed/draws；
- stochastic robustness prompt/vector manifests、seeds和sampling config；
- fixed `N_human_items=720`、strata/quotas、identity-hash抽样算法、空stratum重分配和weight/CI算法；
- annotation assignment预算字段。

Freeze B不能包含尚未生成的response identities、predicted classes或实际inclusion probabilities，也不能在behavior outcomes可见后回写这些字段。

### 10.3 Human-validation sample lock

新增append-only：

```text
human_validation_sample_freeze.json
```

时间：全部候选正式responses和locked automated-judge predictions已经生成，但任何human gold label均不可见时。该文件必须由Freeze B中预定的算法确定性生成，并包含：

- Freeze A/B hashes；
- eligible response identity universe/hash；
- locked predicted classes与judge/config hash；
- model/anchor/arm/domain/predicted-class strata counts；
- 720个selected response identities；
- 每个item的selection stratum与inclusion probability；
- duplicate/eligibility audit；
- sampling seed、code/config hash、timestamp与自身SHA256。

该sample lock不得修改P1/P2/K1/K2/V2分析，也不得依据human labels回写。若eligible universe不足720，按Freeze B预定的容量重分配算法取尽全部eligible items并在任何human label前锁定实际N，同时预先触发相应precision downgrade。

### 10.4 推荐执行顺序

v3.3 推荐顺序：

```text
P0  archive source/manifests + E0
P1  define prompt frames + pooled-token P1 external power
P2  write/hash Freeze A
P3  E1/E2 under Freeze A
P4  E3 descriptive remap/ranking
P5  random-family independent screening
P6  qualify/build/screen prompt-domain contrastive family
P7  simulate P2/K2/V2 + freeze marginalization/sampling/human plan
P8  write/hash Freeze B
P9  P2/K1 + E6 K2 + benign + V2 confirmation
P10 stochastic-decoding robustness
P11 strict attention association
P12 lock automated predictions + write/hash human-validation sample lock
P13 fixed-720 human annotation + locked validation analysis
P14 optional preregistered secondary blocks
```

Stochastic robustness、attention和optional blocks不得延迟或挤占P1/P2/K2/V2及human validation。

---

## 11. 预算与 Block Registry 重算

### 11.1 不改变 generation 的修改

以下修改只增加离线统计或文档工作，不新增generation：

- pooled-token target澄清与equal-domain sensitivity；
- P2 practical-claim simulation；
- K2-U/K2-B multiplicity修正；
- GLMM marginalization明确化；
- fixed human sampling本身。

### 11.2 Stochastic block 增量

默认新增：

```text
N_stochastic_generated = 1,200
N_stochastic_automated_judged = 1,200
```

这些是sampling repetitions，必须与greedy primary trajectories分列，不能并入P2/K2的P/V样本量。

### 11.3 第二family matched random arm

V2 matched random arm原则上复用E6 Qwen在`D_second_confirm`上的已有20 directions x3 anchors：

```text
identity match: 0 new random-family trajectories
identity mismatch: 30 x 20 x 3 = 1,800 new trajectories
```

预算必须显示真实复用状态。不得默认写0而不检查hash。

### 11.4 默认预算公式

保留 v3.2：

```text
N_random_generated = 19,784 + B_bridge*1,000 + R_render
N_random_judged    = 19,640 + B_bridge*1,000 + R_render
```

v3.3 加入：

```text
N_v3_3_generated =
  N_random_generated
  + N_second_family_generated
  + N_second_family_random_rematch
  + 1,200 stochastic robustness

N_v3_3_automated_judged =
  N_random_judged
  + N_second_family_judged
  + N_second_family_random_rematch
  + 1,200 stochastic robustness
```

identity-success、无render rescue、bridge planning=1时：

```text
cross-reference path:
  21,984 generated / 21,840 automated judged

Stage3 second-family path:
  add the actual 1,950..2,100 second-family branch
  => 23,934..24,084 generated
     23,790..23,940 automated judged
```

若V2 random arm identity mismatch，再增加1,800。若P/V/N、bridge、render rescue或V2 hard cap变化，必须按公式重算，不能机械引用上述planning numbers。

### 11.5 Human与其他资源单列

资源表必须分列：

```text
greedy vector-conditioned generation
vector-free clean
stochastic sampled generation
same-alpha unjudged QA
attention teacher-forced trajectories
V2 construction activation forwards
automated judge calls
human response items = 720
primary annotation assignments = 1,440
adjudication assignments = observed disagreements
norm token records/storage
```

Block Registry 中每个block必须有split、freeze dependency、expected cells、统计单位、stop rule、证据等级、failure consequence和是否允许identity reuse。

---

## 12. 必须同步修改的 v3.2 章节

Codex 可保留25章结构，但必须逐章检查：

| v3.2章节 | v3.3必须同步的内容 |
|---|---|
| 1 Executive Summary | P1 target措辞、K2两成员family、V2准确名称、greedy边界 |
| 2 Threat Model | 保持evaluator-facing定位；不扩大攻击者能力 |
| 4 Claims/Endpoints | pooled-token estimand、P2两层证据、K2-U/B |
| 6 Freeze | 新增Freeze A/B字段和human-validation sample lock |
| 7 Models/Vectors/Prompts | V2资格、名称、matched random subset |
| 8 Estimators | primary pooled-token、token shares、equal-domain sensitivity |
| 9 E0 | stochastic seed repeatability与V2 fixtures |
| 11 E2/P1 | bootstrap和reporting更新 |
| 14 E5/P2 | detection/practical language、marginalization算法 |
| 15 E6/K2 | K2-U/K2-B Holm family |
| 16 Secondary controls | 增加stochastic robustness小节 |
| 17 Labels/Validation | fixed720、items/assignments、无顺序停止 |
| 18 Power | detection vs practical probability、K2/V2模拟 |
| 19 Statistics | P2 standardization、K2/V2 families/fallback |
| 20 Budget/Registry | stochastic、V2 rematch、human assignment公式 |
| 21 Threats | pooled-token composition、greedy/sampling边界、V2 prompt-domain含义 |
| 22 Artifacts/Figures | 新增token shares、stochastic和V2 matched artifacts |
| 23 Claims | 删除不再允许的旧措辞 |
| 24 Checklist | 增加本规格全部验收项 |
| 25 Priority | submission-critical证据优先于optional扩展 |

任何一个核心定义不能只在一个章节更新。例如，K2改成两成员family后，Executive Summary、Freeze B、power、statistics、figures、claims和checklist必须全部一致。

---

## 13. 必须替换的 v3.2 表述

| v3.2表述/设计 | v3.3必须修改为 |
|---|---|
| `50:50 calibration population`且tokens等权 | equal-prompt-stratum sampling + pooled-token primary；报告realized token shares |
| P2-B `practical margin=0.10`但power只针对zero-null | `m_B`为claim threshold；分开报告detection power与CI越过阈值概率 |
| P2-U显著即可暗示material security effect | 只称tested-point difference；默认无material threshold |
| `one global model x rho test` | K2-U/K2-B两个global tests组成Holm family |
| second family称behavior-informed/compliance direction | prompt-domain contrastive harmful-vs-benign family |
| random50 prompts与V2 30 prompts可直接比较 | 两family都限制到同一`D_second_confirm`做matched comparison |
| direction ID跨family可视为对应 | direction nested within family，无几何配对 |
| GLMM marginal standardization未说明random effects | 冻结population-average integration算法、seed、draws |
| greedy结果只在Threats中限制 | 增加1,200-response stochastic robustness block |
| human validation按gold/CI逐轮扩到720 | human gold可见前一次冻结720 items |
| `360-720 human annotations` | 720 response items、1,440 primary assignments、另计adjudication |

---

## 14. 允许结论与禁止表述

### 14.1 允许

- equal-prompt-stratum sampled、pooled-token calibration functional中的selection effect超过或未超过0.10；
- pooled-token primary与equal-domain sensitivity一致或不一致；
- P2在两个预注册points检测到或未检测到unsafe/broken differences；
- P2-B family-wise CI是否越过`m_B=0.10` claim threshold；
- 三模型的unsafe和broken model×rho interactions分别存在或不存在；
- tested random与prompt-domain contrastive direction protocols在同一Qwen prompt/anchor support上结果一致或不同；
- greedy与固定stochastic sensitivity结果compatible或不compatible；
- null、rare-event uncertainty、V2 qualification failure、judge failure或decoder dependence限制结论。

### 14.2 禁止

- 将equal prompt counts称为equal token/domain contribution；
- 用point estimate超过0.10且CI排除0声称真实RD超过0.10；
- 把P2 zero-null power写成practical-threshold power；
- P2-U没有预冻margin却写`material security impact`；
- 对unsafe和broken各跑未校正K2 test后仍称一个global test；
- 把prompt-domain contrastive vector称为已验证的compliance/refusal/jailbreak direction；
- 用不同prompt sets直接比较random与V2 family；
- 把跨family direction IDs伪装成paired vectors；
- 在不同block中任意混用conditional、fixed-effect-only和marginal GLMM predictions；
- 把三个decode seeds当作三个独立prompt/vector clusters；
- 把720 items写成720次总人工标注；
- 依据前360个gold outcomes早停并继续使用普通固定样本CI；
- 由greedy和单一sampling config一致推出decoder-independent；
- V2 provenance未资格化却声称解决外部有效性；
- 扩大v3.2已禁止的attention、black-box、curve、architecture或attack-success因果表述。

---

## 15. Codex 交付前验收清单

- [ ] v1、v2、v3、v3.1、v3.2和全部已有revision briefs均未修改
- [ ] 新建`writing/paper1_attention_sink_mu_experiment_design_v3_3.md`
- [ ] v3.3可独立执行，不依赖读者回看本任务书
- [ ] contribution仍定位为evaluation validity/reproducibility
- [ ] P1->P2 fixed sequence保持
- [ ] P1不再含糊称50:50 token/domain mixture
- [ ] equal-prompt-stratum sampling与pooled-token functional写明
- [ ] pooled-token numerator/denominator和realized token shares可计算
- [ ] equal-domain sensitivity已定义且未升级为primary
- [ ] P1 bootstrap从token records重算全部functional
- [ ] P1 lower CI直接越过0.10规则保持
- [ ] P2 zero-null inference与practical-claim threshold明确分开
- [ ] `m_B=0.10`只用于claim strength，不冒充领域通用阈值
- [ ] P2 power标明是zero-null detection power
- [ ] P2-B另报告CI越过0.10的claim probability
- [ ] P2-U没有无依据的practical margin或material wording
- [ ] K2-U/K2-B构成唯一Holm family
- [ ] K2模型、power、figures、claims和checklist全部同步
- [ ] V2 candidate data有完整provenance/license/taxonomy/leakage规则
- [ ] V2统一称prompt-domain contrastive family
- [ ] V2几何sign未被解释为behavior causal direction
- [ ] random与V2使用同一30 prompts/anchors做matched comparison
- [ ] V2 random subset仅在identity hash一致时复用
- [ ] direction nested within family且未伪装成跨family paired
- [ ] V2-U/V2-B模型、Holm、fallback和power/precision已定义
- [ ] GLMM population-average marginalization算法唯一
- [ ] random effects在counterfactual arms中使用同一draw
- [ ] raw paired RD与model-based marginal RD均报告且地位明确
- [ ] primary confirmatory decoding仍唯一为greedy512
- [ ] stochastic robustness固定为1,200 responses
- [ ] stochastic prompt/vector subset、seeds和sampling kwargs唯一
- [ ] decode seeds未被当作独立prompt/vector样本
- [ ] Freeze B只冻结human sampling算法，不虚构尚未生成的identities/probabilities
- [ ] human-validation sample lock在automated predictions后、human gold前固定720 items
- [ ] sample lock含eligible universe、strata、identity、probability和hash
- [ ] predicted-class oversampling、weights和cluster CI保持
- [ ] 无gold-dependent 360->720 optional stopping
- [ ] human items、primary assignments和adjudications分开预算
- [ ] judge agreement、adjudicated gold和失败后果保持正确
- [ ] Freeze A/B字段覆盖本规格全部新增规则
- [ ] budget含stochastic、V2 rematch和human assignment公式
- [ ] block registry、统计计划、主图、claims与数字一致
- [ ] 所有未定实体都有冻结时点、输入、算法和降级规则
- [ ] Allowed/Forbidden Claims与实际识别能力一致

---

## 16. 最终交付要求

Codex 最终只需交付：

1. `writing/paper1_attention_sink_mu_experiment_design_v3_3.md`；
2. 一段简短变更摘要，至少说明如何修复：
   - 50:50 prompt allocation与pooled-token weighting的混淆；
   - P2 detection、practical threshold与power的错位；
   - K2 unsafe/broken endpoint family不明确；
   - 第二vector family的错误命名、资格阻塞和unmatched comparison；
   - GLMM marginal standardization含义不唯一；
   - greedy-only decoder外推；
   - human validation顺序停止与annotation成本误计；
   - 相关Freeze、预算、主图、claims和checklist不同步。

除非用户另有明确要求，不修改实验代码、已有artifacts、任何旧版设计、Paper 1其他文档或运行环境。
