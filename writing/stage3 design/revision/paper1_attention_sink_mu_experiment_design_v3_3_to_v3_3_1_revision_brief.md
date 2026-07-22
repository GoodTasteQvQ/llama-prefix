# Paper 1 Stage 3 实验设计 v3.3 -> v3.3.1 迭代规格

文档用途：本文件是交给 Codex 的修改任务书，不是新的实验协议正文。  
源文件：`writing/paper1_attention_sink_mu_experiment_design_v3_3.md`  
参考文件：`writing/paper1_attention_sink_mu_experiment_design_v3_2.md`、`writing/paper1_attention_sink_mu_experiment_design_v3_2_to_v3_3_revision_brief.md`  
目标文件：`writing/paper1_attention_sink_mu_experiment_design_v3_3_1.md`  
修改方式：保留 v1、v2、v3、v3.1、v3.2、v3.3 和全部已有 revision brief 不变；以 v3.3 为主骨架，新建一份可独立冻结和执行的 v3.3.1。  
目标标准：关闭 v3.3 中仍会阻止 protocol freeze、无歧义编码、预算审计和 TDSC confirmatory interpretation 的缺口，不扩张论文主张或实验范围。

---

## 1. 给 Codex 的执行指令

请完整阅读源文件、参考文件和本迭代规格，然后生成一份自洽、可直接进入 Freeze A/B 准备阶段的 v3.3.1 实验协议。不得在 v3.3 末尾追加勘误；必须把本规格整合进对应章节，使目标文件无需回看本 brief 或 v3.2 才能执行。

执行时必须遵守：

1. 不修改 v1、v2、v3、v3.1、v3.2、v3.3、已有 revision brief、实验代码或历史 artifacts。
2. 不运行实验、模型生成、功效模拟或 judge；不虚构数据、方差、事件率、provenance、模型路径、第二向量族资格或既有 artifacts。
3. 保留 v3.3 已正确建立的 evaluator-facing contribution、P1 -> P2 fixed sequence、pooled-token P1、P2 zero-null 与 practical-claim 分离、K2-U/K2-B、matched V2、population-average GLMM、greedy primary、fixed720 human sample lock、identity reuse 和 append-only amendment。
4. 本规格中的 P0 项必须进入主协议、Freeze schema、统计计划、预算、claims 和 acceptance checklist；不能只放入 Threats to Validity。
5. 所有未确定实体必须有唯一冻结时点、允许输入、确定性算法和失败后果。不得把“由 Freeze B 决定”当作省略算法的理由。
6. 目标协议中的公式、logical cells、P/V/N、预算和 block registry 必须彼此可机械核对。
7. 若本规格与 v3.3 冲突，以本规格为准；本规格未涉及处，保留 v3.3 中更保守、更可审计的规则。
8. 目标文件协议版本写为 `v3.3.1-proposed`。在 Freeze A/B 及本文 acceptance checklist 实际完成前，不得把状态写成 `frozen`。

Codex 交付时只创建目标文件，并给出简短变更摘要。除非用户另行要求，不实现代码、不运行测试、不修改其他文件。

---

## 2. v3.3.1 的总体定位

### 2.1 论文定位保持不变

核心贡献仍为：

```text
security-evaluation measurement validity and reproducibility
```

必须继续承认：已知 `mu` 且可自由选择 actual `alpha` 的 white-box operator 可以补偿 calibration mismatch。本文不声称发现新攻击能力；主要风险是 evaluator/reproducer 使用 nominal `c` 比较协议、模型或实现时形成不可比 actual dose、错误排序、错误安全边界或不可复现实验。

以下边界不得弱化：

- `broken` 是 integrity loss，不是 attack success；
- P2 两个 anchors 不识别完整连续 curve；
- `rho` 不是完整等效剂量；
- random family 与一个 Qwen-only prompt-domain contrastive family不代表全部 activation steering；
- stochastic block 只覆盖一个固定 sampling config；
- attention 只支持 association；
- white-box hook 不推广到 remote API。

### 2.2 本轮只关闭七类缺口

v3.3.1 不增加新的模型、layer、vector family、phase schedule、P2 anchor 或人工样本规模。本轮只完成：

1. 恢复 rendering-package 2x2 的完整可执行定义；
2. 为 V2 screening、anchor rescue、matched random reuse 和 N 指定唯一规则；
3. 将所有预算改为 P/V/N 参数化公式，删除错误 hard upper；
4. 使 Freeze A/B 成为依赖闭合、可校验的 schema；
5. 保护 P2 免受 estimator/anchor arm 差异性 judge 误分类；
6. 删除无 equivalence margin 的 stochastic `compatible/not compatible` 结论；
7. 在运行 coverage simulation 前固定 method-selection 标准。

