# Paper 1 Stage 3 实验设计 v3.3.1 -> v3.3.2 迭代规格

文档用途：本文件是交给 Codex 的修改任务书，不是新的实验协议正文。  
源文件：`writing/paper1_attention_sink_mu_experiment_design_v3_3_1.md`  
参考文件：`writing/paper1_attention_sink_mu_experiment_design_v3_3.md`、`writing/paper1_attention_sink_mu_experiment_design_v3_3_to_v3_3_1_revision_brief.md`  
目标文件：`writing/paper1_attention_sink_mu_experiment_design_v3_3_2.md`  
修改方式：保留 v1、v2、v3、v3.1、v3.2、v3.3、v3.3.1 和全部已有 revision brief 不变；以 v3.3.1 为主骨架，新建一份可独立进入 Freeze A/B 准备阶段的 v3.3.2。  
目标标准：关闭 v3.3.1 中仍会阻止 protocol freeze、唯一编码、统计判定、two-phase 可识别性和完整资源审计的缺口；不增加模型、layer、anchor 数、vector family、formal confirmation 样本或人工样本规模。

---

## 1. 给 Codex 的执行指令

请完整阅读源文件、参考文件和本迭代规格，然后生成一份自洽、可独立执行、内部引用正确的 v3.3.2 实验协议。不得在 v3.3.1 末尾追加勘误；必须把本规格整合进对应章节，使目标文件无需回看旧版或本 brief 即可理解所有冻结输入、算法、判定和失败后果。

执行时必须遵守：

1. 不修改任何旧版设计、已有 revision brief、实验代码、配置、数据或历史 artifacts。
2. 不运行实验、模型生成、judge、human annotation、功效模拟、构建或测试。
3. 不虚构 checkpoint path、anchor 数值、screening outcome、方差、相关系数估计、事件率、provenance、judge 表现、human gold 或 simulation result。
4. 保留 v3.3.1 已正确建立的 contribution boundary、P1 -> P2 fixed sequence、pooled-token P1、P2 zero-null 与 practical threshold 分离、K2/V2 Holm families、greedy primary、fixed720 human sample、append-only freeze、identity reuse、rendering 2x2、V2 one-rescue 和 stochastic CI-only 定位。
5. 本 brief 中的 P0 项必须同时进入正文定义、Freeze schema、power/statistics、预算、block registry、claims、artifacts 和 acceptance checklist；不能只写入 Threats to Validity。
6. 所有仍需由 pre-confirmation artifact 提供的值，必须写出 artifact schema、生成时点、允许输入、验证规则和缺失时的阻断后果。不得把“由 Freeze B 决定”当作省略算法的理由。
7. 本 brief 给出的伪代码、阈值、顺序和 downgrade 是唯一规则。不得增加第二套可选算法或让执行者人工择优。
8. 若本 brief 与 v3.3.1 冲突，以本 brief 为准；未涉及处保留 v3.3.1 中更保守、更可审计的规则。
9. 目标文件版本写为 `v3.3.2-proposed`。在 Freeze A、Freeze B、human sample lock 和目标文件 acceptance checklist 实际完成前，不得标记 `frozen`。

Codex 交付时只创建目标文件并给出简短变更摘要。除非用户另行明确要求，不实现代码、不创建 Freeze JSON、不运行任何命令型验证、不修改其他文件。

---

## 2. v3.3.2 的定位与非目标

### 2.1 论文定位保持不变

核心贡献仍为：

```text
security-evaluation measurement validity and reproducibility
```

不得升级为新攻击能力、通用 activation-steering 安全定律、attention causal mechanism、完整 dose-response curve、decoder independence 或 remote black-box 结论。

### 2.2 本轮只关闭七类缺口

v3.3.2 只完成：

1. 把 base `rho_A/rho_T/rho_H` 改为有 manifest、无 outcome-driven 搜索的外部设计输入；
2. 固定 P2/K2/V2 simulation data-generating process 和 final `P/V` 选择函数；
3. 固定 GLMM/Webb implementation manifest、Holm raw p 和 max-T/claim 冲突处理；
4. 使 fixed720 sampling 对 P2 two-phase correction 满足 positivity、可计算 inclusion probability 和最小 cluster support；
5. 把 two-phase estimator、bootstrap 和 weight-degeneracy downgrade 写成唯一算法；
6. 补齐 V2 blocked partial paths、technical retry 与实际调用预算；
7. 修复失效的第17.7节引用，并冻结 threshold sensitivity 的报告网格。

不新增 confirmation prompts、vectors、models、anchors、human items 或 optional secondary。为删除未定义的 base-anchor 搜索自由度，本轮将 random-family screening logical matrix 固定为原有三模型 x 三 anchors，不再保留未定义的 Qwen extra-range/midpoint branch。

---

## 3. P0：base anchors 必须来自预先哈希的设计输入

### 3.1 新增 `base_anchor_manifest.json`

v3.3.1 使用“random-family screening 已冻结的三个 base anchors”，但没有给出 Stage3 内的唯一生成算法。v3.3.2 不得让 Codex invent 数值，也不得用 behavior screen 搜索数值。必须新增一个在任何 `D_behavior_screen` output 可见前创建和哈希的设计输入：

```text
protocol/base_anchor_manifest.json
```

该 manifest 至少包含：

