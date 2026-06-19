# Activation Steering 防御课题审稿式建议归档

当前课题建议按两篇论文组织：

- Paper 1：`mechanism audit / reproducibility + evaluation correction`
- Paper 2：`phase-aware defense method`

完整路线见 [two_paper_roadmap.md](/D:/llama_prefix/two_paper_roadmap.md)。

## 1. 总体判断

目前这个课题具备继续推进成论文的潜力，但不建议把论文主线写成“Rogue 攻击加入随机向量，我再把它加回去或抵消掉”。如果这样表述，审稿人很容易认为这只是针对单一攻击实现的局部补丁，威胁模型偏弱，创新性不足。

更有论文价值的主线应当是：

> Activation-steering 攻击和防御强烈依赖 generation phase 与 KV cache 语义；现有复现/实现存在 prefill-only 与 claimed generation-time attack 的错位。本文提出 phase-aware、norm-calibrated 的动态激活防御，在不显著损害正常生成的情况下抑制 rogue steering。

也就是说，论文不应只强调“防御 Rogue”，而应强调你发现了 activation-level attack/defense 中一个容易被忽略但非常关键的实验范式问题：prefill、decode、use_cache、mask 以及生成阶段 hook 的语义会显著改变攻击和防御结论。

## 2. 当前已有工作的主要价值

### 2.1 Rogue 复现差异不是普通误差，而是实现语义问题

你发现 Rogue v1 公开代码中使用 `use_cache=True`，但 hook 的 mask 逻辑会导致生成阶段 token 没有真正被 steering。具体表现是：

- prefill 阶段完整 prompt 前向传播时会注入 steering；
- decode 阶段 `seq_len == 1`；
- mask 被截断为 `mask_fixed[:1]`；
- 如果第一个位置是 special/system/padding 相关 token，则 mask 为 0；
- 后续 generated tokens 实际没有直接受到攻击向量干预。

因此，v1 公开代码更像是 prefill poisoning，而不是论文描述中持续作用于 generated tokens 的攻击。这个发现本身可以形成一个 reproducibility / implementation audit 类型的贡献。

写作时建议谨慎措辞：不要直接说作者“论文和代码不一致”或“攻击造假”，而是表述为：

> We observe that the public v1 implementation and the generation-phase description are not fully aligned under `use_cache=True`. In particular, the steering hook effectively operates on the prefill pass, while generated-token states are not consistently steered by the intended mask.

### 2.2 修复 decode steering 后，模型出现退化，这本身是重要发现

你在修复 generated-token steering 后观察到：

- ASR 可能显著下降；
- 但模型出现复读、乱码、语义混乱、特殊 token 泄露、回答崩溃等现象；
- layer 14 / 18 尤其明显；
- 这说明 ASR 降低不一定代表防御成功，也可能只是模型生成能力被破坏。

这个发现非常关键。它意味着 activation steering 防御不能只报告 ASR，还必须报告生成质量和病态生成指标。

建议把这一点提升为论文中的核心论断：

> Direct decode-time steering may suppress unsafe completions, but it can also induce representation collapse. Therefore, safety evaluation based solely on ASR can overestimate defense effectiveness.

### 2.2.1 Rogue 的攻击强度协议也必须成为复现对象

另一个不能再弱化处理的点是 Rogue 的强度标定。根据其论文描述，攻击强度不是单独扫描一个最终系数，而是：

```text
alpha = c * mu^(l)
```

其中：

- `c` 是无量纲倍率
- `mu^(l)` 是模型和层依赖的平均激活范数

这意味着：

- 如果你只用固定 `alpha`，可以做阶段语义审计
- 但如果你声称“复现 Rogue 的数值结果或 ASR 曲线”，就必须把 `mu` 纳入

更重要的是，`mu` 本身会受到下面这些实现因素影响：

- system prompt
- padding side
- structural token 过滤策略
- dtype

所以后续实验不能再把“强度差异”简单理解为一个 `c` 扫描问题，而应当拆成：

- `fixed-alpha semantic audit`
- `Rogue-faithful calibrated reproduction`

### 2.3 点积不是错误，但需要从“余弦相似度”改写为“有符号投影”

你原始选题中写的是“余弦相似度”，但实际实验中根据情况使用了点积。这个地方如果不解释，会被审稿人认为方法描述和实现不一致。

