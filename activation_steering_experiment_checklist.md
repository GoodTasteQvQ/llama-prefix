# Activation Steering 防御课题实验清单

当前实验清单按两篇论文组织：

- `Paper 1`：机制审计、复现与评估修正
- `Paper 2`：phase-aware dynamic activation guard

整体路线见 [two_paper_roadmap.md](/D:/llama_prefix/two_paper_roadmap.md)。

阶段1正式入口见 [scripts/stage1_phase_aware/README.md](/D:/llama_prefix/scripts/stage1_phase_aware/README.md)。

本文档归档下一阶段需要完成的实验内容。实验目标不是继续零散调参，而是形成一条能支撑论文主线的证据链：

> Activation steering 攻击与防御的结论高度依赖 prefill / decode / `use_cache` 的生成阶段语义。本文需要系统证明这种阶段差异，并提出 phase-aware、norm-calibrated 的动态激活防御。

另一个必须纳入的控制变量是 Rogue 的攻击强度协议：

- `fixed-alpha`
- `alpha = c * mu`

凡是声称“与 Rogue 结果可比”的实验，都必须使用 `alpha = c * mu`。

## P0. 固定实验基座

这一部分优先级最高。后续所有结果都应在统一基座上运行，否则不同曲线之间很难严谨比较。

### P0.1 固定模型

1. `Qwen2.5-7B-Instruct`
2. `Llama-3/3.1-8B-Instruct`
3. `Mistral-7B-Instruct-v0.3`

### P0.2 固定随机性与生成参数

每组实验记录：

- random seed：至少 3 个，最好 5 个，（其中一个是42）
- `temperature`
- `top_p`
- `top_k`
- `max_new_tokens`
- `do_sample`
- `repetition_penalty`
- `eos_token_id`
- `pad_token_id`

### P0.3 固定输入模板与 tokenizer 设置

必须记录：

- chat template
- system prompt 是否为空
- padding side
- truncation side
- special token 过滤规则
- system / user / assistant marker 是否过滤
- newline token 是否过滤
- attention mask

特别注意：Qwen 与 Llama 的 padding、chat template、结构性 token 分布不同，必须作为控制变量。

### P0.4 固定数据集划分

建议划分：

- train：用于提取 safety vector
- validation：用于选择阈值、层、`k`、`base0`
- test：只用于最终评估，不能调参

数据类型：

- harmful prompts
- harmless prompts
- jailbreak prompts
- normal utility prompts
- 中文正常任务，尤其用于 Qwen

### P0.5 每次实验必须保存的日志

每条样本保存：

- prompt 原文
- token ids
- attention mask
- decoded tokens
- hook 层
- hook 阶段：prefill / decode
- `prefill_calls`
- `decode_calls`
- `generated_steered_calls`
- 每次 hook 的 `seq_len`
- 每次 hook 的 `mask_sum`
- steering coefficient
- hidden norm
- projection score
- 输出文本
- ASR 判定
- UFR / FRR 判定
- ARR 判定
- repetition 判定
- special-token leakage 判定

## Paper 1. Rogue 攻击阶段语义复现实验

### 目标

证明 Rogue 攻击效果强烈依赖 prefill / decode / `use_cache` 语义。该实验是论文中“问题发现”部分的核心。

### P1.1 Phase-aware attack reproduction matrix

固定模型、层、随机种子、chat template、padding、mask、steering norm 归一化方式，比较以下条件：


| 编号  | 设置                                                   | 目的                          |
| --- | ---------------------------------------------------- | --------------------------- |
| A   | Rogue v1 原始代码，`use_cache=True`                       | 复现公开代码真实行为                  |
| B   | `use_cache=False`，每步全序列 forward steering             | 检查无 KV cache 时的攻击语义         |
| C   | `use_cache=True`，修复 decode hook，只攻击 generated tokens | 验证真正 generated steering 的效果 |
| D   | prefill + decode 都 steering                          | 测试持续 steering 的上限和副作用       |
| E   | prefill + first-k decode steering                    | 检查生成早期 token 是否是关键窗口        |
| F   | prefill + decode decay steering                      | 降低 decode 阶段退化风险            |

