# Paper 1 Stage 3：v1.0、v3.3.2 与 v3.4-rc1 资源可行性评估

**文档类型**：资源与执行周期决策备忘录

**日期**：2026-07-22

**状态**：仅用于评估与后续决策，不是实验设计修订；本文件不改变任何既有协议。

## 1. Executive Decision

v3.4-rc1 的模型生成矩阵并未比 v1.0 增大一个数量级。v3.3.2/v3.4 的 planning generation budget 约为 23k，V2 rescue 完成后约为 25k，与 v1.0 的 25.2k 基本相当。

真正不可执行的部分是 v3.3.2 及 v3.4-rc1 中的 nested coverage/power simulation：outer simulation 与每个 outer dataset 内部的 9,999 次完整重拟合相乘，导致十亿至数百亿级 endpoint fits。

推荐的基线选择是：

```text
以 v3.4-rc1 作为统计正确性基线；
保留其 estimand、multiplicity、two-phase 和 downgrade 修复；
对 nested simulation 进行资源边界处理；
不要原样回退到 v3.3.2。
```

v3.3.2 可以作为生成实验矩阵的参考，但不能作为完整统计协议原样执行，因为它仍保留 resampling/seed 不完全冻结、nested simulation 不可执行和部分 global interaction inference 未闭合的问题。

## 2. Comparison Scope

本文档区分四类成本：

1. `logical generation`：模型实际生成的实验响应数；
2. `automated judge`：Qwen3 等本地 judge 对可评测响应的调用数；
3. `human validation`：人工 response items 与 annotation assignments；
4. `simulation fits`：统计 operating-characteristic simulation 中的 GLMM/endpoint fits，不是模型生成。

这些类别不能合并成一个 sample size。

## 3. Generation Budget Comparison

### 3.1 Main comparison

| Design/path | Logical generated | Automated judged | Relative to v1.0 generated |
|---|---:|---:|---:|
| v1.0 full upper bound | 25,200 | not fixed as a separate total | 1.00x |
| v3.3.2 qualified cross-reference | 21,084 | 20,940 | 0.84x |
| v3.3.2/v3.4 planning | 23,034 | 22,890 | 0.91x |
| v3.3.2/v3.4 completed one-rescue path | 24,984 | 24,840 | 0.99x |
| v3.3.2/v3.4 scope-grid worst case | 59,234 | 59,090 | 2.35x |

v1.0 的 25,200 是全部 Gate 通过后的上限，包含 harmful primary、benign integrity、phase、cross-layer、screening 与 bridge。[v1.0 §12.8](../paper1_attention_sink_mu_experiment_design.md:634)

v3.3.2 的 planning 与 rescue 数字在协议中明确给出。[v3.3.2 §20.5](../paper1_attention_sink_mu_experiment_design_v3_3_2.md:1244)

因此，若只执行最可能的 planning/rescue path，v3.3.2/v3.4 与 v1.0 的生成规模处于同一数量级。59,234 是覆盖候选 P/V 与所有 rescue 状态的 scope-grid upper bound，不等于实际必跑量。[v3.3.2 §20.5](../paper1_attention_sink_mu_experiment_design_v3_3_2.md:1273)

### 3.2 What changed in the allocation

v3.3.2/v3.4 主要进行了预算重分配：

- 主行为条件通常从 `50 prompts x 10 vectors` 增加到 planning 的 `50 prompts x 20 vectors`；
- 删除或限制了部分 v1.0 的 phase/cross-layer 扩展；
- 增加 V2 vector-family、stochastic robustness 和 support audit；
- human validation 从 v1.0 的至少 360 items 增加到 720 items；
- attention block 收窄为 192 条 Qwen teacher-forced trajectories；
- P2/K2/V2 的统计记录和失败审计明显增加。

因此，GPU generation 成本没有发生数量级增长，但人工、manifest、fixture、统计实现和审计成本高于 v1.0。

## 4. Human and Measurement Cost

### 4.1 Human validation

v1.0 要求至少抽取 360 条 response 进行人工验证；v3.3.2/v3.4 固定为：