```text
schema_version
created_at
created_before_behavior_screen = true
source_artifact_paths
source_artifact_schema_versions
source_artifact_sha256
source_record_counts
conversion_formula_version
rho_A
rho_T
rho_H
units = normalized_intervention_magnitude
strict_order_check
model_support_target = [Qwen, Llama, Mistral]
producer_code_hash
producer_config_hash
self_sha256
```

唯一合法性条件为：

```text
finite(rho_A, rho_T, rho_H)
0 < rho_A < rho_T < rho_H
all source artifacts predate D_behavior_screen
no source field contains confirmation outcomes or human gold
all referenced artifacts pass the dependency-closed hash rule
```

若 manifest 缺失、引用不闭合、数值非 finite、顺序不严格或来源包含 Stage3 confirmation outcomes，则 Freeze B 阻断。Codex 不得补造默认值。

### 3.2 A/T/H 是预注册 endpoint identifiers，不是 screen 后发现的自然语义

正文必须明确：

- `A` 是 P2-U 使用的预注册较低 operating-point identifier；
- `T` 是 P2-B 使用的预注册中间 operating-point identifier；
- `H` 是预注册较高 operating-point identifier；
- 名称不证明 A 是 unsafe optimum、T 是真实 transition point、H 是 collapse threshold；
- 三点只作 categorical levels，不识别连续 threshold。

图表可以同时显示中性 `L/M/H`，但为保持 P2 identity，`c_A/c_T` 变量名可以继续使用。任何 `attack-neighborhood`、`transition-neighborhood` 或 `collapse-neighborhood` 措辞都必须加 `preregistered tested-point identifier` 限定，不能写成数据识别出的机制位置。

### 3.3 Random-family screen 只估计 nuisance 和检查 support

random-family screening logical matrix固定为：

```text
3 models
x 3 predeclared base anchors
x 30 D_behavior_screen prompts
x 10 V_screen random directions
= 2,700 logical responses
```

删除 v3.3.1 中未定义的 `Qwen extra range最多3cells=900`、`midpoint rescue` 及其任何同义表述。screening 不得移动、替换、重命名或重新排序 base anchors，也不得根据 unsafe/broken/refusal rate选择 anchor。

每个 model-anchor cell 的 common-support pass 只检查：

```text
post-dtype alpha finite
hook/layer/config identity complete
retained logical-cell completion rate >= 0.95
all retained calls have finite logged dose geometry
no unresolved denominator or identity collision
```

行为率只可作为 independent nuisance estimate 输入 simulation plan，不参与 anchor keep/move 决策。任一 required model-anchor cell support 不通过时：

- 不运行额外 anchor search；
- P2 若其 Qwen A/T cells不通过则 estimation-only 或 blocked；
- K2 common-support interaction降为 estimation-only；
- 保留实际 screen data 和失败原因。

### 3.4 Freeze B 必须保存的 anchor 状态

Freeze B 至少保存：

```text
base_anchor_manifest path/schema/hash
rho_A/rho_T/rho_H exact decimal and binary/dtype values
per-model alpha values after dtype conversion
per-cell support denominators and completion rates
support pass/fail flags
P2/K2 downgrade decisions
```

---

## 4. P0：固定 simulation data-generating process

### 4.1 新增两个 pre-confirmation artifacts

在任何 P2/K2/V2 confirmation outcome 可见前生成并哈希：

```text
simulation_plan.json
statistics_backend_manifest.json
```

`simulation_plan.json` 保存 scenario union、nuisance inputs、data-generating parameters、candidate ordering、seed derivation和 acceptance rules。`statistics_backend_manifest.json` 保存实际统计实现，不得只写 environment hash。

### 4.2 Binary endpoint generator

P2/K2/V2 的 unsafe 与 broken operating-characteristic simulation 使用与各自分析公式一致的 crossed-random-intercept logistic generator。对 endpoint `e`、row `i`：

```text
eta_ei = X_i beta_e
       + u_e,prompt[i]
       + v_e,vector_or_direction[i]
       + w_e,pair[i]

Pr(Y_ei = 1 | random effects) = logistic(eta_ei)
```

随机效应规则固定为：

```text
u, v, w are zero-mean Gaussian random intercepts
variance components come only from independent screening
0x, 0.5x, 1x, 2x multiply variance, not standard deviation
the same cluster draw is reused across paired counterfactual arms
components absent from a family are omitted, not replaced
```

固定 intercept/effect 必须通过 deterministic bisection 校准，使对冻结 target frame 和随机效应积分后的 marginal arm probabilities达到目标：

```text
p_content = clip(q - d/2, 1e-6, 1-1e-6)
p_all     = clip(q + d/2, 1e-6, 1-1e-6)
```

Bisection 使用 tolerance `1e-8`、maximum 200 iterations。未收敛 scenario 标记 generator failure，不得换 solver；该 scenario 触发相应 method/candidate failure。

### 4.3 两 endpoint 的相关结构

为评估 synchronized Holm/max-T family，unsafe 与 broken endpoint 的同类 prompt/vector/pair random effects使用固定相关系数：

```text
kappa in {-0.5, 0.0, +0.5}
```

