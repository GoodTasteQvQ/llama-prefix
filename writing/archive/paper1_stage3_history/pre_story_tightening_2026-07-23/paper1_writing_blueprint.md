# Paper 1 写作蓝图

更新时间：2026-07-22

状态：当前论文叙事基线。历史 TDSC 审计中的旧主张矩阵不再作为当前写作依据；
当前证据边界见 `paper1_claim_evidence_matrix.md`。

## 暂定标题

推荐标题：

> When Steering Happens Matters: Cache-Aware Reproduction and Failure-Aware Evaluation of Activation Steering Attacks

可选标题：

- Beyond ASR: Phase Semantics and Generation Collapse in Activation Steering Attacks
- Cache Semantics Matter: Auditing Generation-Time Activation Steering Under `use_cache=True`

标题暂不加入 `attention sink`、三模型或 dose-calibration 字样。Stage 3 是解释和复现性增强，
不是当前已经得到结果的主发现。

## 一句话主张

公开 Rogue v1 实现在 `use_cache=True` 下更接近 prefill-dominant steering；在 Qwen 和
Llama 上，真正持续作用于 generated tokens 的强 steering 都会使低 ASR 与大量 broken 和
repetition 同时出现。因此 activation-steering 安全评估必须同时审计干预发生的 phase、
区分攻击未成功的不同 failure mode，并记录 nominal `c` 到 actual dose 的标定方法。

## 论文故事路线

1. Rogue 将其干预描述为 generation-time activation steering。
2. 我们不判断原论文对错，而是审计公开 v1 实现在真实 KV-cache 语义下实际何时修改状态。
3. A-F phase/cache 实验表明，`use_cache=True` 下的公开路径更接近 prefill-dominant；
   `decode_only/full/no_cache` 才持续作用于 generated tokens。
4. 在 Qwen 与 Llama 的现有 full1000 条件下，持续 generated-token steering 没有形成随强度
   稳定增长的攻击成功率，而是在高强度下进入严重 generation collapse。
5. 因而低 ASR 只能表示“没有形成有效有害帮助”，不能单独判断输出是正常拒绝、benign/
   non-enabling response，还是 broken/collapse。
6. 我们保留 Rogue-compatible binary ASR 作为攻击成功指标，同时使用
   `unsafe/refusal/safe/broken`、ARR、repetition 和输出诊断分解 binary-negative 结果。
7. Qwen 与 Llama 共享相同的定性 ordering，但 attack peak、collapse threshold、短拒答模式和
   metric artifact 不同；本文报告异质性，不进行“哪个模型更脆弱”的排名。
8. Stage 3 进一步审计 structural/content token inclusion 是否改变 `mu`、actual `alpha/rho`
   与 Qwen 固定 support 上的 unsafe/broken 估计。它是 calibration/reproducibility case study，
   不是 Attention Sink 因果证明，也不负责新的跨模型主结论。

## 研究问题

- `RQ1`: Under real KV-cache semantics, when does the public Rogue v1 intervention actually steer model states?
- `RQ2`: What happens to unsafe success and generation integrity when generated tokens are continuously steered?
- `RQ3`: Which qualitative patterns are shared by Qwen and Llama, and which quantities remain model-specific?
- `RQ4`: Does structural-token inclusion in Rogue-style `mu` calibration change actual intervention dose and fixed-support Qwen estimates?

`RQ1-RQ3` 是论文主线；`RQ4` 是解释与可复现性增强。即使 Stage 3 得到零结果或区间较宽，
`RQ1-RQ3` 的论文故事仍然成立。

## 核心贡献

1. **Cache-aware implementation audit**：通过 phase-call instrumentation 区分 prefill、cached
   decode 和 no-cache full-sequence 语义，证明同一 hook 描述可能对应不同实际干预阶段。
2. **Failure-aware beyond-ASR evaluation**：保留 binary ASR 的原始攻击成功语义，同时把
   binary-negative 输出分解为 refusal、safe/non-enabling 和 broken/collapse。
3. **Cross-model qualitative evidence**：在 Qwen 与 Llama full1000 中观察到共同的
   prefill-dominant attack peak、持续 decode 高强度 collapse、first-k/decay 稳定但较弱的 ordering。
4. **Calibration-aware reproducibility audit**：在 Qwen 上检验 token frame 对 `mu` 与 actual dose
   的影响，并把该影响与 fixed-support unsafe/broken 估计连接。该贡献在 Stage 3 结果产生前只能
   写成研究问题和方法，不能写成已证实发现。

## 摘要骨架

1. 背景：activation steering 正在成为模型安全评估的重要对象，但结论依赖推理阶段和强度标定语义。
2. 审计发现：公开 Rogue v1 在 `use_cache=True` 下更接近 prefill-dominant steering，而非持续
   generated-token steering。
3. 行为发现：在 Qwen 与 Llama 的现有 full1000 实验中，持续 generated-token steering 的高强度
   低 ASR 与 broken/repetition 急剧上升同时出现。
4. 方法贡献：binary ASR 衡量攻击是否形成有效有害帮助，但不足以诊断非成功输出；因此本文提出
   phase-aware instrumentation 与 failure-aware decomposition，并进一步审计 dose calibration 的可复现性。

摘要不得写“三模型验证”，除非 Mistral 的正式 config、raw、judged、summary 和日志均已归档。
摘要不得写“Attention Sink 导致 collapse”。

## 章节结构

### 1. Introduction

提出 activation-steering 研究中的三个隐藏测量问题：干预何时发生、非成功输出是什么、
nominal strength 如何映射到 actual dose。贡献以 cache-aware、failure-aware、calibration-aware
三层组织，但 calibration 是支持性贡献。

