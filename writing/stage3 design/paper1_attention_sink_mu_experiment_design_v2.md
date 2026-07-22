# Paper 1 Stage 3 v2：结构 Token、`mu` 标定与 Attention Sink 审计

协议版本：`v2.0-proposed`  
拟冻结日期：`2026-07-21`  
适用论文：Paper 1 / TDSC Regular Paper  
状态：待内部审阅；正式运行前冻结 primary hypotheses、prompt/vector manifests 与统计脚本  
前一版：`writing/paper1_attention_sink_mu_experiment_design.md`，保留不修改，作为设计演化记录

## 1. v2 执行摘要

Stage 3 不再从一个大规模三模型笛卡尔积开始，而是围绕已经观察到的异常链进行分阶段审计：

```text
复现 ASR 偏高、峰值提前
        |
        v
历史实现重建：template / padding / token exclusion
        |
        v
单个结构 token 是否支配 token-weighted mu
        |
        v
mu 改变 actual alpha，能否解释峰值和 collapse threshold 平移
        |
        v
该高范数 token 是否同时是严格意义上的 Attention Sink
        |
        v
Llama/Mistral 是否出现相同机制，还是只有阈值/失败模式相似
```

v2 的核心原则：

1. **先重建事实，再扩展模型。** Qwen 是机制发现模型；Llama/Mistral 用于关键确认，不复制全部历史错误组合。
2. **先分析 existing artifacts，再运行生成。** 优先把已有 v1/v2/formal 曲线从 `c` 横轴转换为 actual `alpha=c*mu`。
3. **固定 alpha 必须来自有效 Track B 剂量。** 禁止继续使用无行为意义的 `alpha=0-2` 作为 direct-effect 对照。
4. **Stage 3 的 primary endpoint 是标定变化和 collapse，不是个位数随机越狱率。** rare ASR 由已有 single-prompt full1000 支撑。
5. **大部分 filter/aggregator 组合离线计算。** 不为每个 `mu` 估计器重复模型 forward。
6. **Attention Sink 是待验证解释。** hidden norm 达到上万只能证明 structural-token activation outlier，不能单独证明 attention concentration。
7. **生成采用 Gate 驱动。** 核心新增生成预算约 3,000-6,000；只有关键 CI 不足时定向扩样，不默认跑 25,000 或 full1000。

## 2. 已有发现与待验证事实

### 2.1 已观察到的历史现象

同一批约 100 prompts 的历史调试结果包括：

| condition | model/layer | token count | raw mean norm `mu` | 当前解释 |
|---|---|---:|---:|---|
| Llama historical | layer 10 | 2307 | 6.3093 | 右填充基线，checkpoint 为截图中的 Meta-Llama-3-8B-Instruct |
| Qwen historical, unresolved rendering/extraction | layer 9 | 3915 | 412.9935 | 默认 system 增加约 16 tokens/prompt，且 left-padding extraction 有错位 |
| Qwen fixed valid positions / reduced system content / no first-5 drop | layer 9 | 2315 | 652.7743 | token count 已与 Llama 接近，但高范数结构 token 被纳入均值 |
| Qwen current formal artifact | layer 9 | 8 prompts | 59.4958 | 过滤 special IDs，并删除前 5 个 non-special valid tokens |

Qwen 与历史 Llama 的 token 数量差：

```text
(3915 - 2307) / 100 = 16.08 extra tokens per prompt
```

修正 rendering/extraction 后：

```text
(2315 - 2307) / 100 = 0.08 token per prompt
```

这个结果强烈支持“约 16 个额外 token 来自自动注入的默认 system 内容”，但仍需在精确 checkpoint/tokenizer/template 下正式重建。

### 2.2 已观察到的 token-level outlier

一个代表性 Qwen prompt 在目标层出现：

```text
Token: 'system' | Norm:   133.02
Token: '\n'     | Norm: 14374.04
Token: '\n'     | Norm:    66.46
Token: 'user'   | Norm:    76.30
content tokens  | Norm: roughly 60-85
```

因此当前最直接的机制假设不是“整个 Qwen residual stream 都爆炸”，而是：

> 一个位于 chat-template 前部的结构性换行 token 出现极端 hidden norm；当 first-5 exclusion 被移除时，该 token 对 token-weighted mean 产生高杠杆，使 `mu` 从普通尺度上升到 600+。

### 2.3 当前不能视为已证明的内容

- 不能仅凭 `Norm=14374` 断言所有 attention heads 将注意力倾倒到该 token；
- 不能把该现象称为“所有设置下 Qwen 的 `mu` 都爆炸”；
- 不能根据 layer 9/14/18 的均值从约 653 增至约 713 写“指数级增长”；
- 不能把 Qwen 的 left-padding extraction bug 解释为当前右填充 Llama/Mistral 的共同机制；
- 不能直接比较 Qwen/Llama raw L2 mean 后得出架构敏感性，必须控制 hook point、hidden size、checkpoint 和 estimator。

## 3. v1 到 v2 的关键变化

| v1 设计 | v2 修改 | 原因 |
|---|---|---|
| 先做三模型全矩阵 | Qwen forensic-first，Llama/Mistral关键确认 | 避免三模型重复历史错误组合 |
| 最高约 25,200 generations | 核心约 3,000-6,000，Gate 后可定向扩样 | 控制数周运行周期 |
| `mu_standard vs mu_robust` 为主 | 增加与历史发现直接对应的 `drop0 / absolute-first5 / first5-non-special / structural-filter` | 直接解释 `413/653/59.5` |
| template stress test | 精确区分 native user-only、explicit empty system、guaranteed no-system rendering | “空 system role”不等于“无 system role” |
| padding invariance 跨模型同权 | Qwen 历史 blocker；Llama/Mistral仅 sanity/portability QA | 错位只在 left padding + `[:seq_len]` 下发生 |
| fixed-alpha 对照未强调剂量来源 | 所有 fixed-alpha 使用 existing Track B 的 `alpha_peak/alpha_transition` | 避免旧 Track A 强度不足 |
| Attention Sink 与 norm 同阶段展开 | massive/high-norm activation 为主，strict attention 为 Gate 后诊断 | 防止概念越界 |
| 重新跑大量行为曲线 | 先把现有曲线重参数化为 actual alpha | 复用已完成 full1000 |
| 多个 phase/method 全展开 | `decode_only` primary，`rogue_v1/full` 关键控制 | 现有六组已提供 phase 证据 |