主 N-screen 和 prevalence/effect scenarios使用 `kappa=0`。另增加有限 correlation-stress set：在 `q=0.10`、`d in {0,+0.10,-0.10}`、全部 variance components=`1x` 时运行 `kappa=-0.5` 和 `+0.5`。条件 Bernoulli draws独立；该 generator仅用于 binary-endpoint operating characteristics，不声称复现完整四分类语义。

### 4.4 Missingness 与 technical failure

每个 family 使用 independent screen 得到的 blinded pooled technical-failure rate `f_screen`。simulation固定运行：

```text
failure_rate in {0, f_screen}
```

failure 在 simulation 中按预注册 MCAR row mask生成；不允许使用 arm-specific confirmation failure rate。若 screen 没有可估 denominator，则 `f_screen=missing`，simulation plan失败并阻止 Freeze B，而不是默认为0。分析必须使用与正式协议相同的 denominator、rerun/exclusion和 completion 判定。

### 4.5 Core scenario union 保持有限

保留 v3.3.1 的 finite union，但改写为机械可生成：

```text
prevalence q = {0.01,0.05,0.10,0.25,0.50}
signed RD d = {0,+/-0.05,+/-0.10,+/-0.15}
variance multiplier = {0,0.5,1,2}
candidate P/V = {50,75,100} x {20,25,30}
```

Scenario union 固定为：

1. `N-screen set`：全部9个 P/V candidates；`q={0.01,0.10,0.50}`、`d={0,+/-0.10}`、variance=`1x`、`kappa=0`、failure `{0,f_screen}`。
2. `prevalence/effect set`：在 selected P/V 上运行5个 q与7个 d的完整交叉；variance=`1x`、`kappa=0`。
3. `variance-stress set`：selected P/V、`q=0.10`、`d={0,+/-0.10}`；一次只将一个 component改为`0/0.5x/2x`，其他为`1x`，再加 all-components=`0.5x/2x`。
4. `correlation-stress set`：按第4.3节固定集合。
5. `failure-stress set`：selected P/V、`q=0.10`、`d={0,+/-0.10}`、variance=`1x`、`kappa=0`、failure=`f_screen`。

`boundary_effect` scenario继续保留用于 coverage/stress，但不用于 P/V 的 power/precision pass。

### 4.6 K2/V2 interaction pattern library

K2/V2 不得只写“预定 interaction scenarios”。固定使用以下有限 pattern library；`d in {0.05,0.10,0.15}`：

```text
null:                 [0, 0, 0]
single-low:           [+d, 0, 0]
single-middle:        [0, +d, 0]
single-high:          [0, 0, +d]
reversed-single:      corresponding -d patterns
ordered-divergence:   [-d, 0, +d]
reversed-divergence:  [+d, 0, -d]
```

对 K2，以 Qwen 为 fixed reference，依次只对 Llama、再对 Mistral应用一个 interaction pattern；两者同时非零仅增加一个 joint pattern，顺序为 `(Llama pattern, Mistral pattern)`。对 V2，以 random family 为 reference，对 prompt-domain contrastive family应用 pattern。family/group顺序和 pattern顺序必须写入 simulation plan。

这些 alternative patterns只报告 power/precision或最小可识别范围，不改变 P/V。method acceptance 只使用 core null scenarios。

---

## 5. P0：final P/V 与 primary/fallback 必须由唯一函数选择

### 5.1 Candidate 顺序

P2 candidates固定按以下顺序评估，不采用结果后成本函数或 Pareto选择：

```text
(50,20), (50,25), (50,30),
(75,20), (75,25), (75,30),
(100,20), (100,25), (100,30)
```

### 5.2 每个 candidate 的方法选择

对每个 candidate，先只使用 core null scenarios执行：

1. full GLMM + synchronized max-T；
2. full GLMM失败时执行固定 reduced GLMM；
3. GLMM procedure不满足 FWER/coverage/completion时执行预注册 Webb multiway bootstrap；
4. Webb也不满足时，该 candidate 对 P2 标记 `no_valid_confirmatory_method`。

方法接受标准保持：

```text
simulation replicates per core scenario >= 10,000
master seed = 42
MCSE for FWER/coverage <= 0.005
empirical family-wise type-I error <= 0.055
empirical simultaneous 95% CI coverage >= 0.93
successful fit/inference completion >= 0.95
```

### 5.3 P2 candidate pass

只有存在有效方法的 candidate 才进入 power/precision check。唯一 canonical planning scenario为：

```text
q = 0.10
d = +0.10
all variance components = 1x independent-screen estimates
kappa = 0
failure_rate = f_screen
```

Candidate 同时满足以下两项才通过：

```text
P2-B Holm zero-null rejection probability >= 0.80
P2-U mean synchronized family-wise CI half-width <= 0.05
```

选择 candidate list 中第一个通过者。其他 q/d/variance/correlation scenarios只用于 operating-characteristic disclosure和 method stress，不参与 candidate择优。

若没有 candidate通过：

- final `P=100,V=30`；
- 使用该 candidate中通过 null-validity 标准的最高优先级方法；
- P2-B power失败则 P2-B `power-limited/estimation-only`；
- P2-U precision失败则 P2-U `precision-limited/estimation-only`；
- 若最大 candidate没有任何有效方法，整个 P2 family 为 estimation-only。

### 5.4 K2/V2 不得反向改变 P/V