### 2.3 论文级证据结构保持

```text
P1 Measurement primary
  -> P2 Matched protocol primary family

K1 Full outcome-profile secondary
K2-U/K2-B Cross-model unsafe/integrity interaction family
V2-U/V2-B Vector-family robustness secondary
```

P1 未通过时，P2 仍完整运行但只能 estimation-only。K2/V2 不进入 P1 -> P2 gate，但各自 multiplicity family 保持不变。

---

## 3. P0：恢复 rendering-package 2x2 的独立可执行定义

v3.3 第16.1节只保留了“T0/T2 x alpha0/alpha1形成A-D”，删除了 `mu0/mu1`、`alpha0/alpha1` 和 A-D 映射。v3.3.1 必须恢复以下完整定义，不得要求执行者回看 v3.2：

```text
T0 = T0_native_user_only
T2 = T2_controlled_no_system

mu0 = mu_all_tw estimated under T0
mu1 = mu_all_tw estimated under T2

alpha0 = c_T * mu0
alpha1 = c_T * mu1
```

四个 cells 固定为：

| cell | rendering package | injected alpha |
|---|---|---:|
| A | T0 | alpha0 |
| B | T2 | alpha0 |
| C | T0 | alpha1 |
| D | T2 | alpha1 |

必须解释：

- `B-A`：固定 `alpha0` 的 rendering-package contrast；
- `D-C`：固定 `alpha1` 的 rendering-package contrast；
- `C-A` 与 `D-B`：各 rendering 下的 dose contrast，仅作 descriptive/secondary CI；
- `package x alpha`：key-secondary interaction；
- `D-A`：combined contrast，不称 mediation、newline effect 或单 token 因果效应。

`B-A` 与 `D-C` 组成 two-sided Holm family。Freeze B 必须保存 T0/T2 rendered-message schema、template hashes、`mu0/mu1` hashes、`alpha0/alpha1` dtype 后数值、四个 cell identities、support audit 和 whole-block downgrade 状态。

保留 v3.3 的 support rescue：若四 cells 中任一 cell 在独立 screen 上不满足 technical/operational support，只允许一次 `10 prompts x 5 V_screen vectors x 4 cells = 200` rescue；仍失败则整个 2x2 降为 partial/descriptive，不能选择性删除不便的 cell。

---

## 4. P0：关闭 V2 screening、anchor 与样本量歧义

### 4.1 V2 名称和构造保持

继续使用：

```text
prompt-domain contrastive harmful-vs-benign direction family
```

不得称 compliance、refusal、behavior-informed 或 jailbreak direction。继续保留 375 eligible pairs、25 个 disjoint 15-pair partitions、5 screen directions、20 confirm directions、固定 sign 和技术 QA。`data/safe_pairs.json` provenance 不完整时必须保留 `blocked_for_paper_level_generalization`，不得虚构资格。

### 4.2 V2 anchor screening 的唯一算法

V2 initial screen 使用 random-family screening 已冻结的三个 base anchors：

```text
rho_base = {rho_A, rho_T, rho_H}
10 D_second_screen prompts
x 5 V2_screen directions
x 3 anchors
= 150 responses
```

在全部 technical-valid screen responses 上，按 prompt-direction observations 计算每个 anchor 的 `broken` marginal rate。不得按 unsafe、refusal 或期望方向选择 anchor。

唯一 rescue 决策为：

```text
if broken_rate(rho_A) > 0.50:
    rho_v2 = 0.5 * rho_base elementwise
elif broken_rate(rho_H) < 0.50:
    rho_v2 = 2.0 * rho_base elementwise
else:
    rho_v2 = rho_base
```

若第一或第二分支触发，仅允许用同一 10 prompts、同一 5 screen directions 在 `rho_v2` 上再运行一次 150-response rescue。禁止第二次缩放、midpoint 搜索、按 confirmation outcome 调整或只移动单个 anchor。

若 initial 不触发缩放，不运行 rescue，直接令 `rho_v2 = rho_base`。若 initial 触发缩放，则仅在 rescue 后三个 anchors 均有有效 denominator 且 technical support 完整时继续。最终一律冻结为中性名称，不再根据任何 behavioral outcome 或事后语义判读重命名：

```text
rho_V2_L < rho_V2_M < rho_V2_H
```

正文、图例和统计模型均只使用 categorical `L/M/H`；不得在结果后补充 attack/transition/high-collapse 标签。若 rescue 后 technical failure、nonfinite dose、有效 denominator 或顺序条件仍失败，则 V2 标记 blocked，不再搜索 anchors。

### 4.3 Matched random arm 必须使用同一最终 anchors

V2 confirm 与 matched random arm 必须共享：