本组实验应拆成两条并行线：

- `Track A`: `fixed-alpha semantic audit`
- `Track B`: `Rogue-calibrated alpha = c * mu`


### P1.2 层与强度设置

层选择：

- `1/3 depth`
- `1/2 depth`
- `2/3 depth`
- 额外加入已有实验中发现的 best layers
  - Qwen：例如 layer 9 / 14 / 18
  - Llama：已有实验中安全/攻击敏感层
  - Mistral：已有实验中 best layer，例如 layer 13 附近

攻击强度：

- `fixed-alpha` 线：
  - `0.0`
  - `0.25`
  - `0.5`
  - `0.75`
  - `1.0`
  - `1.25`
  - `1.5`
  - `1.75`
  - `2.0`
- `Rogue-calibrated` 线：
  - `c = 0.25`
  - `c = 0.5`
  - `c = 0.75`
  - `c = 1.0`
  - `c = 1.25`
  - `c = 1.5`
  - `c = 1.75`
  - `c = 2.0`

并且每个点都必须记录：

- `mu`
- `alpha = c * mu`
- `mu` 的计算设置

### P1.3 评估指标

每组报告：

- ASR
- refusal rate
- UFR / FRR
- ARR
- repetition rate
- special token leakage
- EOS 过早结束率
- 平均输出长度
- latency overhead

### P1.4 预期产物

- 一张 phase matrix 总表
- 每个模型的 ASR 曲线
- 每个模型的 ARR 曲线
- 每个模型的 `mu` 敏感性表
- prefill-only 与 decode-steering 的对比图
- 代表性输出样例

## Paper 1. μ 标定敏感性实验

### 目标

证明 Rogue 的 `mu` 不是稳定常数，而是会受 prompt formatting、padding、dtype 与 structural token 过滤策略影响，从而改变最终 `alpha` 和 ASR。

### P1.4a 对照因素

- system prompt：有 / 无
- padding side：left / right
- structural token 策略：
  - no filter
  - special-only
  - role markers
  - newline
  - all structural
- dtype：
  - `float32`
  - `bfloat16`，硬件允许时

### P1.4b 运行方式

每个因素都要跑两组：

- `fixed-alpha control`
- `Rogue-calibrated alpha = c * mu`

### P1.4c 输出

至少报告：

- `mu`
- `alpha`
- ASR
- ARR
- repetition
- avg output length

并明确区分：

- `mu` 变化导致的间接效应
- prompt / dtype / padding 本身导致的直接效应

## Paper 1. Decode Steering 退化诊断实验

### 目标

证明 ASR 降低不等于防御成功。直接对 generated tokens 进行 steering 可能只是破坏模型生成能力，而不是提升安全性。

### P1.5 对比设置

重点在 Qwen 和 Llama 上做：

1. prefill-only steering
2. decode-only steering
3. prefill + decode steering
4. first-1 decode token steering
5. first-3 decode token steering
6. first-5 decode token steering
7. first-10 decode token steering
8. decode steering with exponential decay

### P1.6 退化指标

记录：

- ARR
- repetition rate
- special token leakage
- EOS 过早结束率
- 平均输出长度
- 输出为空比例
- 语言切换比例
- 控制符泄露比例
- 自相矛盾回答比例

### P1.7 代表性坏样例

每个模型至少保存 10 个典型异常输出，包括：

- 复读
- 乱码
- 特殊 token 泄露
- 空输出
- 过早停止
- 拒绝后又继续给有害步骤
- 先顺从再拒绝
- 语言突变

### P1.8 预期论点

该实验应支持以下论断：

> Generated-token steering may suppress unsafe completions, but it can also induce representation collapse. Therefore, ASR alone is insufficient for evaluating activation-level defenses.

## Paper 1 / Paper 2 共享：Safety Vector 质量验证实验

### 目标

证明 safety vector 是稳定、可解释、可迁移的，而不是偶然从小数据集中提取出的方向。

### P1.9 数据规模实验

分别使用以下数据规模提取 safety vector：

- 100 对
- 200 对
- 500 对
- 1000 对
- 2000 对，如果算力允许

每个规模记录：

