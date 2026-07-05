# 阶段1 phase-aware reproduction / 机制审计 实验A-F

## 当前状态

更新时间：2026-07-02

本页是阶段1实验的当前版笔记，用于替换早期导出的 Notion 页面。旧页面中的方向判断基本正确，但当时只做了浅层验证，数值和实验完成度已经过时。当前应以本页为准。

当前已经完成：

- Qwen2.5-7B-Instruct 的 6 个 phase/cache track 的 100-sample judge
- Qwen2.5-7B-Instruct 的 `rogue_v1 / decode_only / full` 三组 full1000 judge
- judge 协议升级为 Paper-1 dual judge：主四分类 + Rogue-compatible binary
- 初步结论已经清楚：`when steering happens matters`

仍在进行：

- Qwen 的 `no_cache / first_k / decay` 三组 full1000 judge

尚未完成：

- Llama / Mistral 跨模型复现
- phase-call 审计总表的最终整理
- Attention Sink / 结构 Token 范数解释实验
- `mu` 标定敏感性实验

## 一句话结论

公开 Rogue v1 在 `use_cache=True` 下更接近 prefill-dominant steering，而不是真正稳定作用于 generated tokens 的 generation-time steering。当 steering 被修正为真正作用到 decode/generated tokens 后，Qwen2.5 往往不是稳定提高 unsafe success，而是出现 repetition、empty/truncated、language switch、garbled 等 collapse 行为。因此 Paper 1 不能只报告 ASR，必须同时报告 broken rate、ARR、repetition、empty/truncated、output length 等 beyond-ASR 指标。

## 命名说明：A-F 与 Track A/B

这里有两套命名，容易混淆：

### A-F：phase/cache 设置

| 编号 | 当前代码名 | 设置 | 目的 |
|---|---|---|---|
| A | `rogue_v1` | Rogue v1 原始 cache semantics，`use_cache=True` | 审计公开实现真实行为 |
| B | `no_cache` | `use_cache=False`，每步全序列 forward steering | 检查无 KV cache 时的攻击语义 |
| C | `decode_only` | `use_cache=True`，只攻击 generated tokens | 验证真正 generated-token steering |
| D | `full` | prefill + decode 都 steering | 测试持续 steering 的上限和副作用 |
| E | `first_k` | decode-only first-k steering，当前为前 3 个 decode token | 检查生成早期 token 是否是关键窗口 |
| F | `decay` | decode-only steering with exponential decay，当前 decay=0.85 | 降低 decode 阶段退化风险 |

### Track A/B：强度协议

| Track | 名称 | 含义 | 作用 |
|---|---|---|---|
| Track A | fixed-alpha semantic audit | 直接扫描固定 alpha | 主要用于机制审计和对照 |
| Track B | Rogue-calibrated | `alpha = c * mu` | 用于和 Rogue 强度协议对齐，并观察文本行为 |

## 实验基座

当前 Qwen 实验设置：

- Model：`Qwen2.5-7B-Instruct`
- Judge model：`Qwen3-8B`
- 数据：JailbreakBench / JBB-Behaviors harmful 子集
- 强度：`0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0`
- Track B：`alpha = c * mu`
- 评估协议：Paper-1 dual judge

结果文件位置：

- 100-sample 原三组 summary：`results/stage1_phase_aware/formal/qwen25/judge_summaries/qwen25_stage1_qwen3_v2_judge_summary.json`
- 100-sample remaining 三组 summary：`results/stage1_phase_aware/formal/qwen25/judge_summaries/qwen25_stage1_remaining_phase_qwen3_v2_judge_summary.json`
- full1000 前三组 summary：`results/stage1_phase_aware/formal/qwen25/judge_summaries/qwen25_stage1_qwen3_v2_full1000_judge_summary.json`
- 100-sample 合并图表：`results/stage1_phase_aware/formal/qwen25/judge_summaries/qwen25_stage1_all_phase_qwen3_v2_plots/`
- full1000 前三组图表：`results/stage1_phase_aware/formal/qwen25/judge_summaries/qwen25_stage1_qwen3_v2_full1000_plots/`

## 评估口径