K2 使用 P2 选出的 final `P/V`。V2 始终固定 `P=30 prompts,V=20 directions/family`。K2/V2 simulation只决定：

```text
GLMM primary
Webb primary
estimation-only/fixed-tested-conditions
```

K2/V2 power或precision不足不得扩 P/V、增加 model/direction/anchor，或改变 P2 选样。

---

## 6. P0：统计 backend、Holm、max-T 和 claim gate 必须一致

### 6.1 `statistics_backend_manifest.json` 必含字段

Codex 不得虚构具体软件，但 v3.3.2 必须要求在 simulation前填入并哈希：

```text
language/runtime version
package names and exact versions
GLMM estimator and likelihood approximation
optimizer and optimizer order
initialization
absolute/relative tolerances
maximum iterations/evaluations
Hessian and singularity checks
random-effect SD boundary threshold
standard-error extraction
parametric bootstrap implementation
Webb weight distribution and centering
multiway cluster combination rule
quantile implementation
RNG algorithm and seed derivation
```

manifest缺失或 implementation fixture失败时不得运行 coverage simulation或 Freeze B。

### 6.2 Raw p-value 的唯一计算

对 GLMM parametric bootstrap和 Webb fallback，endpoint raw two-sided p-value统一使用相应预注册 centered studentized bootstrap distribution：

```text
p_raw_j = (1 + count(abs(T_j_star) >= abs(T_j_observed)))
          / (R_successful + 1)
```

不得混用 Wald p、likelihood-ratio p、bootstrap p或按较小者报告。Holm对 fixed family order中的 `p_raw_j` 调整；raw p tie按 family order处理。

### 6.3 max-T 保持 synchronized

保留 v3.3.1 的9,999 synchronized replicates、nearest-rank 0.95 quantile、studentization、完整 refit/standardization和最多5% technical fit failure。补充：

- 只有 family所有 members均成功的 replicate进入 max-T distribution；
- `R_successful` 对 family共同计数；
- 任一原始 member non-estimable或 family共同 completion `<95%` 时该 procedure失败；
- 同一 replicate使用相同 prompt/vector/direction resampling identities和同一 endpoint-correlation draw identity。

### 6.4 P2 zero-null 的唯一 Boolean gate

对每个 P2 endpoint `e`，confirmatory zero-null wording必须同时满足：

```text
P1 gate passed
and automated primary Holm-adjusted p_e < 0.05
and automated synchronized max-T 95% CI excludes 0
and two-phase synchronized family-wise 95% CI excludes 0
and all three signs agree
and judge/human quality and support gates pass
```

任一条件失败都不得写 confirmatory detection。Holm 与 automated max-T 不一致时固定写：

```text
multiplicity procedures were discordant; endpoint retained for estimation only
```

不得选择较有利者。P2 joint-profile wording要求 P2-U和P2-B分别通过上述 gate。

P2-B practical-threshold wording还要求 automated和two-phase family-wise CIs均完全越过同一 `+0.10` 或 `-0.10` 边界。

### 6.5 K2/V2 的 global/local 规则

K2/V2 的 global interaction detection由对应 global-test Holm-adjusted p `<0.05` 决定。Anchor-wise max-T CIs只用于定位和量化：

- global Holm通过、无 anchor-wise CI排除0：允许写 global interaction detected，但不能点名某 anchor difference；
- global Holm不通过、个别 anchor CI排除0：只作 secondary estimate，不声称 global interaction；
- method validation失败：整个 family estimation-only。

Rendering `B-A/D-C` family采用同样的 Holm detection/max-T localization层级，不得把 local CI替代 family decision。

---

## 7. P0：重写 fixed720 sampling，保证 positivity 与可计算权重

### 7.1 不得先抽 floor 再抽剩余样本

v3.3.1 的“先抽四 cell floor，再抽剩余 quota”会使同一 item 具有难以审计的多阶段 inclusion probability。v3.3.2 必须改为：先计算所有 disjoint strata 的最终 quota，再在每个 stratum 内执行一次 uniform sampling without replacement。

### 7.2 P2 critical strata

P2 critical sampling strata固定为：

```text
(logical_cell, predicted_class)

logical_cell in {
  (mu_all_tw, c_A),
  (mu_content_tw, c_A),
  (mu_all_tw, c_T),
  (mu_content_tw, c_T)
}

predicted_class in {broken, unsafe, refusal, safe}
```

对每个 logical cell：

1. 总 quota至少30；
2. 每个 nonempty predicted-class stratum quota至少1；
3. cell内剩余 quota按 eligible count Hamilton分配；
4. tie按 canonical stratum key字典序；
5. 若 cell eligible总数不足30，则取尽并触发对应 endpoint capacity downgrade。

P2 critical quotas先作为约束写入全局 quota table。全局 predicted-class target仍为 `30%/30%/20%/20%`；先扣除 critical quotas，再将剩余 quota按 v3.3.1 的 model/anchor/arm/domain规则分配。若某全局 class target已被 critical quotas超过，其 residual设0，溢出不回收已分配项，剩余容量按其他 class的原始缺口 Hamilton重分配。总 N始终为720或 universe容量不足时的预定降级 N。

### 7.3 Stratum 内抽样与 inclusion probability

每个 disjoint stratum `h` 使用 PCG64，从 master seed42和 canonical stratum key 派生独立子流。子 seed 的唯一计算为：

