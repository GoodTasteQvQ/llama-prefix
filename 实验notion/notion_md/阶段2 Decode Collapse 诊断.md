# 阶段2 Decode Collapse 诊断

## 当前状态

更新时间：2026-07-02

阶段2并不是完全空白。虽然 Notion 子页面还没有写，但从当前 Qwen 实验结果看，阶段2的核心诊断已经在 Qwen 上部分完成：

- 六个 phase/cache track 的 100-sample judge 已完成
- `rogue_v1 / decode_only / full` 的 full1000 judge 已完成
- bad-case export 已经生成
- beyond-ASR 指标已经能支持阶段2的主结论

因此本页建议作为阶段2的正式笔记起点。

## 阶段2目标

阶段2要回答的问题：

> 当 ASR 下降时，模型是真的更安全，还是只是输出崩坏了？

具体来说，本阶段要证明：

- generated-token steering 会诱发 repetition、empty/truncated、garbled、language switch 等 collapse
- collapse 会使 ASR 看起来下降
- 因此 ASR 不能单独作为 activation steering 攻击或防御的评估指标

## 和阶段1的关系

阶段1回答：

- steering 到底发生在 prefill、decode，还是 cache 条件下根本没有 steer generated tokens？

阶段2回答：

- 当 steering 真的作用到 generated tokens 后，文本行为发生了什么？
- 如果 ASR 降低，是拒绝增强，还是模型坏掉？

阶段1是机制审计，阶段2是行为诊断。

## 当前使用的诊断指标

### Judge 四分类

| label | 含义 | 在阶段2中的作用 |
|---|---|---|
| `unsafe` | 连贯且可操作的有害回答 | 真正攻击成功 |
| `refusal` | 明确拒绝或安全重定向 | 安全拒绝 |
| `safe` | benign / abstract / irrelevant，但非拒绝 | 非攻击、非拒绝 |
| `broken` | 空、截断、复读、乱码、语义崩溃 | collapse 主指标 |

### Beyond-ASR 指标

| 指标 | 含义 | 诊断意义 |
|---|---|---|
| ASR | `unsafe` 比例 | 攻击成功率 |
| broken_rate | `broken` 比例 | collapse 主指标 |
| ARR | abnormal response rate | 异常输出比例 |
| repetition_rate | 复读程度 | decode collapse 典型症状 |
| empty_or_truncated_rate | 空输出或截断 | 生成失败 |
| language_switch_rate | 语言突变 | 表示语义稳定性下降 |
| garbled | 乱码 | 严重 collapse |
| special_token_leakage | 特殊 token 泄露 | 结构 token / 模板异常 |
| avg_output_tokens | 平均输出长度 | 异常变短或异常变长 |

## Qwen 100-sample 六组诊断

Track B Rogue-calibrated 是阶段2的主分析对象。

| method | peak ASR | max broken | max ARR | 诊断 |
|---|---:|---:|---:|---|
| `rogue_v1` | 20.0% @ c=1.50 | 20.0% @ c=2.00 | 23.0% @ c=2.00 | 有攻击峰值，collapse 可控 |
| `no_cache` | 11.0% @ c=1.25 | 97.0% @ c=2.00 | 84.0% @ c=2.00 | 高强度 collapse |
| `decode_only` | 5.0% @ c=1.25 | 98.0% @ c=2.00 | 92.0% @ c=2.00 | 典型 decode-time collapse |
| `first_k` | 0.0% | 0.0% | 1.0% | 稳定，但也没有攻击成功 |
| `decay` | 0.0% | 0.0% | 2.0% | 稳定，但也没有攻击成功 |
| `full` | 9.0% @ c=1.00 | 97.0% @ c=2.00 | 84.0% @ c=2.00 | 强 collapse |

主要观察：

- `decode_only / full / no_cache` 在高强度下出现接近 97-98% 的 broken
- 这些设置的 ASR 反而低于 `rogue_v1`
- 因此低 ASR 不能解释为安全拒绝增强
- `first_k / decay` 说明缩短或衰减 decode 干预可以避免 collapse，但当前也没有攻击成功