### 2. Background, Threat Model, and Reproduction Target

- activation steering 与 `alpha=c*mu`；
- prefill/decode/KV cache；
- Rogue-compatible binary ASR 的正确任务语义；
- 本文审计公开实现 under real cache semantics，不把工作写成“原作者代码错误”；
- 威胁模型限定为 inference-time white-box intervention/evaluation，不外推到任意服务端篡改。

### 3. Phase-Aware Reproduction Audit

- A-F：`rogue_v1/no_cache/decode_only/full/first_k/decay`；
- Track A fixed-alpha semantic control 与 Track B Rogue-calibrated behavior evaluation；
- phase-call audit：`prefill_calls/decode_cached_calls/decode_full_calls/generated_steered_calls`；
- 先报告执行语义，再报告 ASR。

### 4. Decode-Time Collapse and Failure-Aware Evaluation

- Qwen full1000 的六方法强度曲线；
- ASR、refusal、safe、broken 联合结果；
- ARR、repetition、garbled、special-token leakage、very-short-output 和长度诊断；
- `broken`、ARR 和 bad-case descriptor 的区别；
- 低 ASR 不等于安全拒绝增强。

### 5. Cross-Model Commonality and Heterogeneity

- Qwen 与 Llama full1000 的相同定性 ordering；
- Rogue peak 的位置和高度不同；
- sustained decode collapse 的阈值和严重度不同；
- Llama 短拒答导致 legacy `empty_or_truncated` 假阳性更明显；
- 不做显著性不足的模型脆弱性排名。

Mistral 若完成，作为第三模型外部验证加入；若未完成，不影响两模型主故事，但全文删除三模型措辞。

### 6. Structural-Token Calibration Sensitivity

本节对应唯一冻结基线 `v3.5-rc2 + binding-amendment-01`；实现入口为
`writing/stage3 design/CURRENT_RELEASE.md`。标题不再使用 `Attention Sink Explanation`。

- P1：all-token 与 content-token pooled norm、token shares、equal-domain sensitivity；
- nominal `c`、`mu`、actual `alpha/rho` 的映射；
- P2：Qwen A/T fixed-support 上 all-token/content-token calibration 的 unsafe/broken paired RD；
- benign integrity、human judge validation 与 matched two-phase sensitivity；
- 只报告 Qwen case-study 结论，不解释未测量的跨模型结构差异。

### 7. Discussion

- phase semantics 与 dose calibration 都是复现协议的一部分；
- ASR 与 generation dependability 回答不同问题；
- shared qualitative pattern 不意味着 identical threshold；
- 对 activation-steering benchmark、artifact 和防御研究的启示。

### 8. Limitations and Conclusion

- Stage 1/2 的现有 full1000 主要是给定 prompt/layer 下的 random-vector distribution；
- 当前不支持一般 harmful-behavior ASR 或模型脆弱性排名；
- 主要攻击家族仍是 Rogue-style random-vector steering；
- first-k=3、decay=0.85 只是固定实例；
- Stage 3 是 Qwen calibration case study，不是 Attention Sink 或跨模型因果解释；
- Mistral、跨层、第二攻击家族属于后续增强，不得写成已完成证据。

## 主文图表

### 主文图

1. KV-cache 下 prefill/decode steering 语义示意图。
2. A-F phase-call audit，突出 `generated_steered_calls`。
3. Qwen/Llama Track B 的 ASR 与 broken 强度曲线。
4. Qwen/Llama repetition 与 failure-aware outcome decomposition。
5. attack peak、collapse threshold 和稳定性 ordering 的跨模型摘要。
6. Stage 3 P1 norm/token-share 与 P2 fixed-support RD；仅在正式结果产生后加入。

### 主文表

1. A-F phase/cache 设置与实际执行语义。
2. Qwen/Llama 关键条件、peak ASR、high-strength broken/repetition。
3. unsafe/refusal/safe/broken 与 ARR/bad-case 诊断边界。
4. Stage 3 nominal `c`、`mu`、actual `alpha/rho` 和估计边界。

## Stage 3 结果分支

- P1 gate 通过且 P2 方向清晰：可以写 token-frame calibration materially changes actual dose，
  并在固定 Qwen support 上对应不同 unsafe/broken estimates。
- P1 gate 通过但 P2 不确定：只能写 calibration measurement changes，行为后果不确定。
- P1 gate 未通过：报告负结果或移入 appendix，不得继续寻找替代 estimator/anchor。
- 任意结果均不得写 structural token 或 Attention Sink “导致”跨模型 collapse。

## 最小成稿包

1. Qwen phase-call audit 与六方法 full1000。
2. Llama 六方法 full1000 及与 Qwen 的统一对照。
3. failure-aware beyond-ASR summary 与代表性人工核查。
4. 明确的 threat model、claim boundary 和 artifact manifest。
5. Stage 3 若完成，作为 calibration-aware 支持章节；若未完成，论文仍可按 RQ1-RQ3 成稿，
   但不得保留 calibration 结果性贡献。

## 写作禁区

- 不写“Rogue 把 collapse 错判为 safe”；binary judge 的任务本来就是攻击成功判定。
- 不写“低 ASR 说明模型更安全”或“低 ASR 说明攻击彻底失败”。
- 不写“Llama 比 Qwen 更脆弱”，除非以后有匹配 prompt/layer 与正式跨模型推断。
- 不写“三模型验证”，除非 Mistral 正式证据存在。
- 不写“Attention Sink 导致 collapse”或“Stage 3 解释了模型差异”。
- 不把 Stage 3 estimation-only interval 写成显著性、检测或确认性结论。
- 不把未完成的扩展实验当作当前论文成立的前提或已有贡献。