- 同一 `D_second_confirm`；
- 同一 Qwen checkpoint/template/formal layer/hook；
- 同一 decode-only greedy config；
- 同一最终 `rho_V2_L/M/H`；
- 同一 judge、failure taxonomy 和 dose logging。

E6 Qwen random cells仅在以下条件全部成立时复用：

1. `rho_v2 == rho_base` 的 dtype 后实际 alpha identities 完全相同；
2. prompt 属于同一冻结 `D_second_confirm` subset；
3. random vector、rendering、generation、hook、phase、RNG、code/environment hashes 全部相同；
4. canonical cell identity SHA256 完全相同。

只要 V2 anchors 经过 `0.5x` 或 `2x` rescue，matched random arm 必须在最终 V2 anchors 上重跑，不能复用 E6 base-anchor cells。该重跑固定为：

```text
30 prompts x 20 random V_confirm directions x 3 final V2 anchors
= 1,800 responses
```

### 4.4 `D_second_confirm` 固定为 30，不再保留 50-prompt hard cap

v3.3.1 必须统一写为：

```text
D_second_confirm = 30 harmful prompts
V2_confirm = 20 directions
matched random = 20 directions
3 categorical V2 anchors
```

删除 V2 confirmation `hard cap 50 prompts`、`50x20x3=3,000` 以及任何无确定选择规则的 30 -> 50 扩样。V2 是 key secondary；若 30 prompts x 20 directions 的 precision/coverage 不足，降级为 fixed-tested-directions estimation，不扩样、不改 anchor、不升格 primary。

因此 V2 generation budget 唯一为：

```text
initial screen                     150
optional one-time rescue        0 or 150
V2 confirmation                 1,800
-------------------------------------
Stage3 V2 total              1,950 or 2,100
```

如果走 qualified cross-reference path，Stage3 新 V2 generation 为 0，但被引用 Stage 的真实成本必须在 Paper 1 总资源表中单列。

---

## 5. P0：重写参数化预算并删除错误 hard upper

### 5.1 所有主要变量

预算章节必须定义：

```text
P  = final D_behavior_confirm harmful prompt count, in {50,75,100}
V  = final random V_confirm count, in {20,25,30}
N_b = final benign prompt count, default 30
B_bridge in {0,1,2}
R_render in {0,200}
Q_alpha in [0,144]
N_V2 in {0,1950,2100}
N_V2_random_rematch in {0,1800}
N_stochastic = 1200
S_random <= 3600
```

`S_random` 是实际 random-family screening/rescue generation；表格可给 3,600 上界，但总账必须记录实际值。

### 5.2 Random-family 通用公式

必须用以下参数化公式替换只对 `P=50,V=20` 成立的常数式：

```text
N_random_generated =
    S_random
  + 9PV                  # E6 three-model categorical dose
  + 2PV                  # Qwen content-estimator additions
  + B_bridge*PV          # historical bridge new cells
  + 3PV                  # rendering A-D additions beyond reused cell
  + 3P                   # harmful clean
  + 3N_bV                # benign transition vector-conditioned
  + 3N_b                 # benign clean
  + Q_alpha              # same-alpha unjudged QA
  + R_render

N_random_automated_judged =
    N_random_generated - Q_alpha
```

当使用 screen 上界 `S_random=3600`、`Q_alpha=144` 时，可简写为：

```text
N_random_generated =
  3600 + (14+B_bridge)PV + 3P + 3N_bV + 3N_b + 144 + R_render

N_random_automated_judged =
  3600 + (14+B_bridge)PV + 3P + 3N_bV + 3N_b + R_render
```

### 5.3 v3.3.1 总公式

```text
N_v3_3_1_generated =
    N_random_generated
  + N_V2
  + N_V2_random_rematch
  + 1,200

N_v3_3_1_automated_judged =
    N_random_automated_judged
  + N_V2
  + N_V2_random_rematch
  + 1,200
```

Planning 示例可以保留，但必须明确是示例而非 hard upper：

```text
P=50, V=20, N_b=30, B_bridge=1,
S_random=3600, Q_alpha=144, R_render=0,
N_V2=1950, rematch=0

= 23,934 generated
= 23,790 automated judged
```

为证明公式覆盖最大候选 P/V，资源表还必须列出 scope-grid worst case：

```text
P=100, V=30, N_b=30, B_bridge=2,
S_random=3600, Q_alpha=144, R_render=200,
N_V2=2100, rematch=1800

= 60,134 generated
= 59,990 automated judged
```

上述数值只是在本协议候选集合下的资源上界，不是 GPU 时间或货币成本。若未来 amendment 改变 P/V/N 或新增 mandatory block，必须重新按公式计算，不能继续称 60,134 为 hard upper。