## 4. 研究问题、假设与主终点

### RQ3.1：历史 `mu` 差异由哪些实现因素造成？

- `H1a`：native template 是否自动注入默认 system 内容，将由 rendered text/token IDs 直接验证。
- `H1b`：`range(seq_len)` 在 left padding 下会包含 padding 并漏掉尾部真实 token；在 contiguous right padding 下不会发生同类错位。
- `H1c`：删除前 5 个位置/有效 token 是否排除了高范数结构 token，是 `mu` 大幅下降的主要因素。

Primary endpoints：

```text
rendered token count
selected token count
mu under each exact selection rule
paired delta_mu across prompts
```

### RQ3.2：一个或少数结构 token 是否支配 `mu`？

- `H2a`：目标结构 token 在多数 Qwen prompts 的相近 template-relative position 重复出现。
- `H2b`：top-1 token 对 prompt-level norm sum 的贡献显著高于普通 content token。
- `H2c`：leave-top-1-out 或 structural-span exclusion 会使 `mu` 接近 content-token scale。

Primary endpoints：

```text
top1_contribution_share
leave_top1_out_mu
leave_all_structural_out_mu
mu_drop0 / mu_first5_non_special
mu_drop0 / mu_structural_filtered
outlier_recurrence_rate
```

### RQ3.3：`c` 峰值提前是否主要来自 `mu -> alpha` 映射变化？

- `H3a`：以 raw `c` 作横轴时，历史版本的 ASR/broken peak 明显平移。
- `H3b`：改用 actual `alpha=c*mu` 后，不同版本的峰值/transition 更接近。
- `H3c`：同 prompt/vector/actual-alpha 下的确定性输出应一致；同 `c`、不同 `mu` 下的差异由实际剂量变化解释。

Primary endpoints：

```text
alpha_peak
alpha_collapse50
paired broken-rate risk difference at same c
distance between version-specific peaks on c and alpha axes
```

### RQ3.4：高范数结构 token 是否同时形成 Attention Sink？

- `H4a`：目标结构 token 获得高于位置匹配非结构 token 的 attention mass。
- `H4b`：该关系可能仅存在于部分 layers/heads，不预设“所有 heads”。
- `H4c`：如果 high norm 与 attention enrichment 不重合，应将二者视为不同机制。

Attention 是 secondary mechanistic endpoint。没有严格 attention evidence 时，Paper 1 仍可基于 structural-token calibration leverage 成立。

### RQ3.5：该机制是否跨模型存在？

- `H5a`：三模型共享 phase/cache 机制，但不一定共享同一种 structural-token outlier。
- `H5b`：Llama/Mistral 可能表现为较小 `mu` leverage，却仍有 model-specific collapse threshold。
- `H5c`：actual-alpha/relative-dose 匹配后仍存在的差异，才可称为模型特定敏感性。

## 5. 术语与数学定义

### 5.1 Steering 与实际剂量

```text
h'_(l,p,t) = h_(l,p,t) + alpha_l * v_hat_l
alpha_l = c * mu_l
||v_hat_l||_2 = 1
```

单步相对剂量：

```text
r_(l,p,t) = alpha_l / ||h_(l,p,t)||_2
```

论文必须同时报告 `c`、`mu`、actual `alpha` 和 token-level relative dose `r`。只报告 `c` 会掩盖 estimator 改变带来的绝对强度差异。

### 5.2 Structural-token activation outlier

定义为 chat-template structural span 上的 token，其 hidden norm 或 coordinate concentration 相对于同 prompt/layer 的 content-token distribution 极端偏高。

报告：

```text
L2 norm
L2 / sqrt(hidden_size)
L_inf / L2
max_abs / median_abs
within-prompt percentile
robust z-score relative to content tokens
```

不预先规定所有模型共享同一绝对阈值。

### 5.3 Attention Sink

Attention Sink 指后续 queries 对初始/结构 keys 分配不成比例的 attention mass。严格结论必须来自 attention weights 或等价 score，不得由 hidden norm 替代。

参考：

- *Efficient Streaming Language Models with Attention Sinks*, arXiv:2309.17453: https://arxiv.org/abs/2309.17453
- *Massive Activations in Large Language Models*, arXiv:2402.17762: https://arxiv.org/abs/2402.17762

## 6. 模型、checkpoint 与数据划分

### 6.1 两条模型线必须分开

#### Historical forensic line

目标是重建截图和旧代码观察。必须尽可能使用当时的：

- Qwen2.5 checkpoint/tokenizer/modelscope revision；
- Meta-Llama-3-8B-Instruct historical checkpoint；
- Transformers/PyTorch 版本；
- chat template；
- prompt 顺序；
- batch size 和 padding side。

截图中的 Llama 是 Meta-Llama-3-8B-Instruct，不等同于当前 formal 的 Meta-Llama-3.1-8B-Instruct。若 historical checkpoint 不可获得，使用已保存 raw/log 作为 forensic artifact，并将该分支标为 `artifact reconstruction`，不得冒充新 checkpoint 的精确复现。

#### Current confirmatory line

1. Qwen2.5-7B-Instruct
2. Meta-Llama-3.1-8B-Instruct
3. Mistral-7B-Instruct-v0.3

用于当前 Paper 1 的跨模型结论。

### 6.2 必须归档的模型信息