```text
seed_bytes = SHA256(
  UTF8("human-sample-v1|42|" + canonical_stratum_key)
).digest()[0:16]

subseed = int.from_bytes(seed_bytes, byteorder="big", signed=false)
```

然后在该 stratum 内做一次 uniform sampling without replacement：

```text
N_h = eligible item count
n_h = final frozen quota
pi_i = n_h / N_h for every item i in stratum h
```

禁止通过结果后 reroll、交换 item、补抽 rare gold或优化 judge agreement。每个 P2 critical nonempty stratum必须有 `n_h>=1`，从而保证进入 P2 correction 的所有 eligible units满足 `pi_i>0`。任一 P2 unit所在 stratum `pi_i=0` 时，对应 endpoint two-phase correction不可识别并降为 estimation-only。

### 7.4 Cluster-support 与 weight-degeneracy gate

抽样后、任何 human gold可见前，在 sample lock中计算但不得 reroll：

```text
per P2 logical cell:
  unique prompt_ids >= 15
  unique vector_ids >= 10

per P2 endpoint arm:
  Kish ESS = (sum_i 1/pi_i)^2 / sum_i (1/pi_i)^2 >= 20
  max normalized analysis weight <= 0.20
```

若 eligible universe本身的 unique prompt/vector少于阈值，则记录 capacity failure。任一阈值失败时，对应 endpoint human-corrected inference标记 `cluster_or_weight_precision_downgrade`；不得重新抽样或扩720。

这些是最小可计算性/权重稳定性 gate，不是证明 power充分。Threats必须继续承认 fixed720 和 rare gold限制。

### 7.5 Human sample lock 必含字段

除 v3.3.1 字段外，新增：

```text
canonical disjoint stratum definition
eligible N_h and final n_h for every stratum
quota-construction trace
critical-cell constraint trace
per-item pi_i
per-cell unique prompt/vector counts
per-arm Kish ESS and maximum normalized weight
positivity pass/fail
cluster/weight downgrade state
```

---

## 8. P0：two-phase estimator 和 CI 的唯一实现

### 8.1 使用 Hájek residual correction

将 v3.3.1 的含糊 `IPW mean` 明确为 self-normalized Hájek estimator。对 endpoint `e`、arm `a`：

```text
r_i(e) = y_gold_i(e) - y_judge_i(e)
w_i = 1 / pi_i

b_validation(e,a) =
  sum_(i in validation arm a) w_i * r_i(e)
  / sum_(i in validation arm a) w_i

p_two_phase(e,a) =
  clip(p_judge_full(e,a) + b_validation(e,a), 0, 1)

RD_two_phase(e) =
  p_two_phase(e,all-token) - p_two_phase(e,content-token)
```

Point estimate和每个 bootstrap replicate均应用同一 clip规则。不得改用 unnormalized Horvitz-Thompson、naive human-subset RD、matrix inversion correction或按结果选择 estimator。

### 8.2 Primary prompt-cluster bootstrap

Two-phase primary CI固定使用9,999个 synchronized stratified prompt-cluster bootstrap replicates：

1. 在 frozen harmful prompt category strata内，对 full eligible P2 prompt IDs有放回抽取原 stratum prompt数；
2. 每个被抽 prompt的全部 full-universe judge rows继承 prompt multiplicity；
3. validation residual rows同时继承相同 prompt multiplicity和固定 `1/pi_i`；
4. 每个 replicate重算 `p_judge_full`、Hájek residual、clip、arm probabilities、RD和两个 P2 endpoints；
5. 两 endpoints共享同一 prompt resample identity；
6. 使用 synchronized max-T形成 two-phase family-wise CI；
7. 任一 arm分母为0的 replicate记 technical inference failure；family共同成功率必须`>=95%`。

### 8.3 Vector-aware two-way sensitivity

Mandatory sensitivity使用 two-way pigeonhole bootstrap：prompt IDs与 vector IDs分别在各自冻结集合内有放回抽取，row multiplicity为二者 multiplicity乘积；其余 Hájek、clip、同步 family和失败处理与 primary相同。该 sensitivity不替代 prompt-cluster primary，也不新增 p-value family。

### 8.4 Judge metrics 与 two-phase gate

保留 raw Krippendorff alpha、weighted macro-F1和 critical-class recall thresholds。明确 `weighted macro-F1` 是使用 `1/pi_i` 恢复每个 class confusion totals 后的 class-wise macro average，不是 sklearn support-weighted F1：

```text
precision_c = IPW_TP_c / (IPW_TP_c + IPW_FP_c)
recall_c    = IPW_TP_c / (IPW_TP_c + IPW_FN_c)
F1_c        = 2 * precision_c * recall_c / (precision_c + recall_c)
macro_F1    = arithmetic_mean_c(F1_c)
```

零 denominator 的 class metric记 non-estimable并触发对应 quality downgrade，不以0或1静默填充。必须同时报告各 class F1和未加权 validation-sample结果。

对 P2-U A两 arms和P2-B T两 arms，继续分别报告 IPW sensitivity、specificity、FPR、PPV、confusion counts及 CI。overall/per-model指标不能替代 arm-specific audit。

若出现以下任一情况，对应 endpoint降为 estimation-only：