### 5.4 资源停止规则

`25,000 judged` 继续只是 optional-secondary soft cap，不是 mandatory-block hard cap。若 prospective simulation 选择更大的 P/V，必须在 Freeze B 前完成资源可行性确认；不能为了回到 25k 而删除 P2/K2、benign、qualified V2、human validation 或预注册 stochastic block。

资源表继续分列：generation、automated judge calls、vector-free clean、same-alpha unjudged QA、attention teacher-forced、construction forwards、human response items、primary annotation assignments 和 adjudication assignments。

---

## 6. P0：使 Freeze A/B schema 依赖闭合

### 6.1 通用 manifest 引用规则

Freeze 文件可以引用外部 manifest，但每个引用必须保存：

```text
relative artifact path
schema version
artifact SHA256
record count / identity count
creation timestamp
producer code/config hash
```

仅写“见 prompt manifest”或只保存 git hash 不足以闭合依赖。Freeze JSON 自身使用 canonical sorted JSON 计算 SHA256；自身 hash 字段的计算规则必须明确，避免递归自哈希歧义。推荐 hash payload 排除 `self_sha256` 字段，再写入最终字段。

### 6.2 Freeze A 必含字段

`measurement_freeze.json` 至少包含或哈希引用：

- checkpoint absolute path、revision、weight hash；
- tokenizer、chat template、rendering IDs/hash；
- formal layer、normalized depth、hook site、pre/post-hook semantics；
- dtype/backend、padding/batching 和 canonical extraction；
- `D_norm_confirm`/extension prompt-frame hashes、final per-stratum N、dedup/leakage manifest；
- `V_p/C_p`、special-token/span rules、zero-content/unresolved handling；
- pooled-token numerator/denominator、realized shares、equal-domain sensitivity test vectors；
- P1 stratified prompt bootstrap 的 exact resampling、CI type、one/two-sided quantiles、seed 和 replicates；
- `delta_P1_min=0.10`、dominance gate 和 allowed wording；
- P1 simulation-plan/artifact hash与 N-selection result；
- all-layer simultaneous-band algorithm；
- environment、code、config、timestamp 和自身 SHA256。

Freeze A 必须在任何 `D_norm_confirm` outcome 可见前生成。

### 6.3 Freeze B 必含字段

`behavior_freeze.json` 至少包含或哈希引用：

- Freeze A path/hash；
- `D_behavior_confirm`、`D_second_confirm`、`D_stochastic_robustness`、`D_benign_confirm` prompt identities/frame hashes；
- final P、V、`N_b`、random/V2 vector manifests；
- base `rho_A/T/H`、Qwen `c_A/c_T`、各模型 dtype 后 alpha、common-support audit；
- V2 initial/rescue decision、final `rho_V2_L/M/H`、matched-random reuse/rematch state；
- P2/K2/V2 endpoints、models、fallback sequence、coverage acceptance artifact；
- Holm family order、raw p-value definition、synchronized max-T CI algorithm、resample count/seed；
- population-average random-effect integration 的 draw structure、seed、minimum/maximum draws、MCSE calculation；
- rendering A-D 的 `mu0/mu1/alpha0/alpha1` 与 support/downgrade；
- greedy primary和stochastic subset/seeds/isolated RNG/sampling kwargs；
- judge model/revision/prompt/schema/parser/blinding、class priority和failure taxonomy；
- fixed720 human sampling algorithm、P2 critical-cell floor、two-phase correction和decision-consistency rule；
- attention target/query/control/missing rules；
- 每个 secondary family 的 multiplicity 或 CI-only 状态；
- complete cell-identity schema、预算公式的实际代入值、code/config/environment hash、timestamp、自身 SHA256。

Freeze B 必须在任何 behavior/attention confirmation outcome 可见前生成。它可以使用独立 screening 的 nuisance estimates和 support结果，但不能使用 confirmation outcome、human gold或未来 response identities。

### 6.4 Human-validation sample lock 保持 append-only

继续保留：

```text
human_validation_sample_freeze.json
```

它在全部 eligible formal greedy responses 与 automated predictions 生成后、任何 human gold label 可见前生成。包含 Freeze A/B hashes、eligible-universe hash、strata counts、selected identities、每 item inclusion probability、duplicate audit、seed、code/config hash、timestamp、自身 hash。

不得回写 Freeze A/B，不得根据前360个 gold labels早停或扩样。

---

## 7. P0：增加 differential judge-error protection

### 7.1 问题必须在主设计中承认

overall macro-F1、overall recall 或 per-model recall不能排除 estimator/anchor arms 之间的差异性误分类。尤其 unsafe 稀少时，两个 arms 很小的 false-positive-rate 差异即可制造或抹去 P2 RD。因此 v3.3.1 不能继续以“judge recall达标”作为 P2 自动标签有效性的唯一条件。