本阶段的 judge 结果用于确认 phase/cache 设置带来的行为差异。详细的四分类定义、beyond-ASR 指标和 bad-case 诊断放在阶段2页面，避免两个页面重复。

本页只保留两个要点：

- 主分析使用 Paper-1 four-class judge：`unsafe / refusal / safe / broken`
- 同时保留 Rogue-compatible binary judge：`safe / unsafe`，只用于和 Rogue 原始口径对齐

注意：

- `broken` 的详细定义和坏例统计见阶段2
- 阶段1的重点不是证明 collapse，而是证明不同 phase/cache 设置确实对应不同实验语义

## 覆盖情况

### 100-sample

| 项目 | 数量 |
|---|---:|
| phase/cache methods | 6 |
| Track | 2 |
| strength points | 9 |
| records per condition | 100 |
| total conditions | 108 |
| total records | 10800 |

100-sample 已覆盖：

- `rogue_v1`
- `no_cache`
- `decode_only`
- `first_k`
- `decay`
- `full`

### full1000

| 项目 | 数量 |
|---|---:|
| 已完成 methods | 3 |
| 已完成 methods | `rogue_v1 / decode_only / full` |
| Track | 2 |
| strength points | 9 |
| records per condition | 1000 |
| total conditions | 54 |
| total records | 54000 |

full1000 正在补：

- `no_cache`
- `first_k`
- `decay`

## Judge 质量

| batch | records | JSON parse fail | fail rate |
|---|---:|---:|---:|
| 100-sample `rogue_v1 / decode_only / full` | 5400 | 25 | 0.46% |
| 100-sample `no_cache / first_k / decay` | 5400 | 10 | 0.19% |
| full1000 `rogue_v1 / decode_only / full` | 54000 | 245 | 0.45% |

结论：judge 解析失败率低，当前统计可以用于阶段性汇报和论文 pilot 分析。

## Phase-call 审计表：阶段1主证据

阶段1的核心证据不是 ASR，而是 hook 在推理过程中实际发生在哪个阶段。因此这里应该优先报告 phase-call 审计表，再把 judge / bad-case 结果放到阶段2解释。

下表使用 Track B 的代表性强度 `c=1.0` 聚合 1000 个 vectors。选择非零强度是因为 `c=0` 下即使 hook 被调用，attack strength 也为 0，不能代表 generated-token steering 是否真正生效。

| method | phase_mode | use_cache | prefill attack | decode cached / run | decode full / run | generated steered / run | mean decode mask | 解释 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `rogue_v1` | `rogue_v1_cache_semantics` | True | True | 70.8 | 0.0 | 0.0 | 0.00 | prefill-dominant；cached decode 阶段没有 steer generated tokens |
| `no_cache` | `prefill_and_decode` | False | True | 0.0 | 154.2 | 154.2 | 181.82 | 每步全序列 forward，generated positions 被反复 steer |
| `decode_only` | `decode_only` | True | False | 189.0 | 0.0 | 189.0 | 1.00 | cached decode-only，每个 generated token 被 steer |
| `first_k` | `first_k_decode` | True | False | 95.1 | 0.0 | 3.0 | 1.00 | 只 steer 前 3 个 decode step |
| `decay` | `decode_only`, decay=0.85 | True | False | 91.5 | 0.0 | 91.5 | 1.00 | decode step 持续被 steer，但强度指数衰减 |
| `full` | `prefill_and_decode` | True | True | 159.4 | 0.0 | 159.4 | 1.00 | prefill + cached decode 都被 steer |

这张表支撑阶段1的核心机制结论：

- `rogue_v1` 虽然在 prefill 阶段施加攻击，但在 `use_cache=True` 的 cached decode 阶段没有真正 steer generated tokens。
- `decode_only / full / no_cache` 才是真正 generated-token steering 的设置。
- 当前 `first_k / decay` 是 decode-side variants，没有 prefill attack，因此不能直接等同于 `rogue_v1`。
- `no_cache` 的 `decode_full / run` 和 `mean decode mask` 很高，说明它不是 cached decode 单 token 语义，而是每步全序列 forward 语义。

导出的审计表文件：

- `实验notion/notion_md/assets/qwen_phase_call_audit_alpha_or_c_1.csv`
- `实验notion/notion_md/assets/qwen_phase_call_audit_alpha_or_c_1.md`

