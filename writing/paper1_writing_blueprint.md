# Paper 1 写作蓝图

## 暂定标题

可选标题：

- When Steering Happens Matters: Cache-Aware Reproduction and Evaluation of Activation Steering Attacks
- Beyond ASR: Phase Semantics and Representation Collapse in Activation Steering Attacks
- Cache Semantics Matter: Auditing Generation-Time Activation Steering Under `use_cache=True`

推荐主标题方向：

> When Steering Happens Matters: Cache-Aware Reproduction and Beyond-ASR Evaluation for Activation Steering Attacks

## 一句话主张

公开 Rogue v1 实现在 `use_cache=True` 下与 generation-time steering 的文字描述未完全对齐；当 steering 真正作用到 generated tokens 后，模型容易出现 collapse，因此 activation steering 不能只用 `ASR` 评估。

## 摘要骨架

摘要建议固定为四句话：

1. 背景句：activation steering 正在成为大模型安全中的重要攻击面，但其实验结论高度依赖推理阶段语义。
2. 发现句：我们审计公开 Rogue v1 实现，发现其在 `use_cache=True` 下更接近 prefill-dominant steering，而不是真正稳定的 generation-time steering。
3. 诊断句：当 steering 被修复为真正作用于 generated tokens 时，虽然 `ASR` 可能下降，但模型会显著出现复读、乱码、special-token leakage 和输出崩溃。
4. 结论句：因此仅用 `ASR` 会系统性高估攻击或防御效果，我们提出一套 beyond-ASR 的评估协议，并在 Qwen、Llama、Mistral 上验证这一现象。

## 章节结构

### 1. Introduction

这节回答三个问题：

- activation steering 为什么值得关注
- 为什么当前文献容易忽视 prefill / decode / cache 语义
- 这篇文章解决什么问题

结尾固定写三点贡献：

1. 揭示公开 Rogue v1 在 `use_cache=True` 下的阶段语义错位
2. 证明 generated-token steering 容易引发 representation collapse，`ASR` 单指标不足
3. 给出一套 beyond-ASR 的评估框架和多模型证据

### 2. Background

内容只保留最必要部分：

- activation steering / representation engineering 的基本形式
- prefill / decode / KV cache 的推理语义
- Rogue 类攻击的基本思想

这节不要讲防御方法细节，避免和 Paper 2 混在一起。

### 3. Threat Model and Reproduction Target

这一节非常关键，必须明确：

- 本文研究的是 `inference-time activation steering attack`
- 不是 prompt jailbreak
- 不是“攻击者可任意篡改服务端所有代码”的最强白盒
- 复现目标是“审计公开实现 under real cache semantics”

这一节还应明说：

- 我们不判断原论文是否“错误”
- 我们只判断公开实现与文字描述在特定运行语义下是否对齐

### 4. Phase-Aware Reproduction Audit

这是正文核心第一部分。

建议分四个小节：

1. `Rogue v1 under use_cache=True`
2. `No-cache full-sequence steering`
3. `Decode-only / prefill+decode / first-k / decay`
4. `Cross-model comparison`

这里的重点不是 `ASR`，而是：

- `prefill_calls`
- `decode_cached_calls`
- `decode_full_calls`
- `generated_steered_calls`
- `decode_mask_sums`

### 5. Decode-Time Collapse and Beyond-ASR Evaluation

这是正文核心第二部分。

分三块写：

1. decode-only steering 的病态输出现象
2. 为什么 `ASR` 会误导
3. beyond-ASR 评估指标

这里要重点引入：

- `ARR`
- `repetition rate`
- `special-token leakage`
- `empty/truncated`
- `avg output length`
- `latency`

### 6. Explaining Model Differences

这一节用于消化 Qwen / Llama / Mistral 的差异，避免结果看起来像“只是不同模型不稳定”。

重点解释：

- chat template / role marker
- tokenizer / structural token
- hidden norm / attention sink
- cache 语义与层结构差异

attention sink 的分析结果放在这里最合适。

### 7. Discussion

这里集中讨论三件事：

- 为什么 activation steering 研究必须区分 prefill 和 decode
- 为什么安全评估不能只看 `ASR`
- 这对后续防御设计意味着什么

结尾可以自然引出：

> These findings motivate phase-aware defensive interventions, which we study in follow-up work.

这样就能把 Paper 2 顺滑接上。

### 8. Limitations

建议主动写清楚：

- 目前主要围绕 Rogue 风格攻击
- 更强优化攻击仍需进一步验证
- utility benchmark 仍可能进一步扩展

主动写限制，反而更稳。

## 图表清单

### 主文图

Figure 1. Activation steering 在 prefill / decode / cache 语义下的示意图  
用途：帮助读者一眼理解“为什么同样的 hook 在 cache 条件下语义会变”

Figure 2. Qwen phase matrix A-F 的阶段调用统计图  
用途：展示 `generated_steered_calls` 与 `mask_sum` 的区别

Figure 3. 三模型 phase-aware reproduction 对比图  
用途：展示 Qwen / Llama / Mistral 是否都存在类似语义差异

Figure 4. decode steering 强度敏感性曲线  
用途：展示 steering coefficient 对 `ASR` 和 `ARR` 的影响

Figure 5. `ASR` vs `ARR` / repetition 的联合图  
用途：直接证明“低 ASR 可能只是模型坏掉”

Figure 6. attention sink / structural token norm 可视化  
用途：解释 Qwen 为何更敏感

### 主文表

Table 1. Phase matrix A-F 设置总表  
列：phase mode、`use_cache`、是否 steer generated token、预期语义

Table 2. 三模型 reproduction 审计结果表  
列：`prefill_calls`、`decode_cached_calls`、`generated_steered_calls`、`mean latency`

Table 3. Beyond-ASR 评估表  
列：`ASR`、`ARR`、`repetition rate`、`special-token leakage`、`avg output length`

Table 4. 代表性坏样例归类表  
列：repetition、garbled、special-token leakage、empty、language switch

## 实验到章节映射

### 章节 4 对应实验

- phase matrix A-F
- `use_cache=True` vs `use_cache=False`
- 三模型关键对照

### 章节 5 对应实验

- decode-only / full / first-k / decay 的 harmful judge
- bad-case export
- beyond-ASR summary
- steering 强度敏感性曲线

### 章节 6 对应实验

- attention sink 策略 sweep
- chat template / structural token 过滤对比
- 模型间结构 token 分布差异

## 最小必跑结果

如果只保最小成稿包，优先保证下面这些结果完整：

1. 三模型 `Rogue original vs fixed decode hook`
2. 三模型 `prefill-only / decode-only / prefill+decode`
3. decode collapse 诊断
4. beyond-ASR summary
5. attention sink 解释结果

这五组结果做扎实，Paper 1 就能独立成立。

## 写作提醒

- 不要把文章写成“作者代码有 bug”
- 用“public v1 implementation is not fully aligned under `use_cache=True`”这种克制措辞
- 不要在 Paper 1 里展开完整 defense 主实验，只做轻量动机铺垫
- 所有核心结论都要尽量由多模型结果支撑，而不是只靠 Qwen

