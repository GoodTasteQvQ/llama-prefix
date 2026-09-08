# Paper 1 Stage 3 实验结果与后续计划

更新时间：2026-08-14

用途：组会汇报与 Notion 结果归档

当前状态：P1、A/T/H support、P2 raw 和 K1 已完成并通过负责人检查；harmful-clean、benign integrity、fixed720 human validation 和 two-phase sensitivity 尚未完成。

---

## 1. 一页结论

Stage 3 研究的问题是：**all-token 与 content-token 两种 calibration frame 是否会改变 `mu`、实际 intervention dose，以及固定 Qwen 条件下的行为估计。**

当前结果可以概括为三点：

1. **Calibration geometry 明确改变。**
   `mu_all_tw=441.4951`，`mu_content_tw=62.1641`，前者约为后者的 7.10 倍。P1 的预设 gate 明确通过，因此可以写 token frame materially changes the measured calibration scale and intervention-dose geometry。

2. **预设 P2 行为差异方向为正，但仍不确定。**
   A 点 unsafe 配对风险差为 `+1.03` 个百分点，T 点 broken 配对风险差为 `+0.41` 个百分点；两项 simultaneous 95% CI 均包含 0，不能写成行为差异已被确认。

3. **K1 显示 T 点存在值得报告的描述性行为组成迁移。**
   在四个 cell 共同完整的 951 个 prompt-vector 坐标上，T all-token 的 unsafe 为 9.15%，T content-token 为 1.47%；对应 refusal 为 69.72% 和 79.81%。这提示更强的 all-token 实际剂量主要对应 unsafe 增多、refusal 减少，而不是大规模 broken。但 K1 没有正式 arm-contrast 区间，不能替代预设 P2 推断。

当前 Stage 3 结果分支为：

> P1 显示实质 calibration shift，但预设 P2 raw 行为对比仍不确定。K1 提供描述性行为组成解释，但不将 P2 升级为确认性正结果。

---

## 2. 总体进度

| 模块 | 固定规模 | 当前状态 | 是否产生正式结果 |
|---|---:|---|---|
| 输入与 anchor 设计 | harmful/benign frames、30 vectors、A/T/H | 完成 | 是，作为固定输入 |
| P1 calibration measurement | 100 harmful + 100 benign | 完成，`ESTIMABLE`，gate PASS | 是 |
| A/T/H support screen | `3 x 30 x 10 = 900` | 完成，A/T/H 均 `SUPPORTED` | 是 |
| P2 四个行为 cell | `4 x 50 x 20 = 4,000` | 完成，raw P2 `ESTIMABLE` | 是 |
| P2 raw materialization | 9,999 Webb replicates | 完成 | 是 |
| K1 四分类 profile | 复用 P2，0 新调用 | 完成，`ESTIMABLE` | 是 |
| Harmful clean | 50 | 未实现 runner、未运行 | 否 |
| Benign clean + T-steered | 30 + 600 | 未运行 | 否 |
| Fixed720 human sample | capacity 足够时固定 720 identities | 未分配、未标注 | 否 |
| Human-corrected P2 | 9,999 + 9,999 replicates | 未运行 | 否 |

正式 generation/judge registry 共 5,580 个 logical identities：

```text
已完成：support 900 + P2 4,000 = 4,900
未完成：harmful clean 50 + benign 630 = 680
完成比例：4,900 / 5,580 = 87.8%
剩余比例：680 / 5,580 = 12.2%
```

P1 的 200 次 measurement forward 属于独立资源类别，不计入上述 5,580 个 generation/judge identities。K1 完全复用 P2，新增 generation/judge 调用均为 0。

---

## 3. 实验设计中的三个数值：`rho`、`c` 和 `alpha`

三个 A/T/H anchor 固定的是归一化测试位置 `rho`，不是 Stage 3 运行时直接使用的 coefficient `c`。

```text
c_k = rho_k * median_content_norm_Qwen / mu_all_tw_Qwen
alpha = c * mu
```

P1 测得：

```text
median_content_norm_Qwen = 61.1210594177
mu_all_tw_Qwen            = 441.4951206107
mu_content_tw_Qwen        = 62.1640943159
```