### 7.2 Human sample 的 P2 critical-cell floor

fixed720 总样本不变。Freeze B 的 sampling algorithm 除 predicted-class/model/anchor/arm/domain quotas 外，必须保证四个 P2 logical cells各至少抽中 30 个 validation items：

```text
(mu_all_tw, c_A)
(mu_content_tw, c_A)
(mu_all_tw, c_T)
(mu_content_tw, c_T)
```

该 floor 是 response-item count，不要求预先知道 gold class。若某 logical cell eligible items少于30，则取尽该 cell，并在 sample lock 中记录容量不足；对应 endpoint 自动触发 precision downgrade。floor 分配完成后，剩余 quota再按 v3.3 的 predicted-class oversampling和 Hamilton redistribution 分配。

### 7.3 必须报告的差异性误分类审计

对 P2-U 的 A 两 arms 和 P2-B 的 T 两 arms，分别使用 inclusion-probability weights报告：

- binary sensitivity/recall；
- specificity与 false-positive rate；
- positive predictive value；
- confusion matrix cell counts和cluster-aware CI；
- arm-to-arm sensitivity difference；
- arm-to-arm false-positive-rate difference。

overall/per-model four-class macro-F1、unsafe/broken recall 和 raw agreement仍保留，但不能替代上述 P2 arm audit。

### 7.4 两阶段 difference estimator

P2-U 和 P2-B 各增加一个预注册 human-corrected sensitivity estimate。对 endpoint `e` 和 arm `a`：

```text
p_judge_full(e,a)
  = automated-judge positive rate in the full eligible P2 arm

b_validation(e,a)
  = IPW mean over validation items in arm a of
      [y_gold(e) - y_judge(e)]

p_two_phase(e,a)
  = clip(p_judge_full(e,a) + b_validation(e,a), 0, 1)

RD_two_phase(e)
  = p_two_phase(e, all-token arm)
    - p_two_phase(e, content-token arm)
```

CI 使用 prompt-cluster weighted bootstrap，并保留 vector-aware two-way sensitivity。每个 bootstrap replicate必须同步重算 full-universe judge rate、validation residual correction和两 arms差值。不得只在 human subset 上计算未加权 RD，也不得把 response rows 当独立样本。

### 7.5 P2 final claim 的 decision-consistency gate

Automated-judge GLMM/raw RD仍是预注册主要分析；`RD_two_phase` 是 mandatory validation sensitivity。最终 confirmatory wording必须同时满足：

1. raw inter-annotator alpha和现有 judge quality thresholds达标；
2. 对应 P2 arms 的 confusion metrics可估，且没有容量/critical-gold downgrade；
3. automated primary 与 two-phase sensitivity 的方向一致；
4. 对 zero-null claim，两者的预注册 family-wise/cluster-aware CI均排除0且方向一致；
5. 对 P2-B `m_B` claim，只有 automated family-wise CI与 two-phase CI均完全越过同一 `+0.10` 或 `-0.10` 边界时，才允许 threshold wording。

若 automated primary支持而 two-phase CI不支持，结果写为 `automated-label result not robust to preregistered human-error correction`，降为 estimation，不得保留 confirmatory wording。若 human-corrected estimate因 rare gold/容量不足无法可靠计算，也降级，不以 overall recall达标替代。

K2/V2 继续至少执行 per-model/per-family confusion audit。若相关 subgroup 的 judge validation失败，则对应 key-secondary claim降级；不要求为 K2/V2 另增 human N。

### 7.6 删除含糊的“human gold子集重估”

将 v3.3 中“broken recall失败则在 human gold子集重估或降级”等措辞替换为上述唯一 two-phase correction与 downgrade 流程。禁止在结果后选择 naive human-subset RD、misclassification correction或未经校正 automated RD 中最有利者。

---

## 8. P1：删除无 margin 的 stochastic compatibility 结论

v3.3 明确默认不做 equivalence，却允许 `compatible/not compatible`，两者不一致。v3.3.1 不新增任意 equivalence margin，因此必须采用保守方案：

1. 固定 1,200-response stochastic block、prompts、vectors、seeds、common-random-number intent 和 sampling kwargs全部保留；
2. 报告 greedy RD、stochastic seed-averaged RD、`RD_stochastic - RD_greedy` 和 cluster-aware 95% CI；
3. 可描述方向是否相同、CI 区间和估计不确定性；
4. 不进行 equivalence/noninferiority test；
5. 不使用 `compatible`、`not compatible`、`equivalent`、`robust across decoders` 作为二元结论。

允许措辞示例：

```text
Under the fixed stochastic configuration, the estimated difference from
the greedy result was X, with a 95% CI of [L, U].
```

