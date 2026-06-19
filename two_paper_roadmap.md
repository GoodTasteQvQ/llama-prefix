# Activation Steering 两篇论文路线图

## 总体判断

当前最稳妥的研究路线不是把所有内容压成一篇，而是拆成两篇：

- Paper 1：`mechanism audit / reproducibility + evaluation correction`
- Paper 2：`phase-aware defense method`

这样拆分后，第一篇不需要承担“动态防御一定优于所有方法”的方法创新负担，只需要把阶段语义、cache 语义、decode collapse 和评估失真这条证据链做扎实。第二篇则建立在第一篇发现之上，回答“既然 steering 的生效阶段决定结论，防御为何必须动态且 phase-aware”。

结论上：

- `可行性`：高
- `可发表性`：有，但两篇的目标层级不同
- `Paper 1`：更适合作为先导文章，强调复现审计、机制解释和评估修正
- `Paper 2`：如果实验完整，潜力明显高于 Paper 1

另一个必须显式纳入的前提是：Rogue 原始攻击强度协议是 `alpha = c * mu`，而不是单独扫描固定 `alpha`。因此后续所有计划都应并行保留两条实验线：

- `fixed-alpha semantic audit`
- `Rogue-faithful calibrated reproduction`

## Paper 1：机制审计 / 复现与评估修正

### 核心定位

Paper 1 不应写成“Rogue 作者代码有 bug，所以论文结论不成立”。更稳妥的表述应为：

- `under use_cache=True`，公开 Rogue v1 实现与 generation-time steering 的文字描述未完全对齐
- 当 steering 真正作用到 generated tokens 后，模型容易出现复读、乱码、输出崩溃等 collapse 现象
- Rogue 风格的 `mu` 标定对模板、padding、dtype 和 structural token 策略敏感，因此仅用 `ASR` 评估 activation steering 攻击或防御会系统性失真

这篇的主线应固定为三段：

1. 阶段语义审计：prefill / decode / cache 语义是否真的与文字描述一致
2. decode-time steering 的病态生成诊断：ASR 下降是否只是模型坏掉
3. 强度标定与评估修正：`mu` 的计算方式和 `ARR / repetition / special-token leakage / empty / latency` 一样都必须显式报告

### 贡献类型

这篇的贡献不在于“提出新攻击”或“提出新防御”，而在于：

1. reproducibility finding
2. mechanism-level explanation
3. evaluation correction beyond ASR

### 最低竞争力要求

不能只停留在 Qwen。至少需要覆盖：

- `Qwen2.5-7B-Instruct`
- `Llama-3.1-8B-Instruct`
- `Mistral-7B-Instruct-v0.3`

并且每个模型至少完成：

- phase matrix 关键对照
- decode collapse 诊断
- steering 强度敏感性曲线
- `mu` 敏感性曲线
- 统一 judge + summary 指标

如果最后结果显示 Qwen 对 decode steering 更敏感，而 Llama / Mistral 不完全同样，这不是负面结果。前提是需要给出合理解释，例如：

- chat template / role marker 差异
- tokenizer 与 structural token 分布差异
- hidden norm / attention sink 差异
- cache 语义或层结构差异

### 投稿定位

如果只做到：

- Rogue 单攻击
- 三模型
- phase matrix + collapse 诊断 + beyond-ASR 评估

则更适合：

- trustworthy AI / LLM safety / empirical ML systems 方向 workshop
- short paper
- 应用型会议或中上水平期刊

如果想冲更强安全期刊，仅这一篇通常还偏弱，因为它更像：

- `reproduction + measurement + evaluation critique`

## Paper 2：Phase-Aware Dynamic Activation Guard

### 核心定位

Paper 2 的逻辑建立在 Paper 1 上：

- Paper 1 发现：`when steering happens matters`
- Paper 2 提出：`phase-aware dynamic activation guard`

这里的方法主张不能写成“攻击者加了一个向量，我再减回去”。正确重述应为：

- 防御的是 `inference-time activation deviation`
- 不是只防 Rogue
- 也不是假设已知攻击向量本体
- 防御触发依据是当前激活落入异常方向，而不是“我知道攻击者加了什么”

### 方法表述

Paper 2 应强调以下设计：