- model/tokenizer absolute path 与 revision/hash；
- `num_hidden_layers`、`hidden_size`、attention heads/KV heads；
- chat template 原文与 SHA256；
- tokenizer special IDs；
- default `padding_side` 与实验 resolved value；
- model dtype、norm reduction dtype；
- Transformers/PyTorch/CUDA 版本；
- target module 与 `hidden_states[l+1]` 对齐结果。

### 6.3 Prompt splits

| split | 建议数量 | 用途 | 是否可重叠 |
|---|---:|---|---|
| `D_forensic` | historical 100 | 重建 3915/2315 tokens 与 413/653 现象 | 必须与历史一致 |
| `D_norm_cal` | 100 harmful + 100 benign | current 三模型全层 norm/`mu` | 不与行为 confirmation 重叠 |
| `D_behavior_screen` | 30 harmful | Qwen/cross-model小规模筛选 | 不与 confirmation 重叠 |
| `D_behavior_confirm` | 50 harmful | 关键 paired behavior cells | 不参与 `mu` 标定 |
| `D_benign_check` | 30 benign | selected-condition generation integrity | 不参与 `mu` 标定 |
| `D_attention` | 32 Qwen；跨模型各 16 | strict attention | 可从 norm calibration 固定抽样 |

要求：

- prompt IDs、category、source version、SHA256 全部固定；
- split 间做 exact 和 semantic-near-duplicate 审计；
- harmful confirmation 至少覆盖 8 个行为类别；
- 不按越狱成功与否筛选 prompts；
- vectors 从原始未筛选 pool 中固定抽样，不选择成功向量。

## 7. 精确实验因素

### 7.1 Template/rendering 因素

不能只使用“system on/off”描述，必须保存输入 messages 和 rendered text。

| ID | messages/rendering | 目的 |
|---|---|---|
| `T_native_user_only` | messages 只有 user role，调用 checkpoint native chat template | 检查模板是否自动注入默认 system |
| `T_explicit_empty_system` | 显式 system role，content 为空，再添加 user role | 保留 system header，删除 system semantic content |
| `T_controlled_no_system` | 保证 rendered text 中不存在 system role/header/content | 纯 no-system 对照 |
| `T_historical_exact` | 历史脚本实际 messages 和 wrapper | 复现 artifact，不与 current line 混用 |

每个 prompt 保存：

```text
messages JSON
rendered text
input_ids
decoded token-by-token text
token count
system-content span
user-content span
assistant-preamble span
template hash
```

### 7.2 Padding/extraction 因素

| ID | 定义 | 使用范围 |
|---|---|---|
| `P_historical_range` | `seq_len=sum(mask)` 后使用 `[:seq_len]` | 只用于 Qwen historical forensic，不用于正式 estimator |
| `P_valid_mask` | `nonzero(attention_mask==1)` | 所有 canonical measurements |
| `P_batch1` | 单 prompt，无实际 padding | canonical reference |
| `P_batch_left` | batch 后 left padding | Qwen regression test；其他模型 portability QA |
| `P_batch_right` | batch 后 right padding | Llama/Mistral historical/current sanity test |

确定性说明：

```text
right padding: [A B C PAD PAD], [:3] -> [A B C]
left padding:  [PAD PAD A B C], [:3] -> [PAD PAD A]
```

因此：

- Qwen historical left padding + `P_historical_range` 是真实错位；
- current Llama/Mistral right padding 不受同类错位影响；
- `analyze_attention_sink.py` 当前默认强制 left padding，因此即使分析 Llama/Mistral，也可能人为引入该问题；
- formal runner 和当前 `measure_activation_norm.py` 都是逐 prompt 路径，现有 full1000 不应被错误宣称受 batch-padding 错位影响；
- batched right-padding generation 的 last-position 问题属于另一类问题，本阶段不与 norm extraction 混写。

### 7.3 Token selection/`mu` estimators

所有 estimator 尽可能从同一 `(template, model forward, hidden states)` 的 raw per-token records 离线计算。

| ID | special filter | positional drop | structural filter | aggregation | 用途 |
|---|---|---|---|---|---|
| `mu_special_drop0` | 是 | 无 | 无 | token-weighted mean | 直接重现 600+ 发现 |
| `mu_public_absolute5` | 是 | tensor absolute positions 0-4 | 无 | token-weighted mean | public historical implementation fidelity |
| `mu_valid_absolute5` | 是 | unpadded valid positions 0-4 | 无 | token-weighted mean | padding-invariant public-style rule |
| `mu_first5_non_special` | 是 | 前 5 个 non-special valid tokens | 无 | token-weighted mean | current formal artifact rule |
| `mu_structural_filtered` | 是 | 无 | span-based structural exclusion | prompt-balanced mean | structural leverage 主对照 |
| `mu_structural_trim10` | 是 | 无 | span-based structural exclusion | per-prompt 10% trimmed mean，再 prompts 等权 | robust sensitivity |
| `mu_content_median` | 是 | 无 | 仅 content spans | median | appendix sensitivity |

必须避免：

- 使用 token ID `encode("system")` 全局删除正文中的普通词；
- 把 absolute-first-5 与 first-5-non-special 混成同一规则；
- 把历史 8-prompt `mu=59.4958` 当作 100-prompt population truth；
- 根据哪个 estimator 产生更好行为后再选主 estimator。

### 7.4 Aggregation 不扩增 forward

同一 raw token table 离线计算：

- token-weighted mean；
- prompt-balanced mean；
- per-prompt trimmed mean；
- median；
- leave-top-k-out；
- leave-structural-class-out。

这部分不为每个 aggregator 重复 GPU forward。

## 8. 实验 E0：工具正确性 Gate

正式运行前必须通过：