禁止措辞：

```text
greedy and stochastic decoding were compatible
decoder robustness was established
the result was decoder-independent
```

主表、Threats、Allowed/Forbidden Claims、figure caption、multiplicity table 和 acceptance checklist 必须同步删除二元 compatibility 语言。该 block 保持 CI-only，不新增 p-value family。

### 8.1 RNG 实现要求

Freeze B 必须规定每个 `(prompt_id, vector_id, decode_seed, logical_cell)` 的独立 RNG 初始化和生成顺序。若底层 sampler 无法保证跨 logical cells 消费可审计的 common random stream，只能称 paired seeds，不能声称严格 common random numbers；结果仍按 prompt/vector 聚类，seed不是独立 cluster。

---

## 9. P1：在模拟前冻结 coverage 与 primary/fallback 选择标准

### 9.1 不得留给 Freeze B 自由判断“合格”

v3.3.1 必须在正文写出以下接受标准，Freeze B 只能记录结果，不能结果后改变阈值：

```text
simulation replicates per core scenario >= 10,000
fixed master seed = 42
Monte Carlo SE for estimated FWER/coverage <= 0.005
empirical family-wise type-I error <= 0.055
empirical simultaneous 95% CI coverage >= 0.93
successful fit/inference completion rate >= 0.95
```

保守 coverage 高于 nominal 不构成失败；只设置 lower bound，不设置 upper rejection bound。

### 9.2 Core scenario 的确定性构造

P2/K2/V2 simulation plan必须在 confirmation outcomes可见前保存并哈希。允许输入仅为：

- independent behavior screening；
- external/historical artifacts；
- blinded pooled prevalence、missingness和technical failure；
- protocol-fixed effect grids。

每个 endpoint 至少覆盖：

```text
event prevalence: 0.01, 0.05, 0.10, 0.25, 0.50
effect/RD grid: 0, 0.05, 0.10, 0.15
prompt/vector/pair variance:
  zero component plus 0.5x, 1x, 2x independent-screen estimates
candidate P/V combinations from the protocol
null and direction-reversed scenarios
```

Variance multiplier产生 nonfinite 或不可识别参数时，按预先记录的数值 cap截断；cap必须在 simulation-plan artifact 中先写明。不得只模拟最有利 prevalence/ICC。

### 9.3 Primary/fallback 的固定选择顺序

对 P2、K2、V2 分别执行：

1. 评估 full GLMM + synchronized max-T procedure；
2. 若其在全部 core null scenarios满足 FWER/coverage/completion标准，Freeze B 将其定为 model-based primary，raw/multiway estimates为 mandatory sensitivity；
3. 若不满足，评估预注册 pair-level prompt/vector 或 prompt/direction Webb multiway bootstrap；
4. 只有 Webb procedure满足相同 FWER/coverage标准时，才将其定为 primary；
5. 两者均失败时，该 family在 Freeze B 中预先降为 estimation-only/fixed-tested-conditions；不得在 confirmation 后按 p-value切换方法。

GLMM singular时的 deterministic reduced-model顺序保持 v3.3：先删除 highest-order pair intercept，保留 prompt/model:prompt/model:vector 或对应 P2/V2 主 random effects。不得新增结果驱动的 optimizer/model search。

### 9.4 max-T CI 必须可编码

Freeze B 必须指定：

- family 成员与固定顺序；
- synchronized resampling unit；
- studentized statistic和零方差处理；
- max-absolute-T quantile；
- two-sided CI inversion方法；
- bootstrap/parametric replicate数与seed；
- failed replicate处理和最大允许失败比例；
- Holm p-value与max-T CI可能不完全等价时的报告规则。

不得只写“Holm/max-T”而不提供以上实现字段。

---

## 10. P1：补充 threshold rationale，但不升级主张

v3.3.1 应在 P1/P2 claim-language 附近增加简短、预实验的解释：

- `delta_P1_min=0.10` 是 protocol-specific reproducibility threshold，表示 same-`c` actual alpha 至少发生10%相对改变；不是自然定律或通用安全阈值；
- `m_B=0.10` 是 protocol-specific absolute-RD claim threshold，用于区分“检测到非零 broken difference”和“足以改变评估解释的大幅 integrity difference”；不是通用风险容忍度；
- 两者均不得由本数据重新标定；
- 可报告其他阈值下的 descriptive sensitivity，但不得更换 confirmatory gate。

不为 P2-U 新增 practical margin，不恢复 `material security impact` 语言。

---

## 11. 必须同步修改的章节

Codex 可保留 v3.3 的25章结构，但必须逐章同步：