```text
raw alpha < 0.70
required judge threshold fails
positivity fails
critical-cell capacity fails
cluster/weight gate fails
two-phase family completion < 0.95
automated/two-phase signs disagree
required Holm/max-T/two-phase gate fails
```

### 8.5 修复章节引用

在目标协议第17节新增正式小节：

```text
### 17.7 P2 Decision-Consistency and Downgrade
```

将 v3.3.1 第17.6节末尾关于 P2判定顺序、K2/V2 confusion audit和 validation-set不可调 judge prompt的相关内容按逻辑拆入17.7。第4.6节引用“第17.7节”因此成为有效引用。全文检查所有章节号，不得保留不存在的交叉引用。

---

## 9. P0：预算必须覆盖 blocked partial paths 与实际调用

### 9.1 Random screen 固定值

由于删除未定义 Qwen extra-range branch：

```text
S_random_logical = 2,700
```

不得继续以3,600作为正常 screen logical upper。Technical retries另计，不混入 logical-cell N。

### 9.2 V2 分解变量

用以下变量替换 `N_V2 in {0,1950,2100}`：

```text
S_V2 in {0,150,300}
C_V2 in {0,1800}
N_V2_logical = S_V2 + C_V2
N_V2_random_rematch in {0,1800}
```

只允许以下状态：

| path | S_V2 | C_V2 | rematch |
|---|---:|---:|---:|
| qualified cross-reference / blocked before screen | 0 | 0 | 0 |
| blocked after initial screen | 150 | 0 | 0 |
| blocked after one rescue | 300 | 0 | 0 |
| completed, no rescue | 150 | 1,800 | 0 |
| completed, rescue, matched random rerun required | 300 | 1,800 | 1,800 |

若 rescue发生但 V2 confirmation被其他 pre-confirmation gate阻断，则 `300/0/0`，不得提前运行 matched random rematch。

### 9.3 Logical budget公式

Random-family logical generation改为：

```text
N_random_logical_generated =
    2700
  + 9PV
  + 2PV
  + B_bridge*PV
  + 3PV
  + 3P
  + 3N_bV
  + 3N_b
  + Q_alpha
  + R_render

N_random_logical_automated_judged =
  N_random_logical_generated - Q_alpha
```

总 logical budget：

```text
N_v3_3_2_logical_generated =
    N_random_logical_generated
  + S_V2
  + C_V2
  + N_V2_random_rematch
  + 1200

N_v3_3_2_logical_automated_judged =
    N_random_logical_automated_judged
  + S_V2
  + C_V2
  + N_V2_random_rematch
  + 1200
```

### 9.4 新 planning 与 scope-grid fixtures

Planning complete/no-rescue path：

```text
P=50, V=20, N_b=30, B_bridge=1,
Q_alpha=144, R_render=0,
S_V2=150, C_V2=1800, rematch=0

= 23,034 logical generated
= 22,890 logical automated judged
```

同一参数下：

```text
qualified cross-reference = 21,084 / 20,940
completed one-rescue      = 23,184 / 23,040
```

Scope-grid complete/rescue/rematch path：

```text
P=100, V=30, N_b=30, B_bridge=2,
Q_alpha=144, R_render=200,
S_V2=300, C_V2=1800, rematch=1800

= 59,234 logical generated
= 59,090 logical automated judged
```

这些仍只是当前 scope-grid 的 logical-cell上界，不是 actual call、GPU hour、货币成本或未来 amendment的永久 hard upper。

### 9.5 Actual call budget

新增实际调用变量：

```text
R_generation_technical = actual generation retries after technical failures
R_judge_parse = actual automated-judge retries after parse/infrastructure failures

N_generation_calls =
  N_v3_3_2_logical_generated + R_generation_technical

N_automated_judge_calls =
  N_v3_3_2_logical_automated_judged + R_judge_parse
```

每个 logical cell最多一次相同配置的 technical retry，因此：

```text
0 <= R_generation_technical <= N_v3_3_2_logical_generated
0 <= R_judge_parse <= N_v3_3_2_logical_automated_judged
```

资源表必须同时报告 scheduled logical cells、completed logical outputs、excluded failures、generation attempts和judge attempts。不得把 logical budget称为 actual调用总数。

---

## 10. P1：threshold rationale 与 sensitivity grid

`delta_P1_min=0.10` 和 `m_B=0.10` 保持 confirmatory gate，不由数据重标定。为避免只给单一任意阈值，固定 descriptive sensitivity grid：

```text
P1 relative calibration threshold grid:
  {0.05, 0.10, 0.15, 0.20}

P2-B absolute RD threshold grid:
  {0.05, 0.10, 0.15, 0.20}
```

只有0.10进入 confirmatory gate；其他值只报告 point estimate/CI相对阈值的位置，不计算新的显著性 family，不选择最有利阈值，不改变主结论。

P2-U继续无 practical margin，因此任何 significant tiny unsafe difference只能写 `detected tested-point difference`，不得写 `material security impact`。Threats必须说明0.10是 protocol-level interpretation threshold，不是外部验证的通用安全损失函数。

---

## 11. 必须同步修改的章节

目标协议可保留25章主结构，但至少同步：