| QA | 设计 | 通过条件 |
|---|---|---|
| left/right mask | synthetic padded sequences | selected token IDs 100% 符合预期 |
| historical bug reproduction | Qwen 两个不同长度 prompts | `P_historical_range` 读取 pads/漏尾部，`P_valid_mask` 正确 |
| right-padding sanity | Llama/Mistral batch | `P_historical_range` 与 valid mask 在 contiguous valid prefix 上一致 |
| batch invariance | 同 prompts，batch1/4/8 | canonical content-token norm relative median error < `1e-4`，max < `5e-3`；失败则正式测量使用 batch1 |
| layer alignment | hook output vs `hidden_states[l+1]` | dtype tolerance 内一致 |
| vector norm | selected vector pool | fp32 下 `abs(||v||-1)<1e-5` |
| span annotation | 每模型 30 rendered prompts | accuracy >=98%，unresolved <1% |
| deterministic alpha identity | 相同 input/vector/actual alpha | greedy token IDs 完全一致 |
| eager attention parity | production vs eager prefill logits | top-1 agreement 100%，误差与 JS divergence 低于冻结阈值 |

任何 canonical QA 失败时停止正式实验。`P_historical_range` 的预期失败只用于证明历史 bug，不进入 Gate 失败统计。

## 9. 实验 E1：历史异常精确重建

### 9.1 目标

回答：`mu` 从普通尺度到 400-700 的变化，分别由 system rendering、padding extraction 和 first-5 rule 贡献多少。

### 9.2 Qwen forensic matrix

固定：

- historical Qwen checkpoint/tokenizer；
- `D_forensic=100`，保持原 prompt 顺序；
- layers 9/14/18；
- historical dtype/batch size；
- 同一组 forward raw records。

必要 rendering forwards：

```text
T_historical_exact
T_explicit_empty_system
T_controlled_no_system
```

对每个 raw table 离线应用：

```text
P_historical_range / P_valid_mask
x
mu_special_drop0 / mu_public_absolute5 /
mu_valid_absolute5 / mu_first5_non_special /
mu_structural_filtered
```

由于 extraction/filter/aggregation 从同一 hidden states 离线重算，这不是 3×2×5 次模型 forward。

### 9.3 Llama historical control

若 historical Llama-3 checkpoint 可获得：

- 同 `D_forensic=100`；
- historical layers 10/15/18/20；
- right-padding exact reproduction；
- `P_historical_range` 与 `P_valid_mask` 对照；
- 至少 `mu_special_drop0 / mu_first5_non_special / mu_structural_filtered`。

若 checkpoint 不可获得，不重新用 Llama3.1 冒充。保留截图/raw log，并在 current confirmatory line 使用 Llama3.1。

### 9.4 Forensic 主表

| model/revision | template | padding | extraction | selection | tokens | `mu` | top token | top norm | top contribution |
|---|---|---|---|---|---:|---:|---|---:|---:|

必须明确展示：

- 默认 system 是否贡献约 16 tokens/prompt；
- padding bug 选中了多少 pad、漏掉多少 valid tail tokens；
- `drop0 -> first5` 的 `mu` ratio；
- 修复 padding/system 后 `mu` 上升是否来自 denominator/selection 改变，而非“修复失败”。

### 9.5 验收与解释

若同 checkpoint/environment 可恢复，数值目标为接近历史记录；允许误差由 dtype/library version 解释，但必须报告。

若不能精确恢复：

- 仍报告方向和 effect size；
- 标注 `partial reconstruction`；
- 不用 current checkpoint 数值替换 historical 数值。

## 10. 实验 E2：单 token 对 `mu` 的贡献归因

### 10.1 Raw records

对每个 `(model, layer, prompt, token)` 保存：

```text
prompt_id
template_id
token_id / token_text
tensor_position / valid_position / template-relative position
token_type
L2 / RMS / L_inf
coordinate concentration
selected_by_each_estimator
```

使用 Parquet/Arrow，不把完整 hidden vectors 写入 JSON。

### 10.2 主指标

对 prompt `p`、token `t`：

```text
contribution_share[p,t] = norm[p,t] / sum_j norm[p,j]

mu_leave_top1_out[p]
  = mean(norm[p,j] for j != argmax_t norm[p,t])

mu_leave_structural_out[p]
  = mean(norm[p,j] for semantic content tokens)
```

聚合报告：

- top token type/text/position 的 recurrence；
- median top-1 contribution share 与 95% prompt-bootstrap CI；
- `mu_special_drop0 / mu_first5_non_special`；
- `mu_special_drop0 / mu_structural_filtered`；
- leave-one-out 降幅；
- 结构 token 在 top-0.1%/1%/5% norm 中的 enrichment；
- max/median 与 max/content-mean ratio。

### 10.3 “`mu` 爆炸”的操作性表述

主文不使用无条件的“Qwen `mu` explosion”。建议写：

> Under the no-positional-drop, token-weighted estimator, a recurrent structural-token outlier dominates the norm sum and inflates the calibration statistic by X-fold relative to content-only/first-five-excluded estimates.

内部 Gate，不作为领域通用定义：

- `mu_special_drop0 / mu_structural_filtered` 的 95% CI lower bound > 1.5；或
- median top-1 contribution share > 50%。

若均不满足，不扩展 estimator-induced behavior matrix，保留 null result。

### 10.4 全层分析

current 三模型在 `D_norm_cal` 上一次 forward 输出全层 hidden states，绘制：

- per-layer content norm；
- per-layer structural top-1 norm；
- per-layer `mu` ratio；
- outlier token identity/position 是否稳定。

只有在多于三个层点上观察到与深度近似 log-linear 的增长并通过预注册拟合，才讨论“指数增长”；否则只写 persistent/increasing outlier。

## 11. 实验 E3：复用现有曲线的 actual-alpha 重分析

### 11.1 这是 behavior 前的必做步骤

收集历史 v1/v2 与 current formal 的：

```text
c values
mu used by each run
actual alpha, if already stored
prompt/vector IDs
ASR / broken / refusal / repetition
config/template/padding metadata
```

重新计算：

```text
alpha_run = c_run * mu_run
```

若 vector 未单位归一化，还需：

```text
effective_vector_dose = alpha_run * ||v||_2
```

### 11.2 强度换算

以历史示例：