```text
720 response items
1,440 primary annotation assignments
additional adjudication assignments for disagreements
```

[v1.0 judge validation](../paper1_attention_sink_mu_experiment_design.md:722)

[v3.3.2 human validation](../paper1_attention_sink_mu_experiment_design_v3_3_2.md:900)

这是人工工作量约 2 倍，但仍属于可执行范围。若每个 item 两名标注者各需 2--5 分钟，则 primary assignments 约需 48--120 annotator-hours，尚不包括 adjudication 和组织时间。

### 4.2 Measurement and attention

v3.3.2/v3.4 的主要非生成资源包括：

- 三模型 all-layer norm records；
- Qwen formal-layer extension；
- 192 条 attention teacher-forced trajectories；
- V2 construction forwards，planning 约 750、上限约 1,000；
- Freeze、hash、QA fixture 和统计 backend artifact。

这些成本明显高于一个简单的 1000-vector generation run，但没有显示出字面不可执行性。主要不确定性来自 Stage 3 production script 和 fixture 是否需要重新实现。

## 5. Nested Simulation Problem

### 5.1 v3.3.2 problem

v3.3.2 要求每个 core scenario 至少 10,000 个 outer simulations，同时正式 max-T procedure 又要求 9,999 次同步 resampling，并在每次 resampling 中重新拟合模型。[v3.3.2 §18.3--18.5](../paper1_attention_sink_mu_experiment_design_v3_3_2.md:1002)

已有资源审计计算出，即使只取 N-screen null 的最低范围，也至少有：

```text
9 candidates x 3 prevalence x 10,000 outer x 9,999 inner
= 2,699,730,000 inner resampling/refit operations
```

[v3.3.2 resource audit](../../judge%20subagent/resource_and_implementation_audit.md:92)

这还没有计入 alternative/stress scenarios、K2/V2、fallback、integration draws 和 technical retries。

### 5.2 v3.4-rc1 exact budget

v3.4-rc1 将这个问题完全参数化并锁定为：

| Active rows | Endpoint fits |
|---:|---:|
| 27 audit lower bound | 5,684,040,000 |
| 73 core-null | 15,367,960,000 |
| 162 N-screen | 34,104,240,000 |
| 239 full active union | 50,314,280,000 |

[v3.4 §18.5.1](../paper1_attention_sink_mu_experiment_design_v3_4_rc1.md:1287)

每个 fit 还最多需要 160,000 次 population-average integration draws，且上述数字未包含 fallback、retry 和额外 draw operations。[v3.4 §18.5.1](../paper1_attention_sink_mu_experiment_design_v3_4_rc1.md:1294)

### 5.3 Approximate wall-clock scale

只计算 15.368B core-null fits，忽略 I/O、通信和并行损失：

| Single fit time | Serial | 1,000 workers |
|---:|---:|---:|
| 1 ms | 178 days | 4.3 hours |
| 10 ms | 4.87 years | 1.78 days |
| 100 ms | 48.7 years | 17.8 days |
| 1 s | 487 years | 178 days |

完整 50.314B active union 还要再乘约 3.27。普通实验室的少量 GPU/CPU 节点无法把该 simulation 视为几周内可完成的普通实验。

## 6. Why v3.4 Should Remain the Baseline

v3.4-rc1 的主要变化是把 v3.3.2 中未闭合的统计语义显式化，而不是增加了同等规模的模型生成实验。它保留并明确了：

- K2/V2 的 estimation + simultaneous CI 边界；
- two-phase SRSWOR variance、SE 和 non-estimable downgrade；
- 80% 只属于 automated P2-B sub-gate；
- exact resampling counts、master seed 和 substream derivation；
- 资源不足时不得生成虚假的 coverage/power artifact；
- resource failure 后的确定性 downgrade。

v3.3.2 的资源审计明确指出，其仍有 resampling/seed 未完全冻结、nested simulation 不可执行以及相关统计闭合问题。[v3.3.2 audit](../../judge%20subagent/resource_and_implementation_audit.md:91)