| v3.3.1章节 | v3.3.2必须修改 |
|---|---|
| 1 Executive Summary | 版本改为v3.3.2-proposed；说明只关闭冻结缺口 |
| 2 Threat Model | 保留judge differential error；增加two-phase positivity/weight风险 |
| 4 Claims | P2 zero-null写成唯一Boolean gate；threshold sensitivity固定 |
| 6 Freeze | 增加base-anchor、simulation-plan、statistics-backend依赖 |
| 7 Models/Vectors/Prompts | base anchors改为external frozen inputs；删除Qwen extra-range搜索 |
| 9 E0 | 增加generator、P/V selection、positivity、partial-budget fixtures |
| 14 E5/P2 | Hájek correction、prompt bootstrap、Holm/max-T/two-phase联合判定 |
| 15 E6/K2 | anchors不由screen移动；K2不反向改变P/V |
| 16 V2/Stochastic | V2 partial states；V2固定30/20；stochastic不变 |
| 17 Validation | disjoint quota、exact pi、cluster/ESS gates、新17.7 |
| 18 Power | exact generator、scenario union、candidate function、interaction patterns |
| 19 Statistics | backend manifest、raw p、global/local判定、family共同成功replicates |
| 20 Budget | S_random=2700、S_V2/C_V2、logical/attempt分列、新fixtures |
| 21 Threats | external anchor input、binary simulation approximation、fixed720权重限制 |
| 22 Artifacts | 增加base anchor/backend/quota trace/partial budget artifacts |
| 23 Claims | 增加discordant multiplicity和two-phase downgrade措辞 |
| 24 Checklist | 加入本 brief 全部验收项并删除旧数值 |
| 25 Priority | anchor manifest和simulation backend先于screen/simulation/Freeze B |

全文必须同步删除或替换：

```text
S_random <= 3,600              -> S_random_logical = 2,700
23,934 / 23,790                -> 23,034 / 22,890
60,134 / 59,990                -> 59,234 / 59,090
N_V2 in {0,1950,2100}          -> S_V2/C_V2 state model
Qwen extra range / midpoint    -> removed
IPW mean                       -> Hajek residual correction
30-item floor first-pass draw  -> final disjoint-stratum quotas then one draw
```

旧版数值可在版本历史说明中出现，但不得作为 v3.3.2 当前预算或 acceptance target。

---

## 12. E0 与实现前 QA 新增项

目标协议 E0 至少包含：

| QA | fixture | pass rule |
|---|---|---|
| base-anchor manifest | missing/hash/order/outcome-contamination fixtures | 非法manifest阻止Freeze B，不产生默认anchor |
| random-screen matrix | 3x3x30x10 fixture | 恰为2,700 logical identities，无extra-range branch |
| marginal generator | zero/random-effect fixtures | bisection后marginal probability误差`<=1e-8` |
| endpoint correlation | fixed synthetic draws | kappa子流、shared clusters和family identities可复现 |
| P/V selector | pass/fail matrix | 返回candidate list首个合格项；全失败返回100/30+downgrade |
| interaction patterns | K2/V2 pattern registry | pattern/order/hash与手算列表一致 |
| backend manifest | incomplete/complete fixtures | 缺optimizer/tolerance/Webb字段时non-zero failure |
| raw bootstrap p | small reference distribution | plus-one p、Holm tie和family order匹配手算 |
| max-T family completion | member failure fixtures | 只使用family共同成功replicates，<95%失败 |
| P2 Boolean gate | Holm/CI/two-phase discordant cases | 任一冲突均降级，无择优分支 |
| quota construction | sparse/over-target classes | final disjoint quotas和720总数确定性 |
| inclusion probability | known N_h/n_h | 每item `pi=n_h/N_h`，P2无zero pi |
| cluster/weight gate | concentrated sample | prompt/vector/ESS/max-weight失败触发downgrade且不reroll |
| Hájek correction | hand-computed weighted sample | residual、clip、RD与手算一致 |
| two-phase bootstrap | fixed prompt multiplicities | full judge与validation residual同步重算 |
| V2 partial budget | five allowed states | 0/150/300/1950/2100 paths与rematch约束正确 |
| budget arithmetic | planning/scope-grid | 得到23,034/22,890和59,234/59,090 |
| actual calls | retry fixtures | logical counts与generation/judge attempts正确分列 |
| section references | heading/reference scan | 不存在失效的第x.y节引用 |

任一对应 QA 未定义或失败时阻止相关 Freeze，不得只记录 warning 后继续 formal execution。

---

## 13. Allowed and Forbidden Claims 修订

### 13.1 继续允许

- pooled-token P1 effect是否越过固定0.10 gate；
- P1/P2-B point estimate和CI相对固定 descriptive threshold grid的位置；
- P2 endpoint是否同时通过 automated Holm、automated max-T、two-phase CI和quality/support gates；
- multiplicity procedures是否discordant并因此降级；
- K2/V2 global interaction及可被 simultaneous CI定位的anchor estimates；
- two-phase correction、judge differential error和weight/cluster downgrade；
- V2在initial/rescue后完成或被阻断的实际路径；
- logical cells、completed outputs和actual attempts的资源差异。

### 13.2 新增禁止