```text
mu_drop0 ~= 653
mu_formal ~= 59.5
ratio ~= 10.97

c_formal_equivalent
  = c_drop0 * mu_drop0 / mu_formal
  ~= 10.97 * c_drop0
```

因此 `drop0 c=0.1` 约对应 formal `c=1.10`；`drop0 c=0.25` 约对应 formal `c=2.74`。该换算应先用于解释“峰值提前”，而不是立即重跑 1000 vectors。

### 11.3 重新绘图

每个版本同时生成：

```text
c vs ASR / broken / refusal / repetition
actual alpha vs ASR / broken / refusal / repetition
relative dose vs broken / repetition
```

如果 `c_peak` 不同而 `alpha_peak` 接近，支持 calibration mapping 解释。

如果 actual-alpha 曲线仍不对齐，进一步检查：

- template direct effect；
- different prompt/vector pools；
- checkpoint/library differences；
- phase/hook semantics；
- vector normalization。

### 11.4 统计

- 同 vector IDs 时做 paired vector bootstrap；
- 不同 vector pools 时只报告独立 CI，不伪装成配对；
- peak/transition CI 通过 bootstrap curve resampling；
- 未覆盖共同 alpha range 时不外推对齐结论。

## 12. 实验 E4：Strict Attention Sink 诊断

### 12.1 启动 Gate

只有 E2 表明 Qwen structural outlier 可重复且具有显著 `mu` leverage 后，才启动 strict attention。

### 12.2 Qwen 主分析

- prompts：32，16 harmful + 16 benign；
- layers：9/14/18，必要时加入 outlier 最大层；
- clean prefill；
- clean decode 前 32 steps；
- `output_attentions=True`；
- `attn_implementation="eager"`；
- batch size 1；
- production/eager logits parity 先通过 E0。

### 12.3 Attention 指标

```text
attention_mass_to_target_structural_token
attention_mass_to_first_4_valid_tokens
attention_entropy
head-wise target rank
fraction_of_heads_where_target_is_top1_key
high-norm/attention-sink position overlap
```

不能只使用 uniform baseline。主对照为：

- 相同 template-relative position 附近的非结构 tokens；
- equal-count position-matched nonstructural keys；
- 同 prompt 中普通 content token distribution。

uniform causal-mask expectation 只作 secondary reference。

### 12.4 Teacher-forced decode

先生成 clean 32-token prefix，再在相同 prefix 上 step-by-step replay，以避免 clean/steered 文本分叉混淆 attention 比较。

### 12.5 跨模型 Gate

如果 Qwen 目标 token同时满足高 norm 与 attention enrichment：

- Llama3.1：16 prompts，current target layers；
- Mistral：16 prompts，current target layers。

如果 Qwen 没有 attention enrichment：

- 不进行大规模跨模型 attention；
- 将 Paper 1 术语固定为 structural-token activation outlier；
- 不影响 `mu` calibration 主结论。

### 12.6 Attention intervention

默认不执行。它侵入模型 attention logits，容易扩展为新防御方法并显著增加实现/验证成本。

只有论文明确需要因果声称“Attention Sink contributes to collapse”时，另立独立协议，并加入 equal-count random-position suppression 和 clean utility controls。

## 13. 实验 E5：Actual-alpha 锚定的行为因果验证

### 13.1 为什么不能继续使用旧 Track A alpha

旧 Track A 的 `alpha=0-2` 主要用于 phase/control-flow audit。若 current Track B `mu≈59.5`，则：

```text
c=1.0 -> alpha≈59.5
c=1.5 -> alpha≈89.2
c=2.0 -> alpha≈119.0
```

因此 template direct-effect 或 estimator causal control 若继续使用 `alpha=1`，很可能完全没有行为效应。v2 所有 fixed-alpha 必须来自 existing Track B：

```text
alpha_attack = c_peak_formal * mu_formal
alpha_transition = c_collapse50_formal * mu_formal
alpha_high = c_high_formal * mu_formal
```

这些值在使用 test prompts 前由已有 full1000/pilot 冻结。

### 13.2 两种不同的行为问题

#### A. Same-c protocol effect

同一个 `c` 下，不同 estimator 产生不同 actual alpha：

```text
alpha_E = c * mu_E
```

该实验回答“相同论文倍率标签为何得到不同结果”。

#### B. Alpha-matched identity/direct effect

对 estimator-only 变化，设置：

```text
c_E = alpha_anchor / mu_E
```

如果实际 input/vector/schedule 相同，输出应一致。这是 runner identity QA，不需要完整 500-response 重复。

对 template 变化，即使 actual alpha 相同，输出仍可不同，因为 template 会直接改变模型状态。这需要 2×2 因果分解。

### 13.3 Qwen estimator behavior matrix

前提：E2 structural leverage Gate 通过。

Primary method：`decode_only`。  
Primary endpoint：`broken_rate`。  
Secondary：ASR、refusal、safe、repetition、length、leakage。

估计器：

```text
mu_special_drop0
mu_first5_non_special
mu_structural_filtered
```

强度不重复 9 点：

- 一个历史 peak/early-peak `c`；
- 一个由 formal transition alpha 反推的低 `c`，保证 `mu_special_drop0` 不超过已有 high-alpha 范围；
- alpha-matched identity 只跑 8 prompts × 3 vectors。

Screening：

```text
30 prompts x 10 vectors = 300 responses/cell
3 estimators x 2 same-c points x 300 = 1,800 generations
```

如果某 historical same-c 点对应的 alpha 远超所有既有有效范围：

- 保留 100-response forensic behavior cell；
- 不为该超范围点扩到 300/500；
- 主要通过 actual-alpha 换算解释，而不是反复生成明显 collapse 输出。

### 13.4 Template direct/indirect 2×2

Qwen primary templates：

```text
T0 = historical/native rendering
T1 = controlled no-system rendering
```

测得：

```text
mu0 = mu under T0
mu1 = mu under T1
alpha0 = frozen formal transition alpha
alpha1 = c_transition * mu1
```

