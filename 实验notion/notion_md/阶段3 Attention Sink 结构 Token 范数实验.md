# 阶段3 Attention Sink / 结构 Token 范数实验

## 当前状态

更新时间：2026-07-02

阶段3目前还没有正式完成结果，应作为下一步机制解释实验。它的作用不是继续证明 collapse 存在，而是解释为什么 Qwen 对 Rogue-calibrated decode/full steering 特别敏感，以及为什么 `mu` 标定可能受到 chat template、padding、结构 token 和 hidden norm 异常影响。

## 阶段3目标

阶段3要回答的问题：

> Qwen 上为什么会出现强烈的 decode-time collapse？Rogue-calibrated `mu` 是否受到结构 token / attention sink / hidden norm 异常的影响？

这个阶段对应 Paper 1 的解释部分：

- chat template / role marker
- tokenizer / structural token
- hidden norm / attention sink
- `mu` 标定敏感性

## 为什么需要阶段3

阶段1和阶段2已经说明：

- `rogue_v1` 与真正 generated-token steering 行为不同
- `decode_only / full / no_cache` 在 Qwen 上会强烈 collapse
- `first_k / decay` 更稳定

但是审稿人可能会问：

- 这是不是 Qwen 特例？
- 为什么 Qwen 对 decode steering 特别敏感？
- `alpha = c * mu` 中的 `mu` 是否被少数结构 token 放大？
- 不同 chat template / padding / dtype 会不会改变结论？

阶段3就是用来回答这些问题。

## 核心假设

当前假设：

1. Qwen chat template 中的结构 token / role marker / assistant preamble 可能具有异常高 hidden norm。
2. left padding 与前若干 token 的处理方式会影响 Rogue-style `mu` 估计。
3. 如果 `mu` 被 attention-sink-like token 拉高或拉低，最终 `alpha = c * mu` 会改变攻击强度。
4. 结构 token 过滤策略不同，会导致 Track B 曲线变化。
5. Qwen / Llama / Mistral 的 tokenizer 与 chat template 差异，可能解释模型间 collapse 敏感性不同。

## 已有工具

当前代码中已有两个相关脚本：

### `scripts/stage1_phase_aware/measure_activation_norm.py`

用途：

- 按 Rogue 风格测量某层平均激活范数 `mu`
- 当前默认逻辑：
  - filter special tokens
  - drop first k valid tokens
  - 记录 valid / kept positions

输出应关注：

- `mu`
- `valid_token_count`
- `kept_token_count`
- `norms`
- `kept_positions`
- prompt 渲染后的文本

### `scripts/analyze_attention_sink.py`

用途：

- 检查 high-norm structural tokens
- 比较不同 token filtering strategies
- 比较不同 aggregators

已有策略：

- `no_filter`
- `special_only`
- `role_markers`
- `newline`
- `role_and_newline`
- `all_structural`

已有聚合：

- `mean`
- `trimmed_mean`
- `median`

## 实验3.1：hidden norm / attention sink 分析

### 目标

找出 Qwen prompt 中 hidden norm 最大的 token，并判断它们是否集中在：

- special token
- role marker
- newline
- assistant preamble
- chat-template structural token
- padding-adjacent token
- prompt 开头若干 token

### 建议设置

模型：

- Qwen2.5-7B-Instruct

层：

- 当前主实验层
- 额外选 1/3 depth、1/2 depth、2/3 depth

数据：

- JBB harmful prompts
- 先用 32 或 100 条即可

输出：

- 每层 top-k high-norm tokens
- token text
- token position
- token type
- norm value
- 是否被当前 filtering strategy 保留

### 需要记录的表

| layer | strategy | aggregator | mean norm | median norm | max norm | top token type | top token text |
|---:|---|---|---:|---:|---:|---|---|

## 实验3.2：`mu` 标定敏感性实验

### 目标

证明 `mu` 不是稳定常数，而是会随 prompt formatting、padding、dtype、结构 token 过滤策略变化。

### 对照因素

| factor | values |
|---|---|
| system prompt | empty / default / explicit safety system |
| padding side | left / right |
| structural token filter | no filter / special only / role marker / newline / all structural |
| aggregator | mean / trimmed mean / median |
| dtype | bf16 / fp32 |
| drop first valid tokens | 0 / 5 |

### 输出表

| setting | mu | alpha at c=1.0 | alpha at c=1.5 | valid tokens | kept tokens | comment |
|---|---:|---:|---:|---:|---:|---|

## 实验3.3：filtering strategy 对 ASR / collapse 的影响

### 目标

如果 `mu` 标定因结构 token 改变，那么最终 Track B 的行为也应改变。需要验证：

- 不同 filtering strategy 是否改变 `alpha`
- 是否改变 ASR 峰值
- 是否改变 broken / ARR / repetition

### 最小运行建议

不需要一开始全量跑 9 个强度。先选关键点：

- method：`rogue_v1`, `decode_only`, `full`
- c：`1.0`, `1.25`, `1.5`, `2.0`
- sample：100
- model：Qwen2.5

### 输出表

| strategy | method | c | mu | alpha | ASR | broken | ARR | repetition |
|---|---|---:|---:|---:|---:|---:|---:|---:|

## 实验3.4：跨模型结构 token 对比

### 目标

为 Paper 1 的跨模型差异提供解释。

比较：

- Qwen2.5-7B-Instruct
- Llama-3.1-8B-Instruct
- Mistral-7B-Instruct-v0.3

关注：

- chat template token 分布
- role marker tokenization
- special token 数量
- high-norm token 是否集中于结构 token
- `mu` 分布是否更极端
- filtered / unfiltered `mu` 差异是否更大

### 输出表

| model | layer | no-filter mu | all-structural-filter mu | ratio | max norm token type | comment |
|---|---:|---:|---:|---:|---|---|

## 当前优先级

阶段3不应该抢在 Qwen full1000 完整合并之前大规模运行。建议顺序：

1. 等 `no_cache / first_k / decay` full1000 完成并合并
2. 人工抽查阶段2 bad cases
3. 启动 Llama / Mistral 100-sample 复现
4. 同时做 Qwen 的 hidden norm / `mu` 敏感性小实验
5. 如果 Qwen 机制解释清楚，再扩展到 Llama / Mistral

## 组会可汇报的当前状态

可以这样说：

> 阶段3目前还没有形成正式结果，但它是解释阶段1和阶段2现象的下一步。Qwen 上 decode/full steering 的 collapse 已经非常明显，下一步需要检查是否由 chat-template structural tokens、attention-sink-like high-norm tokens 或 Rogue-style `mu` 标定敏感性导致。代码中已经有 `measure_activation_norm.py` 和 `analyze_attention_sink.py` 两个入口，可以先做小规模 norm/mu 分析，再决定是否跑生成实验。

## 预期论文贡献

阶段3如果跑通，可以支持 Paper 1 第 6 节：

> Explaining Model Differences

可能形成的论点：

- Qwen 的结构 token / assistant preamble 可能更容易形成 high-norm activations
- Rogue-calibrated `mu` 对 token filtering 和 template 很敏感
- decode-time steering 的 collapse 不只是“强度太大”，也可能与结构 token 范数异常和 cache semantics 交互有关
- 这解释了为什么 activation steering 实验必须记录 chat template、padding side、filtering strategy、dtype 和 `mu` 计算方式