- harmful / harmless 投影分布
- projection distance
- AUROC
- vector cosine similarity between scales
- best layer 是否变化

### P1.10 层扫描实验

对每个模型逐层计算：

- harmful projection mean
- harmless projection mean
- separation distance
- AUROC
- within-class variance
- between-class distance

输出：

- 每层 separation 曲线
- 每层 AUROC 曲线
- best layer 表格

### P1.11 模型对比实验

至少比较：

- Llama
- Qwen
- Mistral

目标是证明不同模型内部安全方向强弱不同。例如：

- Llama / Qwen 的拒绝机制可能更强；
- Mistral 可能更直接、更 uncensored；
- PCA 投影距离可作为模型安全对齐强度的内部指标。

## Paper 1 / Paper 2 共享：点积 vs 余弦相似度消融实验

### 目标

解决“选题说余弦相似度，实际用了点积”的潜在审稿风险。需要证明点积是有意设计，因为它同时捕捉方向和激活幅度。

### P1.12 对比检测分数

比较以下方法：


| 方法                     | 分数                 |
| ---------------------- | ------------------ |
| cosine-only            | `cos(h, v_safe)`   |
| norm-only              | `                  |
| dot / projection       | `h · v_safe_hat`   |
| projection + norm base | `C_base + ReLU` 方案 |


### P1.13 报告指标

每种方法报告：

- harmful / harmless 区分能力
- AUROC
- FPR at fixed TPR
- TPR at fixed FPR
- 对 attention sink 的敏感性
- 防御后 ASR
- 防御后 UFR / FRR
- 防御后 ARR

### P1.14 预期论点

该实验应支持：

> Dot-product projection is not an implementation shortcut for cosine similarity. It intentionally captures both directional alignment and activation magnitude, which is important under attention-sink-induced norm anomalies.

## Paper 1. Attention Sink / 结构 Token 范数实验

### 目标

系统解释 Qwen 中 `mu_layer` 爆炸、复现结果偏高、不同模板导致攻击强度异常等现象。

### P1.15 Token 过滤策略对比

比较：

1. 不过滤任何 token
2. 只过滤 special token
3. 过滤 special + system / user / assistant marker
4. 过滤 newline
5. 过滤 chat-template marker
6. 过滤结构性 token 后使用 mean
7. 过滤结构性 token 后使用 trimmed mean
8. 过滤结构性 token 后使用 median

### P1.16 记录内容

记录：

- 每层 hidden norm 分布
- `mu_layer`
- 最大 norm token 的位置
- 最大 norm token 的文本
- attention sink token 占比
- 不同过滤策略下的攻击强度变化
- 不同过滤策略下的 ASR 曲线变化

### P1.17 预期产物

- token norm 可视化图
- layer-wise norm 分布图
- filtered / unfiltered ASR 对比图
- Qwen 与 Llama 的对比表

## Paper 2. 防御方法主实验

### 目标

证明 phase-aware defense 比静态 steering 更稳定，比 decode 全程 steering 更少退化。

### P1.18 防御方法对比

比较以下防御：


| 编号  | 防御方法                               |
| --- | ---------------------------------- |
| D0  | 无防御                                |
| D1  | 静态 safety vector，全程加               |
| D2  | 只在 prefill 加 safety vector         |
| D3  | 只在 decode 加 safety vector          |
| D4  | norm clipping                      |
| D5  | base-only defense                  |
| D6  | ReLU-only defense                  |
| D7  | base + ReLU，全程挂载                   |
| D8  | prefill base + decode ReLU gated   |
| D9  | prefill base + first-k decode ReLU |
| D10 | prefill base + decode decay ReLU   |


### P1.19 重点比较对象

优先比较：

- D0：无防御
- D1：静态 safety vector
- D4：norm clipping
- D7：base + ReLU，全程挂载
- D8：prefill base + decode ReLU gated
- D9：prefill base + first-k decode ReLU

### P1.20 报告指标

每种防御报告：

- ASR
- UFR / FRR
- ARR
- repetition rate
- special token leakage
- average output length
- normal utility
- latency overhead

### P1.21 预期论点

最终希望支持：

> Phase-aware dynamic defense achieves a better safety-utility-collapse trade-off than static activation steering and full decode-time steering.

## Paper 2. 攻击鲁棒性实验

### 目标

避免审稿人认为方法只防住了 Rogue random vector。

### P2.1 攻击类型

至少包含：

1. Rogue random vector，原始 prefill-only
2. Rogue random vector，修复 generated-token steering
3. 不同随机种子的 random vector
4. 不同攻击层
5. 不同攻击强度
6. refusal-suppression vector
7. optimized adversarial vector，如果算力允许
8. SAE feature vector，如果资源允许
9. prompt-level jailbreak，作为外部攻击对照

如果资源有限，优先完成 1 到 5。

### P2.2 鲁棒性维度

比较：

- 同一防御对不同攻击强度是否有效
- 同一防御对不同攻击层是否有效
- 同一防御对不同随机方向是否稳定
- 同一防御是否能防 optimized vector
- 同一防御是否能防 prompt jailbreak

## Paper 2. 正常能力与误伤实验

### 目标

证明防御不是通过让模型变傻来降低 ASR。

### P2.3 正常任务集合

至少包含：

- harmless Alpaca / ShareGPT 子集
- 普通知识问答
- 写作任务
- 数学或推理小集合
- 中文正常任务
- 多轮对话任务，如果时间允许

### P2.4 能力指标

报告：

- UFR / FRR
- 平均回答长度
- PPL
- 人工抽检质量
- MT-Bench 子集，如果可行
- AlpacaEval 子集，如果可行
- MMLU 子集，如果可行
- GSM8K 子集，如果可行

PPL 可以保留，但不能只依赖 PPL，因为 PPL 对 instruction-following 和回答质量不够敏感。

## Paper 2. 阈值泛化实验

### 目标

证明 `T`、`k`、`base0`、层选择不是在测试集上调出来的。

### P2.5 标准流程

1. train set：提取 safety vector
2. validation set：选择 `T`、`k`、`base0`、层
3. test set：只评估，不再调参

### P2.6 跨模型泛化

比较：

- Llama 上调出的参数迁移到 Qwen
- Qwen 上调出的参数迁移到 Llama
- Llama / Qwen 上调出的策略迁移到 Mistral

### P2.7 跨数据集泛化

比较：

- JailbreakBench harmful prompts
- HarmBench harmful prompts
- 自建 harmful prompts
- harmless Alpaca / ShareGPT

## 两篇论文的最小可发表实验包

### Paper 1 最小包

1. Rogue original vs fixed decode hook 复现实验
2. prefill-only / decode-only / prefill+decode 对比
3. `fixed-alpha` vs `Rogue-calibrated alpha = c * mu` 对比
4. decode steering representation collapse 诊断
5. attention sink / 结构 token 分析
6. 三模型统一 beyond-ASR 指标汇总

### Paper 2 最小包

1. safety vector 层扫描与投影分布
2. cosine vs dot vs norm 消融
3. phase-aware defense vs static defense vs no defense
4. harmful + harmless 双评估
5. utility / latency / collapse trade-off

如果时间或算力有限，先保 Paper 1 能独立成稿，再补 Paper 2 的方法实验。

## 推荐执行顺序

建议按以下顺序推进：

1. 完成 P0，统一实验基座和日志格式。
2. 优先完成 Paper 1：phase-aware attack reproduction matrix。
3. 完成 Paper 1：decode steering 退化诊断。
4. 完成 Paper 1：`mu` 标定敏感性实验。
5. 完成 Paper 1：attention sink / 结构 token 范数实验。
6. 整理 Paper 1 的三模型 beyond-ASR 指标和坏样例。
7. 再完成 safety vector 层扫描和投影分布。
8. 跑点积 vs 余弦 vs norm 消融。
9. 跑 Paper 2 防御方法主实验。
10. 有余力再做 Paper 2 攻击鲁棒性、正常能力和泛化实验。

第一阶段最关键的不是调出最低 ASR，而是让 Paper 1 独立成立：先把 prefill / decode / `use_cache` 的差异、collapse 风险和 beyond-ASR 评估证明清楚。