四组：

| group | template | actual alpha | 解释 |
|---|---|---:|---|
| A | T0 | `alpha0` | baseline |
| B | T1 | `alpha0` | controlled direct template effect |
| C | T0 | `alpha1` | dose-change effect under baseline template |
| D | T1 | `alpha1` | template + recalibration combined effect |

每组先 `30 prompts x 10 vectors=300`：

```text
4 x 300 = 1,200 generations
```

禁止把 `B-A` 与 `D-A` 混写。前者接近 fixed-dose template direct effect；后者同时包含 template 与 recalibration。

### 13.5 Phase controls

不重复现有六组完整矩阵。

- `decode_only`：primary generated-token mechanism；
- `rogue_v1`：一个 historical peak/transition 点，证明 prefill-dominant schedule 不具有相同累计 decode exposure；
- `full`：一个 transition 点确认 prefill+decode；
- 不重跑 `no_cache/first_k/decay`，除非现有 artifact 缺失关键 phase counters。

建议：

```text
2 control methods x 1 point x 100-200 responses
= 200-400 generations
```

### 13.6 Benign integrity

selected conditions：

- 三模型 clean baseline；
- formal estimator at transition；
- no-drop/structural-filter 中最有解释力的一组；
- 30 benign prompts × 3 vectors = 90 responses/cell。

Stage 3 只需证明 collapse 不是 harmful judge 特例。完整 benign utility 属于 Paper 1 generalization/validation track，不在这里复制所有 estimator×method。

## 14. 实验 E6：跨模型关键确认

### 14.1 不复制 Qwen 全部 forensic Cartesian product

Llama3.1/Mistral 必做：

- native rendered template audit；
- current padding side 与 valid-position extraction；
- all-layer token norm profile；
- `mu_special_drop0 / mu_first5_non_special / mu_structural_filtered`；
- top-token contribution/recurrence；
- current formal layer的 actual-alpha mapping。

不必做：

- Qwen 特有的 implicit-system historical wrapper 全组合；
- right-padding 下已知不会错位的重复 bug matrix；
- 每个 aggregator 的生成实验；
- 六个 phase schedules 全重跑。

### 14.2 行为确认 Gate

如果某模型：

- `mu_special_drop0 / mu_structural_filtered` lower CI >1.5；或
- 出现 recurrent structural top-token contribution >50%；

则运行：

```text
2 estimator protocols
x 2 same-c/actual-alpha anchors
x 20-30 prompts
x 10 vectors
```

每模型约 800-1,200 generations。

如果没有 structural leverage：

- 不强行扩 estimator behavior；
- 使用现有 full1000/pilot 的 actual-alpha curve 分析 model-specific collapse threshold；
- 将该模型作为机制不共享的负对照。

### 14.3 跨层行为

全层 norm profile 是必做且低成本。跨层 generation 是 Gate 后可选：

- Qwen outlier 最大层 + current formal layer；
- Llama/Mistral 仅在 structural leverage 重复时增加一个层；
- 每层 transition 一个点，20 prompts × 5-10 vectors；
- 不对 1/3、1/2、2/3 depth 全部执行完整行为矩阵。

这种设计仍可回答“现象是否 layer-specific”，但不会重新产生 `3 models × 3 layers × all methods × all strengths`。

## 15. 新增生成预算与扩样策略

### 15.1 预算分层

| block | 预计 generations | 是否必做 |
|---|---:|---|
| Qwen estimator same-c | 1,800 | E2 Gate 通过后必做 |
| Qwen template 2×2 | 1,200 | template/`mu` 差异存在时必做 |
| phase controls | 200-400 | 必做关键点 |
| benign selected cells | 360-720 | 必做精简版 |
| Llama/Mistral key confirmation | 0-2,400 | 按各自 structural leverage Gate |
| optional cross-layer behavior | 0-1,200 | 仅关键结论需要 |

核心新增行为量：约 3,500-4,500。  
三模型 Gate 全通过后的常见总量：约 5,000-6,500。  
极端上限含 optional cross-layer：约 7,500，不默认执行。

### 15.2 为什么不默认 full1000

Stage 3 的 primary endpoint 通常是高发生率的 broken/collapse 与确定性的 `mu` ratio，不是 1%-3% rare ASR。

- 现有 single-prompt full1000 继续提供 rare random-vector ASR；
- 新 multi-prompt cells 主要估计 transition 和 calibration effect；
- `30 prompts ×10 vectors` 比单 prompt 300 vectors 提供更合理的 prompt/vector crossed variation；
- ASR 为 secondary，0/300 只报告 upper CI，不写“攻击率为零”。

### 15.3 定向扩样

只对预注册 primary cells扩样：

1. 先完成 300/cell；
2. 使用 prompt/vector two-way clustered bootstrap；
3. 若 paired broken-rate RD 95% CI half-width >5 percentage points，扩至 500；
4. 若目标是区分 `<2%` ASR，必须单独声明 rare-event objective 后扩至 1000；
5. 不根据 p-value 是否刚过 0.05 继续加样；
6. 不只扩效果最大的模型/条件而省略负结果。

### 15.4 与 Paper 1 其他实验分工

- Stage 1 full1000：Rogue-faithful random-vector attack rate 与 phase curves；
- Stage 3 v2：解释 calibration anomaly 和 collapse threshold；
- multi-behavior generalization track：一般 harmful ASR 外部有效性；
- second attack track：攻击家族外部有效性；
- Stage 3 不承担上述所有缺口，避免一次实验解决整篇论文。

## 16. 统计分析预案

### 16.1 Forensic/norm 分析

- prompt 是 bootstrap cluster；
- token 不是独立样本；
- 同 prompt 下 estimator/filter 做 paired difference；
- 报告 median、mean、ratio、95% prompt-bootstrap CI；
- top-token recurrence 用 prompt-level proportion；
- 全层 secondary comparisons 使用 simultaneous band 或 BH-FDR。

### 16.2 Existing curve remapping