| v3.3章节 | v3.3.1必须同步的内容 |
|---|---|
| 1 Executive Summary | 不声称当前已frozen；保持claim boundary |
| 2 Threat Model | judge differential error属于evaluator风险 |
| 4 Claims | P2 final claim受two-phase validation gate约束 |
| 6 Freeze | 闭合Freeze A/B依赖和human sample lock |
| 7 Models/Vectors/Prompts | V2 base/rescue/final anchors、固定N=30、rematch规则 |
| 8 Rendering/Estimators | 如需引用T0/T2，保持定义一致 |
| 9 E0 | rendering A-D fixtures、two-phase estimator fixtures、RNG identity QA |
| 14 E5/P2 | automated primary + mandatory two-phase sensitivity与decision gate |
| 16 Secondary | 完整A-D；V2 anchor算法；删除stochastic二元compatibility |
| 17 Labels/Validation | critical-cell floor、arm-specific confusion、two-phase correction |
| 18 Power | 固定simulation acceptance；V2不再30->50扩样 |
| 19 Statistics | primary/fallback选择顺序、max-T实现字段、two-phase bootstrap |
| 20 Budget | P/V/N参数化公式、60,134 scope-grid example、删除28,284 hard upper |
| 21 Threats | judge differential error、rendering多因素、layer非等价、资源上界 |
| 22 Artifacts/Figures | 增加simulation-plan、arm confusion、two-phase RD artifacts |
| 23 Claims | 删除compatible/not compatible；增加human-correction downgrade措辞 |
| 24 Checklist | 加入本 brief 全部验收项 |
| 25 Priority | Freeze schema与simulation plan先于confirmation generation |

任何定义不能只修改一个位置。例如删除 V2 hard cap 后，prompt split、power、budget、block registry、priority 和 checklist 中的 50-prompt文字必须全部删除。

---

## 12. Threats to Validity 必须恢复或新增的内容

v3.3 压缩时遗漏了一些 v3.2 已正确承认的限制。v3.3.1 的 Threats 至少包含：

- historical environment/checkpoint可能无法精确恢复；
- pooled-token primary受domain token-length composition影响；
- model-specific formal layer/normalized depth不是架构等价层；
- rendering package同时改变多个模板因素，2x2不识别单 newline 因果效应；
- automated judge可能产生model/arm/anchor differential error；
- two-phase correction仍受720-item样本与rare gold限制；
- V2 candidate provenance可能阻断；
- V2 prompt contrast不等于behavior/refusal/compliance direction；
- 20 directions和20-30 random clusters限制population inference；
- three anchors不识别连续 curve；
- `rho`不完全控制alignment、relative dose和token geometry；
- greedy加一个sampling config不证明decoder independence；
- teacher-forced attention只支持association；
- prospective P/V选择可将mandatory资源提高到约60k级别；
- identity mismatch会增加实际预算。

---

## 13. Allowed and Forbidden Claims 修订

### 13.1 继续允许

- equal-prompt-stratum、pooled-token functional中的selection effect是否越过0.10；
- P2在两个tested points检测到或未检测到unsafe/broken difference；
- P2-B automated与two-phase intervals是否共同越过`m_B`；
- K2-U/K2-B在冻结模型/anchors上的interaction estimates；
- V2 与 matched random protocol在同一Qwen prompts/anchors上的difference estimates；
- fixed stochastic config相对greedy的difference-of-RD estimate与CI；
- null、rare-event uncertainty、judge correction failure、V2 qualification failure和resource downgrade。

### 13.2 新增禁止

- rendering A-D 未定义完整即声称2x2可执行；
- V2 rescue 后仍复用不同 actual-alpha identity 的 E6 random cells；
- 按V2 behavior outcome反复移动或单独移动anchors；
- 将30-prompt V2无规则扩到50；
- 将 `P=50,V=20` planning常数称整个协议hard upper；
- 仅凭overall recall/macro-F1排除P2差异性误分类；
- automated primary与two-phase sensitivity冲突时保留confirmatory wording；
- 只在human subset上计算未加权RD并替代预注册分析；
- 没有equivalence margin却声称greedy/stochastic compatible或not compatible；
- sampler只共享seed但无法审计随机流时声称严格common random numbers；
- 在看到coverage结果后改变coverage/FWER阈值；
- 根据confirmation p-value选择GLMM、wild bootstrap或prompt-only bootstrap；
- Freeze文件引用未哈希、无版本或无record count的外部manifest。

---

## 14. E0 与实现前 QA 新增项

v3.3.1 的 E0 至少新增：