- prefill 阶段只做轻量矫正
- decode 阶段只在异常投影越阈值时介入
- decode 介入只限于 `first-k` 或 `decay`
- 评分函数使用 `projection / norm-calibrated score`，而不是单纯余弦

方法贡献建议固定为三点：

1. phase-aware defense
2. norm-calibrated dynamic triggering
3. utility-preserving intervention over static steering

### 最大风险

如果写成“我把 Rogue 的随机向量抵消回去”，审稿人很容易定义为：

- 单攻击定制补丁
- 对攻击先验过强
- 缺乏一般化

因此必须把方法问题重新定义成：

- 针对推理期 activation deviation 的通用防御
- 用当前激活异常分数触发干预
- 不依赖显式知道攻击向量

### 投稿定位

如果完成以下最小包，Paper 2 才有更强投稿潜力：

- static vs dynamic defense
- harmful + harmless 双评估
- `ASR / UFR / FRR / ARR / repetition / utility / latency`
- 三模型
- 至少两类攻击设置：random steering + stronger steering variant
- layer / threshold / first-k / decay 消融

达到这个覆盖度后，Paper 2 才具备投更正式期刊或较强会议的基础。

## 两篇论文的解耦原则

为了避免两篇互相稀释，建议强制按以下方式解耦：

- Paper 1 只证明：
  - 阶段语义影响攻击与防御结论
  - `mu` 标定与 prompt / padding / dtype / structural token 设置共同影响攻击强度
  - `ASR` 不足以评估 activation steering
- Paper 2 才证明：
  - 因此需要 phase-aware dynamic defense
  - 动态防御相对静态防御具有更好的 safety-utility-collapse trade-off

Paper 1 不强行塞入完整防御主结果。
Paper 2 不再重复大量篇幅去做 Rogue 代码审计，只保留必要背景。

## 实验验收标准

### Paper 1 验收标准

至少满足：

- 三模型都有 `phase-aware reproduction matrix`
- 三模型都有 `fixed-alpha` 与 `Rogue-calibrated alpha = c * mu` 对照
- 明确报告 `use_cache=True` 与 `use_cache=False` 差异
- 明确报告 `decode-only` 修复后是否出现 collapse
- 明确报告 `mu` 对 system prompt、padding、dtype、structural token 过滤的敏感性
- 指标至少有：
  - `ASR`
  - `ARR`
  - `repetition rate`
  - `special-token leakage`
  - `empty/truncated`
  - `average output length`
  - `latency`
- 保留代表性坏样例
- 写作上不指责原作者，只写“公开 v1 实现与文字描述未完全对齐”

### Paper 2 验收标准

至少满足：

- defense 不是静态全程插入，而是明确 phase-aware
- 触发分数用 `projection score` 或等价的 norm-calibrated score
- 基线至少包含：
  - `no defense`
  - `static defense`
  - `prefill-only`
  - `decode-only`
  - `phase-aware first-k`
  - `phase-aware decay / gated`
- 同时报 harmful 与 harmless 结果
- 给出 utility 损失与 latency overhead
- 攻击强度协议必须显式写明 `c / mu / alpha`
- 至少证明：
  - dynamic defense 在相近安全收益下，utility loss 小于 static defense

## 推荐执行顺序

1. 先完成 Paper 1 的三模型 phase matrix
2. 再完成 Paper 1 的 decode collapse 与 beyond-ASR 评估
3. 写出 Paper 1 的机制发现和评估修正稿
4. 在 Paper 1 结论基础上，开始 Paper 2 的 defense 主实验
5. 完成 Paper 2 的 harmful / harmless / utility / latency 闭环
6. 最后补强攻击鲁棒性与跨模型泛化

阶段1正式实验代码入口应集中放在：

- [scripts/stage1_phase_aware/README.md](/D:/llama_prefix/scripts/stage1_phase_aware/README.md)

## 默认假设

- 默认目标是“先稳发，再冲更强”，不是第一篇就冲顶级安全期刊
- 默认 Paper 1 是 `reproducibility / mechanism / evaluation` 文章
- 默认 Paper 2 是方法文章，必须显式摆脱“把攻击向量减回去”的叙述
- 默认后续会把 Qwen 的现有结果扩展到 `Llama-3.1-8B-Instruct` 和 `Mistral-7B-Instruct-v0.3`