- 未提供合法 `base_anchor_manifest.json` 即运行 random screening或 Freeze B；
- 使用 behavior screen移动或重新选择 base `rho_A/rho_T/rho_H`；
- 恢复 Qwen extra-range、midpoint或其他未预注册 anchor search；
- 根据 K2/V2 power反向增加 P/V；
- simulation generator未锁定即用 coverage结果选择方法；
- 用 confirmation effect、arm-specific confirmation prevalence或human gold构造 simulation scenarios；
- 在 Wald、LRT、bootstrap raw p之间结果后择优；
- Holm与max-T冲突时保留confirmatory P2 wording；
- global K2/V2 Holm不通过时用单个anchor CI声称global interaction；
- 先抽critical floor再以无法计算的总体概率声称IPW有效；
- 任一P2 eligible stratum `pi=0`时仍计算population two-phase correction；
- cluster/ESS/weight gate失败后reroll、换seed或扩720；
- 把support-weighted F1称为本协议的prevalence-restored weighted macro-F1；
- 将 logical-cell budget称为 actual generation/judge calls；
- 忽略 V2 initial/rescue后blocked产生的150/300成本；
- 把0.05/0.15/0.20 sensitivity阈值升级为事后confirmatory gate。

---

## 14. Codex 交付前验收清单

- [ ] 所有旧版设计、brief、代码和artifacts未修改
- [ ] 新建`writing/paper1_attention_sink_mu_experiment_design_v3_3_2.md`
- [ ] 协议版本为`v3.3.2-proposed`且未虚假标记frozen
- [ ] v3.3.2可独立阅读，不要求回看本brief执行
- [ ] contribution、P1->P2 hierarchy和实验范围未扩大
- [ ] `base_anchor_manifest.json` schema、时点、合法性和block规则完整
- [ ] base anchors不再由behavior screen搜索、移动或重命名
- [ ] A/T/H明确为预注册identifiers而非数据发现的自然threshold
- [ ] random screen固定2,700 logical responses
- [ ] 全文删除Qwen extra-range和midpoint rescue自由度
- [ ] simulation_plan与statistics_backend manifests均为Freeze B前依赖
- [ ] logistic random-effect generator、marginal bisection和shared-pair规则完整
- [ ] kappa correlation-stress set有限且固定
- [ ] missingness只用blinded pooled screen input且无默认伪造
- [ ] core scenario union可机械生成且boundary scenarios不用于N择优
- [ ] K2/V2 interaction pattern library、group顺序和reference固定
- [ ] P/V candidate顺序和canonical planning scenario唯一
- [ ] P2-B power与P2-U precision必须联合通过才选择candidate
- [ ] 无candidate通过时固定100/30并逐endpoint降级
- [ ] K2/V2不改变P2 final P/V；V2保持30/20
- [ ] backend manifest包含optimizer/tolerance/likelihood/Webb/RNG字段
- [ ] raw p统一为plus-one centered studentized bootstrap p
- [ ] max-T只使用family共同成功replicates
- [ ] P2 Boolean gate同时包含P1、Holm、automated CI、two-phase CI和quality/support
- [ ] Holm/max-T/two-phase冲突一律降级，不按有利结果选择
- [ ] K2/V2 global Holm与anchor localization的解释层级明确
- [ ] human sampling先计算final disjoint quotas，再每stratum一次SRSWOR
- [ ] P2四logical cells各30 quota且每个nonempty predicted class至少1
- [ ] 每item inclusion probability严格为`n_h/N_h`
- [ ] 所有P2 eligible strata均满足positivity或endpoint降级
- [ ] sample lock记录prompt/vector、Kish ESS和max weight diagnostics
- [ ] cluster/weight失败不reroll、不扩720
- [ ] two-phase point estimator明确为Hájek residual correction
- [ ] prompt-cluster bootstrap和two-way sensitivity算法可编码
- [ ] weighted macro-F1明确定义为IPW prevalence-restored class metric
- [ ] 新增有效的17.7小节且全文无失效章节引用
- [ ] V2预算使用S_V2/C_V2五种合法状态
- [ ] blocked V2的150/300 logical成本进入总账
- [ ] logical generation、completed output、actual generation/judge calls分列
- [ ] planning预算为23,034/22,890
- [ ] scope-grid预算为59,234/59,090
- [ ] v3.3.1旧预算数值不再作为当前验收目标
- [ ] threshold sensitivity grids固定且仅descriptive
- [ ] Threats包含external anchors、binary generator近似、positivity/weight与fixed720限制
- [ ] E0包含本brief规定的全部fixtures
- [ ] block registry、statistics、claims、figures、budget、artifacts和checklist一致
- [ ] 所有未定实体都有artifact schema、冻结时点、允许输入和失败后果

---

## 15. 最终交付要求

Codex 最终只需交付：

1. `writing/paper1_attention_sink_mu_experiment_design_v3_3_2.md`；
2. 一段简短变更摘要，至少说明如何修复：
   - base-anchor provenance和未定义search；
   - simulation generator及P/V联合选择；
   - backend、raw p、Holm/max-T/two-phase冲突；
   - human-sampling positivity、exact inclusion probability和cluster/weight gate；
   - Hájek two-phase estimator及同步bootstrap；
   - V2 blocked partial budget和actual-call accounting；
   - 第17.7节失效引用与固定threshold sensitivity grid。

除非用户另有明确要求，不修改实验代码、任何旧版设计、已有 artifacts、Paper 1其他文档或运行环境，不运行构建、测试、模型、judge、annotation或模拟。