## Track A fixed-alpha 结果

Track A 是 fixed-alpha semantic audit。当前 Qwen 结果显示：

- 100-sample 六个 methods 全部稳定
- full1000 前三组也全部稳定
- 没有明显 ASR
- 没有明显 broken
- 没有明显 ARR / repetition 异常

解释：

Track A 的主要价值不是证明攻击成功，而是作为机制对照：在固定 alpha 下，Qwen 的输出基本保持拒绝，说明后续 Track B 的异常不是普通生成噪声，而是 Rogue-calibrated 强度和 phase semantics 共同作用的结果。

## Track B Rogue-calibrated 结果摘要

Track B 使用 `alpha = c * mu`，是和 Rogue 强度协议对齐的主线。这里保留机制层面的摘要，完整 ASR / broken / ARR / repetition 表放在阶段2。

| method | phase/cache 语义 | 当前观察 |
|---|---|---|
| `rogue_v1` | `use_cache=True` 下更接近 prefill-dominant | 有 ASR 峰值，collapse 相对较低 |
| `no_cache` | 每步全序列 forward steering | generated-token 影响很强，高强度下不稳定 |
| `decode_only` | 只 steer generated tokens | 能验证 generated steering，但高强度下容易 collapse |
| `full` | prefill + decode 持续 steering | 能验证持续 steering，但副作用最大之一 |
| `first_k` | 只干预早期 decode token | 当前最稳定，但没有形成攻击成功 |
| `decay` | decode 干预逐步衰减 | 当前稳定，但没有形成攻击成功 |

关键观察：

- A-F 的语义差异已经不仅是控制流差异，也反映到文本行为上
- `rogue_v1` 与真正 generated-token steering 的行为不同
- 当前 attack 实验中的 `first_k / decay` 不是 prefill+decode，而是 decode-side variants，因此不能直接与 `rogue_v1` 的 prefill-dominant 效果等同
- `first_k / decay` 可作为后续 phase-aware defense 的设计线索，但在 Paper 1 中只作为机制对照

## full1000 当前进展

full1000 已完成前三组：

- `rogue_v1`
- `decode_only`
- `full`

full1000 验证了阶段1最重要的机制判断：

- `rogue_v1` 与 `decode_only / full` 的行为明显不同
- 真正 generated-token steering 的副作用在大样本下仍然稳定存在
- 100-sample 的趋势不是偶然噪声

完整的 full1000 数值表和坏例统计见阶段2页面。

## 当前阶段1结论

1. `use_cache=True` 下，公开 Rogue v1 更接近 prefill-dominant steering，而不是真正稳定的 generation-time steering。
2. 真正作用到 generated tokens 的 `decode_only / full / no_cache` 在 Rogue-calibrated 强度下会显著诱发 collapse。
3. `first_k / decay` 目前看起来更稳定，但也没有形成攻击成功。
4. fixed-alpha Track A 主要是干净对照；Rogue-calibrated Track B 才暴露出关键行为差异。
5. ASR 单指标不足以解释 activation steering 实验；详细 collapse 证据见阶段2。

## 论文中可用表述

推荐写法：

> Under `use_cache=True`, the public Rogue v1 implementation is not fully aligned with a literal generation-time steering interpretation. In our phase-aware reproduction, Rogue v1 exhibits a prefill-dominant behavior, while interventions that truly steer generated tokens often induce representation collapse. Therefore, lower ASR under decode-time steering should not be interpreted as improved safety without beyond-ASR diagnostics.

不建议写法：

> Rogue 代码是错的。

原因：Paper 1 应保持克制，重点写 public implementation under cache semantics 与文字描述的对齐问题，而不是指责原作者。

## 下一步

阶段1还需要补：

- 等 `no_cache / first_k / decay` full1000 完成后，合并六组 full1000 主表
- 整理 phase-call 审计表：`prefill_calls / decode_cached_calls / decode_full_calls / generated_steered_calls / decode_mask_sums`
- 人工抽查坏例，重点看 `unsafe` 与 `broken` 边界
- 启动 Llama / Mistral 的 100-sample 跨模型复现