- 同 vector pool 时做 paired vector bootstrap；
- 不同 pool 时独立 bootstrap；
- `c_peak/alpha_peak` 由同一冻结规则提取；
- transition 定义为预测 `broken_rate=0.5`，若测试范围内未达到则写 `not reached`；
- 只在共同 alpha support 内比较版本曲线。

### 16.3 Behavior crossed design

相同 `(prompt_id, vector_id, method, c/alpha)` 配对。

报告：

- paired risk difference；
- risk ratio；
- McNemar-type paired transition count；
- prompt/vector two-way clustered bootstrap 95% CI；
- actual-alpha/relative-dose curve。

### 16.4 Primary families

1. Qwen `mu_special_drop0` vs `mu_first5_non_special` ratio；
2. Qwen top structural token contribution 与 leave-one-out `mu`；
3. historical/current peak distance on `c` vs actual-alpha axes；
4. Qwen same-c estimator effect on broken rate；
5. Qwen template fixed-alpha direct effect；
6. cross-model structural leverage presence/absence。

模型内 primary comparisons 使用 Holm correction。attention heads、所有层和额外 aggregators 属于 secondary/exploratory。

### 16.5 Equivalence 与停止规则

不再仅凭 `|mu ratio-1|<5%` 停止行为实验，因为陡峭 transition 可放大小剂量差异。

停止 estimator expansion 需要同时满足：

- `mu` ratio 的 CI 位于预注册实质等效区间；
- 基于 existing curve local slope 的 predicted broken-rate shift 小于等效界限；
- independent screening behavior 的 paired RD CI 也位于该界限。

等效界限必须由已有 full1000 variance/power simulation 冻结，不能在看到新结果后设定。

### 16.6 Judge 与人工验证

Paper-1 dual judge 保留：

- harmful：`unsafe/refusal/safe/broken`；
- benign：`helpful/refusal/unsafe/broken`；
- Rogue-compatible binary 仅作攻击成功对齐。

从已有 full1000 与 Stage 3 新结果联合分层抽取至少 360 条进行双人人工标注，不要求全部来自新增生成。

报告：

- inter-annotator agreement，目标 >=0.70；
- judge macro-F1，建议 >=0.80；
- unsafe/broken recall；
- per-model confusion matrix；
- held-out rubric revision，不在同一 validation sample 反复调 judge prompt。

Legacy ARR 继续拆分为 repetition、leakage、garbled、EOS/length；不把短有效拒绝自动解释为 collapse。

## 17. Gate 与决策树

```text
E0 tools pass?
  no  -> stop and fix
  yes -> E1 forensic reconstruction

E1/E2 show recurrent structural leverage?
  no  -> report null; skip large estimator behavior
         analyze relative-dose explanation from existing curves
  yes -> E3 actual-alpha remapping
         E4 strict attention diagnostic
         E5 Qwen causal behavior

Qwen strict attention positive?
  no  -> use "structural-token activation outlier"
  yes -> use "attention-sink-associated outlier"
         run small cross-model attention confirmation

Llama/Mistral show structural leverage?
  no  -> retain as negative controls; use existing collapse curves
  yes -> run key estimator behavior cells only

Primary CI precise enough?
  yes -> stop
  no  -> expand only frozen primary cells to 500/1000 as justified
```

Gate 不能用于删除负结果，只决定是否值得扩展资源密集型机制确认。

## 18. 论文图表与故事结构

### Figure 6：Forensic reconstruction of calibration drift

建议包含：

- A：历史 Qwen/Llama token count，突出 `+16.08 tokens/prompt`；
- B：`mu≈413 -> 653 -> first5-excluded scale` 的条件链；
- C：left-padding `[:seq_len]` 错位示意；
- D：不同 estimator 对同一 raw token table 的 `mu`。

### Figure 7：A structural token dominates `mu`

- token position vs hidden norm；
- top `\n` token 标记；
- contribution share；
- leave-top-1/leave-structural-out `mu`；
- all-layer recurrence。

### Figure 8：`c` 与 actual-alpha 的曲线重参数化

- version-specific `c vs ASR/broken`；
- `alpha vs ASR/broken`；
- `relative dose vs broken/repetition`；
- peak/transition 对齐程度。

### Figure 9：Strict attention 与跨模型确认

只有 strict attention 为正时展示 attention mass。否则 Figure 9 改为三模型 structural leverage 与 model-specific collapse threshold。

### Main tables

Table A：forensic configs、tokens、`mu`、top-token contribution。  
Table B：三模型 estimator ratios、outlier recurrence、attention enrichment。  
Table C：same-c 与 fixed-alpha causal contrasts。  
Table D：允许/不允许的跨模型结论。

## 19. 允许的论文结论

### 19.1 如果 structural leverage 成立

> A recurrent chat-template token exhibits an extreme activation norm and dominates the token-weighted calibration statistic when positional exclusion is removed. Because the steering scale is defined as `alpha=c*mu`, this implementation choice changes the actual intervention dose and shifts the observed attack-to-collapse operating point.

### 19.2 如果 actual-alpha 曲线重新对齐

> The apparent early peak across implementation versions is largely explained by calibration-induced rescaling: curves that differ on the nominal multiplier axis become substantially more aligned when plotted against the actual intervention magnitude.

### 19.3 如果 attention evidence 同时成立

> The high-leverage structural token is also attention-sink-associated, receiving disproportionate attention mass relative to position-matched nonstructural keys.

没有 attention evidence 时删除该句，不影响 calibration 结论。

### 19.4 如果跨模型机制不共享

> The phase/cache mechanism generalizes across models, whereas the structural-token calibration pathology is tokenizer/template/model specific. Model-specific collapse thresholds remain after accounting for actual dose.

## 20. 禁止表述