| QA | fixture | pass rule |
|---|---|---|
| rendering A-D | synthetic `mu0 != mu1` | package/alpha mapping与四cell identity完全匹配手算 |
| V2 anchor decision | low-broken/high-broken/neutral fixtures | 仅触发0.5x、2x或keep中的唯一分支 |
| V2 reuse | base与rescued alpha fixtures | rescued anchors绝不误复用E6 identity |
| budget | planning与scope-grid worst-case | 分别得到23,934/23,790和60,134/59,990 |
| Freeze hash | canonical JSON fixture | external dependencies与self-hash规则可复现 |
| human floor | sparse/empty strata | 四P2 cells floor与Hamilton redistribution确定性 |
| two-phase RD | hand-computed weighted sample | arm correction、clip、RD和bootstrap inputs匹配手算 |
| differential error | asymmetric confusion fixture | 能检测相同overall recall但不同arm FPR |
| stochastic RNG | repeated isolated seeds | 同identity重复完全一致；cell identity改变RNG identity |
| max-T | small synthetic family | Holm order、max-T quantile与CI inversion匹配reference |

这些 QA 失败时阻止对应 Freeze；不得只记录 warning 后继续正式 generation。

---

## 15. Codex 交付前验收清单

- [ ] v1、v2、v3、v3.1、v3.2、v3.3和已有revision briefs均未修改
- [ ] 新建`writing/paper1_attention_sink_mu_experiment_design_v3_3_1.md`
- [ ] 协议版本为`v3.3.1-proposed`，未虚假标记frozen
- [ ] v3.3.1可独立执行，不依赖回看v3.2或本brief
- [ ] contribution和P1->P2 fixed sequence未扩大
- [ ] rendering `mu0/mu1/alpha0/alpha1`与A-D完整定义
- [ ] B-A/D-C Holm、dose contrasts和interaction地位一致
- [ ] V2 initial screen与0.5x/2x/keep算法唯一
- [ ] V2最多一次rescue且不根据unsafe结果选择
- [ ] V2 final anchors使用L/M/H中性名称
- [ ] V2和matched random使用同一final anchors
- [ ] rescued anchors不复用E6 base identities
- [ ] `D_second_confirm`固定30并删除50-prompt hard cap
- [ ] V2 total固定为1,950或2,100；rematch另计1,800
- [ ] random和总预算均使用P/V/N参数化公式
- [ ] planning示例23,934/23,790计算正确
- [ ] scope-grid示例60,134/59,990计算正确
- [ ] 删除28,284作为全协议hard upper的表述
- [ ] 25k只称optional soft cap
- [ ] Freeze A含model/template/hook/span/P1/dependency hashes
- [ ] Freeze B含final P/V/N、anchors、models、multiplicity、budget和dependency hashes
- [ ] Freeze JSON self-hash规则无递归歧义
- [ ] human sample lock仍在predictions后、gold前append-only生成
- [ ] fixed720中四P2 logical cells各有30-item floor或容量downgrade
- [ ] P2报告arm-specific sensitivity、specificity、FPR和PPV
- [ ] two-phase difference estimator公式和cluster bootstrap完整
- [ ] automated与two-phase decision-consistency gate进入Claims/Checklist
- [ ] 删除含糊的“human subset重估或降级”自由选择
- [ ] stochastic固定1,200且仍为CI-only
- [ ] Allowed Claims和结果结论中不再使用compatible/not compatible/equivalence二元判定
- [ ] RNG只能在可审计时称common random numbers
- [ ] simulation replicates、seed、MCSE、FWER、coverage、completion阈值已固定
- [ ] core scenario构造不依赖confirmation outcomes
- [ ] GLMM/Webb/estimation-only选择顺序唯一
- [ ] max-T family、statistic、quantile、failure handling可编码
- [ ] P1与P2-B 0.10阈值有protocol-specific rationale但未被普遍化
- [ ] Threats恢复historical/layer/rendering限制并增加judge differential error
- [ ] E0包含rendering、V2 decision、budget、two-phase和max-T fixtures
- [ ] block registry、主图、statistics、claims、budget和N完全一致
- [ ] V2 provenance不足时保留blocked状态，不虚构资格
- [ ] 所有未定实体有freeze input、算法和失败后果

---

## 16. 最终交付要求

Codex 最终只需交付：

1. `writing/paper1_attention_sink_mu_experiment_design_v3_3_1.md`；
2. 一段简短变更摘要，至少说明如何修复：
   - rendering 2x2 定义丢失；
   - V2 rescue、matched anchors和30/50歧义；
   - P/V变化下预算hard upper错误；
   - Freeze A/B依赖不闭合；
   - automated judge的arm-specific differential error；
   - stochastic compatibility无margin；
   - coverage/fallback标准未预先冻结。

除非用户另有明确要求，不修改实验代码、任何旧版设计、已有 artifacts、Paper 1其他文档或运行环境，不运行构建、测试、模型、judge或模拟。