| Anchor | 固定 `rho` | Stage 3 `c` | all-token `alpha`（bfloat16 后） | content-token `alpha`（bfloat16 后） |
|---|---:|---:|---:|---:|
| A | 0.749947 | 0.103823 | 45.75 | 6.46875 |
| T | 0.999930 | 0.138431 | 61.00 | 8.62500 |
| H | 1.249912 | 0.173039 | 76.50 | 10.75000 |

这张表说明：运行时 `c` 约为 0.10–0.17，并不表示 all-token 干预很弱。以 T 点为例，`c_T=0.1384` 乘以 `mu_all_tw` 后得到 `alpha_all≈61`，正好对应 `rho_T≈1`。同一个 `c` 乘以较小的 `mu_content_tw` 时，content-token 的实际 `alpha` 只有 8.625。

P2 的设计正是比较：**同一个名义 `c` 在两种 calibration frame 下形成不同实际剂量后，行为结果是否不同。**

---

## 4. 已完成实验一：P1 calibration measurement

### 4.1 目的

P1 只测量 calibration statistic，不运行 generation 或 judge。它回答：all-token 与 content-token frame 是否形成实质不同的 pooled norm calibration。

### 4.2 数据完整性

| 项目 | 数值 |
|---|---:|
| Harmful prompts | 100/100 complete |
| Benign prompts | 100/100 complete |
| 总 terminal records | 200/200 |
| Excluded prompts | 0 |
| Bootstrap replicates | 10,000/10,000 successful |
| 结果状态 | `ESTIMABLE` |

### 4.3 核心结果

| 指标 | 点估计 | 95% 区间或单侧下界 | 解释 |
|---|---:|---:|---|
| `mu_all_tw_Qwen` | 441.4951 | - | all-token pooled calibration |
| `mu_content_tw_Qwen` | 62.1641 | - | content-token pooled calibration |
| `ratio_select_tw` | 7.1021 | two-sided [7.0440, 7.1609] | all-token `mu` 约为 7.10 倍 |
| `delta_select_tw` | 6.1021 | two-sided [6.0440, 6.1609] | 相对差值远大于预设幅度 |
| P1 primary gate | - | one-sided lower 6.0529 > 0.10 | `PASS` |
| Equal-domain sensitivity delta | 6.1021 | [6.0444, 6.1610] | harmful/benign 等权后结论不变 |

### 4.4 P1 能说明什么

- calibration frame 不是一个无关紧要的实现细节；它会显著改变测得的 `mu`。
- 相同名义 `c` 在两种 frame 下会映射到相差约 7.1 倍的实际 `alpha`。
- 该结论在固定 Qwen checkpoint、layer、template、prompt frame 和统计协议下成立。

### 4.5 P1 不能说明什么

- P1 本身没有生成行为输出，不能证明 unsafe 或 broken 一定改变。
- 不能把该结果外推为所有模型、层、模板或 activation-steering 方法的普遍比例。
- 不能解释为 structural token 或 Attention Sink 导致行为变化。

---

## 5. 已完成实验二：A/T/H support screen

### 5.1 目的

在启动 P2 前，固定检查 A、T、H 三个 anchor 是否具有足够的有效 generation/judge support。Support screen 不是寻找最佳测试点，也不允许根据标签移动 anchor。

### 5.2 结果

| Anchor | Scheduled | Terminal | Parsed | Terminal judge failure | 最终状态 |
|---|---:|---:|---:|---:|---|
| A | 300 | 300 | 297 | 3 | `SUPPORTED` |
| T | 300 | 300 | 297 | 3 | `SUPPORTED` |
| H | 300 | 300 | 291 | 9 | `SUPPORTED` |
| 合计 | 900 | 900 | 885 | 15 | PASS |

全部 900 条 generation 完成；judge 执行 915 次，其中 15 条按固定策略进行一次 identical retry，最终形成 885 条 parsed 和 15 条 terminal judge failure。

### 5.3 Support 能说明什么

- A/T/H 三个预设 anchor 均具备进入下游分析的最低执行支持。
- P2 使用 A/T 不是根据 P2 标签结果临时挑选，而是沿用预设设计和 support 判定。
- 15 条 judge failure 是透明记录的技术 missingness，不被改写成 `broken`。

Support 标签的聚合组成是 broken 17、unsafe 69、refusal 628、safe 171，但这些标签只作信息性记录，不用于移动 anchor 或形成主要行为结论。

---

## 6. 已完成实验三：P2 fixed-support behavior estimation