- “Rogue binary judge 把 collapse 错判为 safe”；
- “Qwen 的 `mu` 在所有协议下都会爆炸”；
- “Attention Sink 已被证明”，若只有 hidden norm；
- “所有 attention heads 都倾倒到换行 token”，若未报告 head distribution；
- “深层指数级爆炸”，若只有三个缓慢上升的 layer means；
- “padding bug 同时影响 Qwen/Llama/Mistral”，若 Llama/Mistral 使用 contiguous right padding；
- “fixed-alpha 对照无效说明 phase 不重要”，若 alpha 仍使用 0-2；
- “三模型证明所有 LLM 均如此”；
- “structural filtering 是新防御方法”；它是 measurement/calibration audit；
- “0/300 ASR 等于攻击率为零”。

## 21. Artifact 与可审计性

建议新目录：

```text
results/paper1_stage3_attention_mu_v2/
  protocol/
  historical_artifacts/
  model_manifests/
  prompt_manifests/
  qa/
  rendered_prompts/
  token_maps/
  norm_raw_parquet/
  estimator_summaries/
  existing_curve_remap/
  attention_audit/
  generation_screen/
  generation_confirm/
  judged/
  human_validation/
  statistics/
  figures/
  logs/
```

每个 run 保存：

- command、resolved config、git commit、dirty diff hash；
- model/tokenizer/template hashes；
- environment/package versions；
- prompt/vector manifests；
- padding side、batch size、attention mask/position handling；
- estimator ID、`mu`、actual alpha；
- phase counters；
- raw/summary SHA256；
- expected/actual cell counts；
- failed/interrupted runs。

聚合脚本缺少 expected cell 时必须 non-zero exit，不能静默跳过。

## 22. 实施前需要修复或新增的工具

### 必须修复

- `scripts/analyze_attention_sink.py` 的未定义 `valid_mask`；
- left padding 下 `[:seq_len]` 截取；
- role-marker token-ID 全局过滤；
- 缺少 prompt ID/full token baseline；
- 脚本名称与实际未读取 attention weights 的概念不一致。

### 建议新增

1. `build_rendering_manifest.py`
   - 输出 messages/rendered text/token IDs/token spans/template hash。
2. `collect_token_norms.py`
   - 一次 forward 保存全层 per-token summary 到 Parquet。
3. `compute_mu_estimators.py`
   - 从 raw table 离线计算所有 selection/aggregation rules。
4. `reconstruct_historical_mu.py`
   - 重建 template/padding/extraction/filter 条件链。
5. `remap_strength_to_alpha.py`
   - 合并已有 summary，输出 `c/alpha/relative-dose` 曲线。
6. `measure_strict_attention.py`
   - eager attention、position-matched controls、teacher-forced decode。
7. `run_stage3_v2_behavior.py`
   - actual-alpha anchors、paired manifests、Gate-aware selected cells。
8. `summarize_stage3_v2.py`
   - prompt/vector clustered CI、缺失 cell 检查、论文表图。

## 23. 推荐执行顺序

### Phase 0：不运行生成

1. 冻结 historical/current checkpoint 和 prompts；
2. 修复 mask/span/token logging；
3. 通过 E0；
4. 完成 Qwen E1 forensic reconstruction；
5. 完成 E2 top-token contribution；
6. 完成 existing curves 的 E3 actual-alpha remapping。

### Phase 1：低成本机制确认

1. current 三模型全层 norm/estimator ratios；
2. Qwen strict attention 32 prompts；
3. 根据 Attention Gate 决定是否扩 Llama/Mistral attention；
4. 冻结 `alpha_attack/transition/high`。

### Phase 2：有限行为生成

1. Qwen estimator same-c cells；
2. Qwen template 2×2；
3. rogue_v1/full 关键 controls；
4. selected benign checks；
5. Judge 与独立 confirmation。

### Phase 3：跨模型/跨层 Gate 扩展

1. Llama/Mistral structural leverage positive cells；
2. 一个额外关键层；
3. 只对 CI 不足的 primary cells 定向扩样。

## 24. 最终验收清单

- [ ] 原始 v1 设计文档保持不变
- [ ] historical screenshot/log/checkpoint provenance 已归档
- [ ] Qwen `3915 -> 2315` token 差异已在同 prompt pool 重建或解释
- [ ] `413/653/59.5` 对应的不同规则已明确，不再混称同一个 `mu`
- [ ] native user-only / empty-system / no-system rendering 已区分
- [ ] Qwen left-padding historical bug 已复现
- [ ] Llama/Mistral right-padding未被错误归因
- [ ] all canonical extraction 使用 valid mask
- [ ] `drop0 / absolute5 / first5-non-special / structural-filter` 已离线计算
- [ ] top `\n` contribution、leave-one-out、recurrence 已报告
- [ ] raw L2 与 dimension-normalized指标同时报告
- [ ] existing curves 已重画为 actual-alpha/relative-dose
- [ ] fixed-alpha 使用 Track B 有效 alpha anchors，不使用 0-2
- [ ] strict attention 使用 position-matched controls
- [ ] 没有 attention evidence 时删除 Attention Sink 因果措辞
- [ ] behavior primary endpoint 为 broken/transition，ASR 标为 secondary
- [ ] 不重复六个 phase schedules 完整矩阵
- [ ] 三模型负结果保留
- [ ] prompt/vector two-way clustered CI 完成
- [ ] judge-human validation 完成
- [ ] expected/actual cell count 为 zero missing
- [ ] 论文 claim 与第 19-20 节一致

## 25. 最终执行建议

当前空闲 GPU 最适合先完成 Phase 0/1，而不是继续启动新的 full1000：

```text
第一优先：Qwen historical reconstruction + per-token contribution
第二优先：existing c-curves -> actual-alpha curves
第三优先：三模型全层 norm estimator audit
第四优先：Qwen strict attention
第五优先：Gate 后 300/cell 的 selected behavior
```

这一顺序优先回答最有创新性、也最容易被审稿人追问的问题：为什么相同的名义 `c` 在不同实现中代表完全不同的实际干预强度，以及一个 chat-template structural token 是否足以改变攻击与 collapse 的结论。