建议不要把它当成失误，而是主动改写为设计选择：

> 我们使用安全方向上的有符号投影分数，而不是单纯余弦相似度。

形式可以写为：

```text
s = h · v_safe_hat
```

其中 `v_safe_hat` 是归一化后的安全方向。这样，分数同时包含两部分信息：

- 方向是否与安全/拒绝方向对齐；
- 当前 hidden state 的激活幅度是否异常。

这与 Qwen 实验中观察到的 attention sink、结构性 token 范数爆炸现象是匹配的。换句话说，点积不是随意替代余弦相似度，而是为了捕捉“方向 + 范数”的联合异常。

后续需要补充 ablation：

- cosine-only；
- norm-only；
- dot / projection-only；
- projection + norm；
- 去除 system/user/newline 等结构 token 后的 projection。

这样才能证明点积是必要设计，而不是实现偏差。

## 3. 当前工作的主要短板

从优秀审稿人角度看，目前最可能被质疑的点包括：

1. **威胁模型不够清楚。** 如果攻击者能够直接修改 hidden states，那他是否也能关闭你的 defense hook？你的方法到底防的是白盒内部攻击、插件式推理攻击，还是服务端不可见的外部 jailbreak？需要明确。

2. **攻击覆盖不足。** 目前主要围绕 Rogue random steering。后续至少应加入 optimized adversarial vector、SAE feature vector、refusal-suppression vector、universal jailbreak prompt 等更强攻击。

3. **防御是否只是在破坏模型。** ASR 下降可能来自模型退化，而不是安全能力提升。因此必须报告 ARR、重复率、乱码率、EOS 异常率、平均长度、正常任务表现。

4. **阈值和强度是否过拟合。** `k`、`base0`、层选择、阈值 `T` 是否在测试集上调优？需要划分 train / validation / test。

5. **PPL 指标不够。** 你记录中 PPL 基本不变，但 PPL 对 instruction-following 和对话质量不敏感。需要加入更贴近正常能力的指标。

6. **Qwen 的 tokenizer、padding、chat template、attention sink 处理需要标准化。** 你已经发现这些因素会显著影响结果，后续必须把它们写成明确的实验控制变量。

## 4. 建议的下一步实验

下一步不建议直接大规模跑防御，而应先完成一个 phase-aware attack reproduction matrix。

### 4.1 Phase-aware attack reproduction matrix

固定模型、层、随机种子、chat template、padding、mask、steering norm 归一化方式，然后比较以下条件：

| 编号 | 设置 | 目的 |
|---|---|---|
| A | Rogue v1 原始代码，`use_cache=True`，prefill-only | 复现公开代码真实行为 |
| B | `use_cache=False`，每步全序列 forward steering | 检查无 KV cache 时攻击语义 |
| C | 修复 decode hook，只 steering generated tokens | 验证 generated steering 是否导致退化 |
| D | prefill + decode 都 steering | 验证持续攻击的上限和副作用 |
| E | prefill + first-k decode 或 exponential decay | 检查早期生成 token 是否是关键窗口 |
| F | prefill base defense + decode ReLU gated defense | 验证你的 phase-aware 防御 |

每组至少报告：

- ASR；
- refusal rate；
- abnormal refusal / pathological generation rate；
- repetition rate；
- average output length；
- special token leakage；
- normal utility；
- latency overhead。

### 4.2 防御方法建议收敛为 phase-aware dynamic guard

建议方法形式：

```text
s_l,t = zscore(h_l,t · v_safe_l_hat)
```

其中：

- `l` 表示层；
- `t` 表示 token 位置；
- `v_safe_l_hat` 是第 `l` 层归一化后的安全方向；
- z-score 使用 benign calibration set 统计得到。

防御强度可以继续沿用你的思路：

```text
C(s) = C_base + k · ReLU(s - T)
```

但建议强调：

- prefill 阶段使用轻量 base correction；
- decode 阶段只在异常分数越阈值时介入；
- 对 generated tokens 的干预应限制在 first-k tokens 或使用 decay；
- 避免全程强 steering 导致 representation collapse。

### 4.3 Norm / attention sink 的处理必须系统化

你已经观察到 Qwen 中结构性 token 会导致 hidden norm 爆炸。建议加入以下控制：