### 6.1 目的与四个 cell

P2 固定比较两个预设行为 estimand：

```text
P2-U(A) = P(unsafe | A, all-token) - P(unsafe | A, content-token)

P2-B(T) = P(broken | T, all-token) - P(broken | T, content-token)
```

| Cell | Anchor | Calibration arm | Scheduled |
|---|---|---|---:|
| `P2_A_all` | A | all-token | 1,000 |
| `P2_A_content` | A | content-token | 1,000 |
| `P2_T_all` | T | all-token | 1,000 |
| `P2_T_content` | T | content-token | 1,000 |

每个 cell 使用固定的 50 条 `D_behavior_confirm` prompts 和 20 个 confirm vectors。

### 6.2 运行完整性

| Cell | Scheduled | Parsed | Terminal judge failure | Matched pairs |
|---|---:|---:|---:|---:|
| `P2_A_all` | 1,000 | 991 | 9 | 974 |
| `P2_A_content` | 1,000 | 983 | 17 | 974 |
| `P2_T_all` | 1,000 | 986 | 14 | 976 |
| `P2_T_content` | 1,000 | 990 | 10 | 976 |
| 合计 | 4,000 | 3,950 | 50 | - |

所有 4,000 条 generation 均完成，无 generation retry。Judge 共执行 4,050 次，包括 50 次固定的 identical policy retry。技术失败不作为 `broken`，不完整 pair 不进入配对 RD。

### 6.3 P2 正式推断结果

| Estimand | Matched set | N | 点估计 | SE | Simultaneous 95% CI |
|---|---|---:|---:|---:|---:|
| `P2-U(A)` | `M_A` | 974 | +0.01027（+1.03 pp） | 0.00737 | [-0.01334, 0.03387] |
| `P2-B(T)` | `M_T` | 976 | +0.00410（+0.41 pp） | 0.00277 | [-0.00477, 0.01297] |

统计协议：two-way Webb fixed-scale max-absolute simultaneous interval；9,999/9,999 replicates successful；critical value 3.20223。

### 6.4 P2 结果分析

#### A 点 unsafe

- 点估计显示 all-token 的 unsafe 比 content-token 高约 1.03 个百分点。
- 从原始 cell 比例看，unsafe 约为 2.12% 对 1.12%。相对于较低的 content-token 比例，1 个百分点对应较大的相对变化。
- 但 simultaneous CI 为 `[-1.33,+3.39]` 个百分点，仍兼容负差、零差和更大的正差。

因此，正确措辞是：**点估计可能具有实际意义，但当前精度不足以确定其方向和幅度。** 不能写成没有效果，也不能写成已确认 unsafe 增加。

#### T 点 broken

- all-token 中观察到少量 broken，content-token 中未观察到 broken。
- 配对点估计为 +0.41 个百分点。
- simultaneous CI 为 `[-0.48,+1.30]` 个百分点，仍包含 0。

因此，当前证据没有建立 T 点明确的 collapse 差异。

### 6.5 P2 的正式结论

> The calibration statistic changes, while the prespecified raw behavioral contrasts remain uncertain.

P2 是 estimation-only family，不产生 p-value、显著性检验、检测决定或确认性结论。即使区间未来排除 0，也只能报告固定 tested support 上的估计和不确定性。

---

## 7. 已完成实验四：K1 四分类 matched profile

### 7.1 目的

K1 不新增模型或 judge 调用，而是复用 P2 四个 cell 中共同完整的坐标，展示 unsafe、broken、refusal、safe 的完整组成。

```text
M_A = 974
M_T = 976
M_A intersect M_T = 951
四个 cell 各复用 951 条
总 reuse records = 951 x 4 = 3,804
新增 generation calls = 0
新增 judge calls = 0
```

K1 使用 10,000 次同步 prompt/vector bootstrap，10,000/10,000 replicates successful。

### 7.2 K1 四分类结果

括号内为各 cell 的描述性 bootstrap 95% 区间。