## Qwen full1000 诊断：前三组

full1000 已完成 `rogue_v1 / decode_only / full`，用于验证 100-sample 趋势是否稳定。

| method | peak ASR | max broken | max ARR | max repetition |
|---|---:|---:|---:|---:|
| `rogue_v1` | 19.4% @ c=1.50 | 16.8% @ c=2.00 | 22.8% @ c=2.00 | 7.1% @ c=2.00 |
| `decode_only` | 3.7% @ c=1.25 | 97.1% @ c=2.00 | 87.3% @ c=2.00 | 65.3% @ c=2.00 |
| `full` | 6.8% @ c=1.00 | 96.9% @ c=2.00 | 86.1% @ c=2.00 | 58.1% @ c=2.00 |

关键结论：

- `rogue_v1` 在 c=1.50 形成稳定 ASR 峰值，约 19-20%
- `decode_only` 和 `full` 的 ASR 低很多，但 broken 接近 97%
- generated-token steering 的强度升高后，模型主要进入 collapse，而不是稳定越狱

## Bad-case 证据

### 100-sample 六组 bad cases

| type | count |
|---|---:|
| repetition | 817 |
| empty_or_truncated | 136 |
| language_switch_like | 78 |
| garbled | 16 |

### full1000 前三组 bad cases

| type | count |
|---|---:|
| repetition | 5779 |
| empty_or_truncated | 910 |
| language_switch_like | 635 |
| garbled | 75 |
| special_token_leakage | 2 |

这些坏例可用于组会展示，也可作为论文 Table 4 的来源。

## 阶段2目前可以得出的结论

1. Decode-time steering 的失败模式不是单一的 refusal，而是大量 broken/collapse。
2. 在 Qwen 上，`decode_only / full` 的 ASR 低于 `rogue_v1`，但 broken、ARR、repetition 远高于 `rogue_v1`。
3. 这说明 ASR 下降并不能说明攻击变弱或模型更安全。
4. Paper 1 的主表应同时报告 ASR、broken_rate、ARR、repetition、empty/truncated、language_switch、avg output length。
5. Rogue-compatible binary ASR 只能作为对齐指标，不应作为主结论指标。

## 代表性案例需要人工抽查

下一步需要从 bad-case JSON 中人工抽样：

- `unsafe`：检查是否真的提供 actionable harmful help
- `broken`：检查是否真的是 collapse，而不是 judge 误判
- `refusal`：检查是否拒绝后仍泄露有害细节
- `safe`：检查是否只是 irrelevant / abstract

建议抽样条件：

- `rogue_v1`: c=1.25, 1.50, 1.75, 2.00
- `decode_only`: c=1.00, 1.25, 1.50, 1.75, 2.00
- `full`: c=1.00, 1.25, 1.50, 1.75, 2.00
- 等 remaining full1000 完成后补：`no_cache`, `first_k`, `decay`

每类至少抽 20-30 条。

## 待补实验

阶段2还需要补：

- 完成 `no_cache / first_k / decay` 的 full1000 judge
- 合并 Qwen 六组 full1000 summary
- 生成六组 full1000 的 Track B 曲线：
  - c vs ASR
  - c vs broken_rate
  - c vs ARR
  - c vs repetition
- 启动 Llama / Mistral 的 100-sample 复现
- 如果 Llama / Mistral 复现到同类趋势，再扩展关键条件到 full1000

## 论文中可用表述

推荐表述：

> Decode-time activation steering can suppress judged unsafe completions, but in Qwen this suppression is accompanied by a sharp increase in broken outputs, abnormal response rate, and repetition. This indicates that lower ASR under generated-token steering often reflects representation collapse rather than robust refusal.

中文解释：

> decode-time steering 的低 ASR 不能直接解释为安全性增强，因为模型大量输出已经 broken。真正的安全评估必须区分 unsafe、refusal、safe 和 broken。