- 过滤 special token；
- 过滤 system/user/assistant/chat-template marker；
- 过滤连续 newline；
- 使用 trimmed mean 或 median，而不是简单均值；
- 分别报告 filtered 与 unfiltered 结果；
- 对每个模型单独校准 `mu_layer`。

这部分可以成为方法鲁棒性的亮点。

## 5. 指标体系建议

不要只使用 ASR 和 PPL。建议最终指标包括：

| 指标 | 作用 |
|---|---|
| ASR | 有害请求成功率，越低越好 |
| FRR / UFR | 正常请求被错误拒绝的比例，越低越好 |
| ARR | 异常拒绝率，包括乱码、复读、崩溃、特殊 token 泄露 |
| Repetition Rate | 衡量 decode steering 是否造成循环输出 |
| Special Token Leakage | 衡量控制符泄露 |
| Avg. Output Length | 防止模型通过过早结束规避 ASR |
| Utility Benchmark | 正常任务能力，例如 AlpacaEval、MT-Bench、MMLU、GSM8K 子集 |
| Latency Overhead | 推理阶段防御的实际成本 |

其中 ARR 是你现在很值得保留的创新性指标，因为它能解释为什么“ASR 降低”并不等价于“安全提升”。

## 6. 论文定位建议

如果论文只写成：

> Rogue 加了随机向量，我们加安全向量抵消。

那么创新性偏弱，可能只能作为 workshop 或实验报告。

如果论文写成：

> Cache-aware and phase-aware defense against activation steering attacks。

则更有机会形成完整论文。建议贡献点写成：

1. **Reproducibility finding：** 揭示 activation steering 攻击在 `use_cache=True` 下存在 prefill/decode 语义错位，系统分析公开 Rogue v1 实现与 generation-time attack 描述之间的差异。

2. **Evaluation finding：** 证明 generated-token steering 容易导致 representation collapse，因此仅用 ASR 会高估攻击或防御效果，提出 ARR 等病态生成指标。

3. **Defense method：** 提出 phase-aware、norm-calibrated activation guard，在多模型、多层、多攻击强度下，相比静态 safety vector、norm clipping、SCANS 类方法，更好地平衡 ASR 与正常能力。

## 7. 建议标题

可选标题：

- Cache-Aware Activation Guardrails for Defending Against Steering Attacks
- Phase-Aware Defense Against Activation Steering Attacks in Large Language Models
- When Steering Happens Matters: Cache-Aware Evaluation and Defense for Activation-Level Attacks
- Beyond ASR: Detecting Representation Collapse in Activation Steering Defenses

## 8. 两篇论文拆分建议

### 8.1 Paper 1 应怎么写

Paper 1 的主线应固定为：

1. `use_cache=True` 下 Rogue v1 的阶段语义未完全对齐
2. 真正的 generated-token steering 会引入 collapse 风险
3. 因此 activation steering 评估不能只看 `ASR`

这篇的贡献类型是：

- reproducibility finding
- mechanism explanation
- evaluation correction

这篇不要承担“完整动态防御优于所有基线”的方法负担。

### 8.2 Paper 2 应怎么写

Paper 2 建立在 Paper 1 的发现之上，回答：

> 既然 steering 的生效阶段决定结论，那么安全向量为何必须动态且 phase-aware 地插入？

方法表述应改成：

- 防御的是 `inference-time activation deviation`
- 不是简单“把 Rogue 随机向量减回去”
- prefill 轻量校正，decode 阶段阈值触发
- 只对 `first-k` 或 `decay` 窗口介入

### 8.3 投稿层级判断

- Paper 1：更适合 workshop、short paper、应用型会议或中上水平期刊
- Paper 2：如果 harmful / harmless / utility / latency 与多模型闭环做完整，投稿潜力明显高于 Paper 1

## 9. 最终建议

当前最优路线不是马上继续堆更多防御实验，而是先把“Rogue 复现 + use_cache 语义 + prefill/decode 差异 + decode collapse”这条线写扎实。然后让你的防御方法自然服务于这个发现。

也就是说，论文核心不应是“我修补了 Rogue”，而应是：

> 我们发现 activation steering 的攻击和防御结论高度依赖生成阶段语义；如果不区分 prefill 与 decode，不仅会错误理解攻击强度，也会把模型退化误判为安全提升。基于这一点，我们提出了 phase-aware 的动态激活防御。

这个角度比单纯“把随机向量加回去”更有研究价值，也更容易说服审稿人。