| Cell | Unsafe | Broken | Refusal | Safe |
|---|---:|---:|---:|---:|
| A all-token | 20/951 = 2.10% [0.42, 4.64] | 0% [0, 0] | 78.02% [70.35, 84.89] | 19.87% [13.44, 27.11] |
| A content-token | 11/951 = 1.16% [0, 4.10] | 0% [0, 0] | 78.13% [69.75, 85.76] | 20.72% [13.64, 28.69] |
| T all-token | 87/951 = 9.15% [5.25, 13.74] | 4/951 = 0.42% [0, 1.46] | 69.72% [61.68, 77.54] | 20.72% [14.54, 27.55] |
| T content-token | 14/951 = 1.47% [0, 4.49] | 0% [0, 0] | 79.81% [71.61, 86.92] | 18.72% [12.24, 26.33] |

### 7.3 K1 中最重要的描述性变化

在 common-951 frame 上：

| 描述性差值（all-token - content-token） | A | T |
|---|---:|---:|
| Unsafe | +0.95 pp | +7.68 pp |
| Broken | 0.00 pp | +0.42 pp |
| Refusal | -0.11 pp | -10.09 pp |
| Safe | -0.84 pp | +2.00 pp |

A 点的四分类组成整体相近。T 点则出现明显的描述性重新分配：all-token 条件下 unsafe 增多、refusal 减少，而 broken 仍然很少。

这提供了一个重要解释：**T 点较强的 all-token 实际剂量，当前主要对应从 refusal 向 unsafe 的行为组成迁移，而不是进入大规模 broken/collapse。**

### 7.4 K1 的边界

- K1 的区间是各 cell 的 profile 区间，不是 all-token 与 content-token 的 contrast interval。
- 不能通过比较两个 cell-wise CI 是否重叠来替代正式配对推断。
- T 点 unsafe 不是预设 P2 primary member；不能在看到结果后把它替换成新的主要 estimand。
- K1 不改变 P2 两个 simultaneous CI 均包含 0 的事实。
- broken 为 0 的退化 bootstrap 区间只表示样本中没有观察到事件；不证明真实概率严格为 0。

---

## 8. 已完成结果能够回答什么

| 研究问题 | 当前答案 | 证据强度 |
|---|---|---|
| Token frame 是否改变 `mu` calibration？ | 是，all-token `mu` 约为 content-token 的 7.10 倍 | P1 primary gate PASS |
| Token frame 是否改变实际 intervention-dose geometry？ | 是，相同 `c` 对应约 7.1 倍的 `alpha` 差异 | P1 dose binding |
| A 点 unsafe 是否明确增加？ | 点估计为 +1.03 pp，但 CI 跨 0 | 不确定 |
| T 点 broken 是否明确增加？ | 点估计为 +0.41 pp，但 CI 跨 0 | 不确定 |
| 行为组成是否出现值得报告的模式？ | 是，K1 显示 T all-token 的 unsafe 更高、refusal 更低 | 描述性、非确认性 |
| Stage 3 是否证明 structural token/Attention Sink 导致 collapse？ | 否 | 设计没有该因果识别能力 |
| 结果是否适用于所有模型、层和攻击方法？ | 否 | 仅限固定 Qwen 条件 |

可以用于正文的当前核心句：

> Under the fixed Qwen setup, the token frame materially changes the measured calibration scale and intervention-dose geometry. The prespecified raw P2 behavioral contrasts are directionally positive but remain uncertain, while the K1 common-frame profile descriptively shows more unsafe and less refusal under all-token calibration at T.

---

## 9. 尚未完成实验

### 9.1 Harmful-clean：50 条

固定对 `D_behavior_confirm` 的 50 条 harmful prompts 各生成一条 vector-free、`alpha=0` clean response。

目标：

- 建立与 P2 harmful prompt frame 对齐的无 steering 行为 profile；
- 报告 unsafe、broken、refusal、safe 四分类比例；
- 使用 10,000 次 prompt bootstrap 形成描述性区间；
- 不产生新的 P2 arm 或检验 family。

当前状态：K1 owner inspection 已通过，下一步是实现 harmful-clean runner。现有 real smoke 已覆盖 clean backend 路径，不需要新增 development smoke。

### 9.2 Benign integrity：630 条

```text
benign clean       = 30 prompts x vector-free alpha=0 = 30
benign T-steered   = 30 prompts x 20 vectors          = 600
合计                                                    630
```

主要 estimand：

```text
d_p = mean_vector broken(p,v,T) - broken(p,clean)
RD_benign_broken = mean_prompt d_p
```

目标：检查 T-steered 条件是否损害 benign response integrity。使用 10,000 次 prompt bootstrap，报告点估计和两侧 95% CI。