因此，回退到 v3.3.2 并不能消除 nested simulation；它只会重新隐藏计算负担，并可能重新引入统计实现歧义。

## 7. Executable v3.4 Branch and Claim Boundary

### 7.1 Current rc1 resource-failed branch

v3.4-rc1 已规定：如果 `simulation_resource_contract.json` 缺失或容量不足，则：

```text
不启动 coverage/power simulation
不生成虚假的 P/V/N、coverage 或 power artifact
固定进入 P=100,V=30, P2=estimation-only
K2/V2 保持 CI-only
```

[v3.4 resource branch](../paper1_attention_sink_mu_experiment_design_v3_4_rc1.md:1173)

这里需要特别区分：`P=50,V=20` 是前面用于周期估计的 planning configuration，不是当前 v3.4-rc1 resource-failed branch 的最终规定。若希望固定为 `P=50,V=20`，需要另行形成正式 protocol amendment，不能把它当作 rc1 现有规则。

### 7.2 Meaning of estimation-only

在没有完整 simulation/backend resource contract 的情况下，论文可以保留：

- fixed-support endpoint estimates；
- raw paired RD；
- synchronized simultaneous CIs；
- broken/unsafe 的四分类结果；
- model、phase、dose 和 estimator 的描述性比较；
- attention/norm 的 association evidence。

但不能声称：

- power-selected P/V；
- 已通过 protocol-specific coverage simulation 的 coverage 保证；
- 完整 Boolean gate 已获得 80% power 保证；
- K2/V2 的 global detection/power；
- full active union 已完成 operating-characteristic validation。

## 8. Estimated Calendar Time

以下估计针对资源可行的 Stage 3 路线，不包含 15B--50B nested simulation，也不重复已经完成的 Stage 1 full-1000 attack。

### 8.1 Planning-scale branch

假设使用 `P=50,V=20` 左右的 planning-scale behavior matrix，并暂不把它当作当前 rc1 resource-failed branch 的正式 P/V 定义：

| Work package | Estimated time |
|---|---:|
| production scripts、manifests、Freeze、fixtures | 5--10 days |
| norm/`mu`、template/padding QA | 2--5 days |
| random screen、V2 construction、support audit | 2--5 days |
| approximately 23k behavior generation | 4--10 days |
| approximately 23k automated judge calls | 2--7 days |
| attention measurement | 1--3 days |
| human validation and adjudication | 1--3 calendar weeks |
| aggregation、analysis、figures、audit | 4--8 days |

在 2--3 张 GPU、任务可并行且代码基本可用时，总日历周期约为 **4--6 周**。一张 GPU 串行运行时约为 **6--10 周**。如果 Stage 3 production implementation 需要多轮返工，周期可能达到 **8--12 周**。

### 8.2 Current rc1 `P=100,V=30` branch

当前 rc1 的资源失败分支固定为 `P=100,V=30`，其 behavior/judge 成本高于 planning-scale branch，且可能接近 50k--59k logical upper bound，具体取决于 V2 rescue、rendering rescue 和 bridge reuse 状态。

因此，对当前 rc1 branch 更保守的估计是：

- 2--3 张 GPU：约 **5--8 周**；
- 单 GPU 串行：约 **8--12 周**；
- 若还需要重写 Stage 3 runner 和统计 backend：约 **10--14 周**。

这些时间不包括完整 nested simulation，因为该部分在现有实验室资源下没有可信的周/月级估计。

## 9. Final Recommendation

后续修改应以 v3.4-rc1 为基线，采用以下原则：

```text
保留 v3.4 的统计闭合和 claim boundary；
不运行不可执行的 nested coverage/power simulation；
不伪造 coverage、power 或 P/V-selection artifact；
按照真实资源分支报告 estimation-only；
generation、judge、human validation 和 attention 分开核算。
```

不建议原样执行 v3.3.2，也不建议为了缩短周期而删除 v3.4 的 two-phase、multiplicity 或 downgrade 规则。真正需要缩减的是 simulation obligation，而不是 estimand、endpoint 或审计规则。