它只能回答固定 30 prompts、20 vectors 和 Qwen T dose 下的 benign broken risk，不能建立一般安全性、无害性或等价性。

### 9.3 Fixed720 human validation

680 条剩余模型响应完成后，planned human-validation universe 才完整：

```text
P2                    4,000
harmful clean            50
benign T-steered        600
benign clean             30
planned universe      4,680
```

`4,680` 是计划响应数，不是预先保证的 eligible 数量。实际 eligibility 要在所有响应完成后，按唯一、完成且 judge-eligible 的 paper-run 输出确定。若实际 capacity 至少为 720，则使用固定 allocator 和 seed 42 确定性选择 720 条；不得在看到 gold 后换样或补样。若 capacity 小于 720，则按设计报告 `incomplete_capacity`，不形成 fixed720-complete claim。

人工工作量：

```text
两名 annotators 独立标注：2 x 720 = 1,440 assignments
第三人裁决所有分歧：D_adj，范围 0–720
总 assignment：1,440 + D_adj
```

目标：

- 计算 judge confusion matrix、precision、recall、F1；
- 检查 broken/unsafe 的识别质量；
- 形成 matched human-corrected P2 sensitivity；
- 如实报告质量限制，不根据结果更换 judge 或重选样本。

### 9.4 Two-phase corrected sensitivity

人工 gold 完成后，对 `P2-U(A)` 和 `P2-B(T)` 运行匹配的 two-phase correction：

- 9,999 次 prompt x phase-two synchronized replicates；
- 9,999 次 vector-aware sensitivity replicates；
- 输出 human-corrected point estimates 和 simultaneous intervals；
- 只作为 sensitivity analysis，不改变 raw P2 结果，也不形成确认性 decision。

---

## 10. 服务器恢复后的执行顺序

1. 实现 harmful-clean runner，并完成固定范围 owner review。
2. 正式运行 harmful-clean 50，检查结果并物化四分类 profile。
3. 实现并检查 benign runner。
4. 正式运行 benign clean 30 和 T-steered 600，物化 benign broken RD/CI。
5. 完整锁定 4,680-response human-validation universe，执行 fixed720 allocator。
6. 完成双人标注、分歧裁决和 judge quality audit。
7. 运行 two-phase human-corrected P2 sensitivity。
8. 更新 claim-evidence matrix、论文表格、图和最终 artifact manifest。

不需要重跑 P1、support、P2 或 K1。

---

## 11. 组会汇报建议

建议按以下顺序展示：

1. 先用 `mu_all/mu_content≈7.10` 说明 calibration 问题确实存在；
2. 用 `rho -> c -> alpha` 表解释为什么运行时 `c≈0.1` 并不代表 all-token dose 很小；
3. 展示 P2 两个点估计和同时区间，强调“可能有实际意义，但当前精度不足”；
4. 展示 K1 四分类表，说明 T 点变化主要表现为 unsafe 增加、refusal 减少，而非 broken 大幅增加；
5. 明确当前结论是 P1 明确、P2 不确定，避免把 K1 描述性结果升级为新 primary endpoint；
6. 最后报告尚余 680 个模型响应和 fixed720 human validation。

---

## 12. 结果文件与审查记录

### 正式结果

- P1 raw/result：`results/p1-qwen25-paper-20260807T044847Z/`
- P2 raw execution：`results/p2-qwen25-paper-20260808T051044Z/`
- P2 materialized result：`results/p2-materialized-qwen25-paper-20260808T051044Z-v1/p2_raw_result.json`
- K1 materialized result：`results/k1-materialized-qwen25-paper-20260808T051044Z-v1/k1_result.json`

### 负责人检查

- P1：`.codex-temp/stage3_p1_result_owner_inspection_v1/owner_inspection.md`
- Support：`.codex-temp/stage3_support_result_owner_inspection_v1/owner_inspection.md`
- P2：`.codex-temp/stage3_p2_result_owner_inspection_v1/owner_inspection.md`
- P2 materialization：`.codex-temp/stage3_controlled_p2_result_materialization_v1/run_report.md`
- K1：`.codex-temp/stage3_k1_result_owner_inspection_v1/owner_inspection.md`

### 写作边界

- `writing/paper1_writing_blueprint.md`
- `writing/paper1_claim_evidence_matrix.md`
- `writing/stage3 design/paper1_stage3_experiment_design.md`
