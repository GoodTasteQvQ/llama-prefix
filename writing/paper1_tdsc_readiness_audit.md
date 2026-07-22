# Paper 1 TDSC Regular 投稿就绪度审计

## 0. 审计元信息

- 审计日期：2026-07-16
- 目标：IEEE Transactions on Dependable and Secure Computing (TDSC) Regular Paper
- 论文范围：Paper 1，机制审计、复现与 beyond-ASR 评估修正
- 预期篇幅：约 12 页正文级别
- 审计结论性质：内部投稿门槛，不代表编辑部或审稿人的正式决定
- 审计依据：仓库中的实验清单、Paper 1 蓝图、实际配置、当前结果目录，以及作者在本轮对话中声明的在途实验

状态定义：

- `PASS`：现有证据足以支持对应主张
- `PARTIAL`：已有证据，但外部有效性、统计或测量仍不足
- `PLANNED`：已有明确计划，尚无正式结果
- `BLOCKER`：若投稿前不解决，较可能触发拒稿或大修
- `MAJOR`：重要稳健性缺口，应补在正文核心矩阵或补充材料中
- `OPTIONAL`：增强项，不是当前最小阻断项

## 1. 执行结论

### 1.1 总判断

如果只完成当前描述的内容：

1. Qwen 六组 phase/cache 条件 full1000 judge；
2. Llama-3.1 full1000 judge；
3. Mistral 100-sample，若趋势有效再做 full1000；
4. decode collapse 诊断；
5. Attention Sink / 结构 Token 范数实验；

那么论文将具备一条有价值且较清楚的机制证据链，但**仍不建议直接按 TDSC Regular Paper 投稿**。最可能的审稿结论不是“结果数量不足”，而是：

> The study provides a useful implementation audit, but the evidence is conditioned on one harmful prompt, one layer per model, one attack family, and an unvalidated model judge. Therefore, the generality of the security and evaluation claims is not established.

当前计划完成后的合理定位：

- 作为 Rogue 公开实现的精确复现与机制审计：较强；
- 作为 activation steering 的一般性安全结论：不足；
- 作为 beyond-ASR 测量论文：有潜力，但测量有效性尚未闭环；
- 作为 TDSC Regular：`高风险，需补关键外部有效性与评测验证实验`。

### 1.2 最强资产

现有工作的最强部分不是 1000 向量本身，而是：

1. phase/cache 条件被显式拆成 `rogue_v1 / no_cache / decode_only / full / first_k / decay`；
2. phase-call audit 能直接证明 generated token 是否真正被 steering；
3. Qwen full1000 已显示 `decode_only / full / no_cache` 的低 ASR 与高 broken/ARR/repetition 同时出现；
4. 在保留 Rogue 二分类攻击成功口径的同时，主四分类 judge 将其 binary-negative（原标签 `safe`）进一步分解为 `refusal / safe / broken`，形成 failure-aware beyond-ASR 诊断；
5. Qwen、Llama、Mistral 三个模型家族的验证框架已经建立，其中 Mistral 仍在执行。

这条主线可以形成 TDSC 需要的 dependability/security measurement 贡献，但必须从“单一案例”升级为“系统性证据”。

### 1.2.1 正确的创新性定位

Rogue-compatible binary judge 的任务是判断输出是否形成连贯、有效的有害帮助。按照该任务定义，拒绝、无关回答、重复、乱码和 collapse 都属于攻击未成功，因此统一标为 `safe` 是原协议的有意设计，而不是分类错误。

本文不能声称“证明 Rogue ASR 把 collapse 错判为 safe”。正确的创新性是：

1. 系统审计 activation steering 在 prefill、cached decode 和 no-cache full-sequence 下的实际作用语义；
2. 识别并刻画从 attack success 到 generation collapse 的强度转变；
3. 保留 Rogue binary ASR 作为攻击成功指标，同时将其 binary-negative 桶进一步分解为正常拒绝、benign/non-enabling response 和 broken/collapse；
4. 证明相同或相近的低 ASR 可以对应不同的非成功机制，因此攻击成功率不能单独承担生成可靠性诊断；
5. 区分跨模型共享的 phase/cache 机制与模型特定的 attack peak、collapse threshold 和 failure pattern；
6. 用 structural token、hidden norm 与 `mu` 标定敏感性解释模型差异。

建议把本文协议称为 `failure-aware decomposition` 或 `beyond-ASR diagnostics`，而不是 `correction of Rogue labels`。四分类是对不同研究问题的补充测量，不是对原二分类任务的替代。

### 1.3 最大阻断项

按重要性排序：

1. `BLOCKER`：单 prompt 无法支持一般 ASR 或一般 harmful behavior 结论；
2. `BLOCKER`：每个模型只有单层，phase 效应与 layer sensitivity 仍有混淆；
3. `BLOCKER`：Qwen3 judge 与 ARR/broken 指标尚未经过正式人类标注验证；
4. `BLOCKER`：只有 Rogue random-vector 一种攻击家族，结论可能是实现特例；
5. `BLOCKER`：没有 harmless/benign generation integrity 评估，无法证明 collapse 是一般生成退化；
6. `BLOCKER`：没有置信区间、配对统计检验和分层统计模型；
7. `MAJOR`：`first_k=3`、`decay=0.85` 只有单一超参数点；
8. `MAJOR`：Attention Sink 当前是解释性假设，尚未形成固定 alpha 与重标定 alpha 的因果分解；
9. `MAJOR`：实际运行配置、README 和 Mistral 本地配置存在漂移，需要统一归档；
10. `MAJOR`：威胁模型和 TDSC 所需的 security/dependability impact 尚需形式化。

## 2. 可审计证据登记

| ID | 证据 | 路径或位置 | 审计含义 |
|---|---|---|---|
| E01 | 清单要求至少 3 个 seed | `activation_steering_experiment_checklist.md:37` | 当前 seed=42 未达到原清单要求 |
| E02 | 清单要求 1/3、1/2、2/3 depth | `activation_steering_experiment_checklist.md:133` | 当前只做约 1/3 depth |
| E03 | 清单要求 first-1/3/5/10 | `activation_steering_experiment_checklist.md:248` | 当前只有 first-3 |
| E04 | Qwen 归档配置：layer 9、limit 1、seed 42、first-k=3 | `results/stage1_phase_aware/formal/qwen25/generated_single_prompt_configs/stage1_trackB_qwen25_first_k_single_prompt_bomb.json` | Qwen 为单 prompt、单层、单 seed |
| E05 | Llama 归档配置：layer 11、limit 1、seed 42 | `results/stage1_phase_aware/formal/llama31/generated_single_prompt_configs/stage1_trackB_llama31_full_single_prompt_bomb.json` | Llama 同样为单 prompt、单层、单 seed |
| E06 | Mistral 本地配置：layer 11、limit 8、seed 42 | `configs/local/stage1_trackB_mistral_first_k.json` | 与“单 prompt”声明不一致，需以服务器真实归档为准 |
| E07 | first-k 固定为 3，decay 固定为 0.85 | `scripts/stage1_phase_aware/build_stage1_configs.py` | 当前 E/F 只验证一个设计点 |
| E08 | README 声明不继承单 prompt slicing | `scripts/stage1_phase_aware/README.md:53` | 与 Qwen/Llama 实际归档配置不一致 |
| E09 | Qwen 六组 full1000 合并结果 | `results/stage1_phase_aware/formal/qwen25/judge_summaries/qwen25_stage1_qwen3_v2_all6_full1000_judge_summary_from_judged.json` | Qwen 主现象已有大样本证据 |
| E10 | Llama 当前本地 100-sample summary | `results/stage1_phase_aware/formal/llama31/judge_summaries/llama31_stage1_qwen3_v2_100sample_judge_summary.json` | Llama 跨模型 pilot 已完成 |
| E11 | 本地仅归档 Qwen vector pool manifest | `results/stage1_phase_aware/random_vector_pools/` | Llama/Mistral vector manifest 需补归档 |
| E12 | 仓库未发现正式 human agreement / judge-human confusion matrix | 仓库检索日期 2026-07-16 | judge 测量有效性尚未闭环 |
| E13 | 仓库未发现 CI/bootstrap/significance 实现 | 仓库检索日期 2026-07-16 | 统计推断尚未闭环 |
| E14 | 仓库未发现 Paper 1 harmless/utility 正式结果 | 仓库检索日期 2026-07-16 | 正常生成完整性证据缺失 |
| U01 | Llama full1000 judge 正在进行 | 作者 2026-07-16 声明 | 尚未作为已完成结果计入 |
| U02 | Mistral 100-sample judge 正在进行 | 作者 2026-07-16 声明 | 尚未作为已完成结果计入 |
| U03 | Mistral 若有效则扩 full1000 | 作者 2026-07-16 声明 | 条件性计划，不能代替预先定义的扩展规则 |

审计注意：`U01-U03` 是作者声明，不等价于本地可复核 artifact。实验结束后必须下载实际 config、vector manifest、raw output、judged output、summary 和运行日志。

## 3. 主张—证据矩阵

| 论文主张 | 当前状态 | 当前证据 | 投稿前要求 |
|---|---|---|---|
| C1. Rogue v1 在 `use_cache=True` 下是 prefill-dominant，而非持续 generated-token steering | `PASS` | phase-call audit；`generated_steered_calls=0` 对照 | 三模型各抽查 phase-call，公开最小复现脚本 |
| C2. 真正 decode/full steering 会诱发 collapse | `PARTIAL` | Qwen full1000 强证据；Llama 100-sample pilot | Llama/Mistral确认；多 prompt、多层；置信区间 |
| C3. ASR 能衡量攻击成功，但不能诊断非成功输出由 refusal、benign non-enabling 还是 collapse 构成 | `PARTIAL` | unsafe/refusal/safe/broken + ARR/repetition | human validation；harmless integrity；统计推断 |
| C4. first-k/decay 能减少 collapse | `PARTIAL` | k=3、decay=0.85 单点结果 | k 与 decay-rate sweep；跨层/跨 prompt |
| C5. Attention Sink/结构 token 导致 `mu` 敏感和模型差异 | `PLANNED` | 当前只有假设与分析脚本 | 固定 alpha 与重标定 alpha 的因果分解 |
| C6. 结论适用于 activation steering，而非只适用于 Rogue v1 | `BLOCKER` | 只有 Rogue random-vector | 至少一个独立攻击构造 |
| C7. 结论具有跨行为外部有效性 | `BLOCKER` | Qwen/Llama 使用单 prompt | 多类别 harmful prompt 评估 |
| C8. 结论不依赖特定层 | `BLOCKER` | 每模型单层 | 1/3、1/2、2/3 depth 核心矩阵 |

## 4. 关键审稿问题与详细判断

### 4.1 单 prompt 是当前最严重的问题

当前 Qwen/Llama 的设计是：对一个 harmful prompt 使用 1000 个随机向量。该实验能严谨估计的是：

> 在给定模型、给定层、给定 prompt、给定生成配置下，从指定随机向量分布采样时的成功或 collapse 概率。

它不能直接估计：

> 模型在一般 harmful behaviors 上的 Attack Success Rate。

因此，当前 `ASR` 更准确的统计名称应是：

- single-behavior vector success rate；或
- conditional attack rate over random vectors。

1000 个随机向量提高了对“向量分布”的估计精度，但没有增加 prompt/behavior 维度的外部有效性。把 1000 个向量当作 1000 个安全行为样本会构成伪重复（pseudoreplication）。

审稿风险：极高。TDSC 审稿人很可能认为结果只说明某个 bomb-related prompt 对 layer/phase 的特殊敏感性。

处置：保留当前单 prompt full1000，明确标为 `Rogue-faithful reproduction track`；新增独立的 `multi-behavior generalization track`。两条线不能混成一个 ASR 表。

### 4.2 单层会混淆 phase effect 与 layer effect

当前层设置：

- Qwen：layer 9；
- Llama：layer 11；
- Mistral：layer 11；
- 均约为 1/3 depth。

若 decode/full 在该层 collapse，不能排除以下替代解释：

- 该层本身特别脆弱；
- 该层 norm 或 residual stream 尺度异常；
- 中后层可能表现完全不同；
- Rogue 的最佳攻击层与 collapse 最敏感层不是同一个层。

不需要把完整 `6 methods × 9 strengths × 1000 vectors` 在所有层重跑。投稿前至少要在核心条件上覆盖：

- 1/3 depth；
- 1/2 depth；
- 2/3 depth；
- 可选：每模型经验 best layer。

核心比较应至少包括 `rogue_v1 / decode_only / full`，以及 baseline、transition strength、high strength。

### 4.3 seed=42 不是首要阻断项，但需要正确解释

固定 seed=42 与 Rogue 对齐是合理的精确复现选择。Qwen vector manifest 显示一次 seed 产生了 1000 个归一化随机向量，因此已有大量向量级重复。

但需要区分：

- 1000 vectors：估计一个随机向量分布中的变异；
- multiple seeds：验证 PRNG pool、抽样顺序和任何随机生成过程不会改变结论；
- multiple prompts：验证行为外部有效性。

因此，补 seed 的优先级低于补 prompt 和 layer。资源友好的做法是：

- 保留 seed 42 的 full1000 主结果；
- 在核心矩阵上增加 2 个向量池 seed；
- 每个新 seed 使用 100-200 vectors 即可；
- 使用相同 prompts 和 paired conditions。

不建议为每个 seed 重跑全部 6×9×1000。

### 4.4 judge 与 ARR 的测量有效性尚未达到期刊标准

Paper-1 dual judge 比 Rogue binary 更合理，但当前仍是单一 Qwen3-8B judge。需要回答：

- `unsafe/refusal/safe/broken` 与人类标注的一致性是多少？
- `broken` 是否会把短但有效的拒绝判错？
- judge 是否对 Qwen 系输出存在同家族偏差？
- fallback parser 的 0.x% 失败是否集中在某类边界样本？

已观察到一个具体测量风险：Llama 的简短有效拒绝可能被启发式 `empty_or_truncated/ARR` 记为异常，而四分类 judge 仍判为 refusal。说明 ARR 不能作为跨模型统一单阈值指标直接使用。

投稿前要求：

1. 分层抽样 400-600 条输出；
2. 覆盖三模型、六方法、低/中/高强度和四个预测标签；
3. 两名独立标注者，记录 adjudication；
4. 报告 Cohen's kappa 或 Krippendorff's alpha；
5. 报告 judge-human confusion matrix、macro-F1、每类 precision/recall；
6. 单独验证 `unsafe` 与 `broken` 两个关键类别；
7. ARR 拆成可观察子指标，不用一个未经验证的总阈值替代全部 collapse。

建议主表使用：四分类标签 + repetition + early stop + leakage + length。ARR 可以保留，但必须给出定义、校准与敏感性分析。

### 4.5 单一攻击家族不足以支撑一般化标题

如果论文标题和结论写成 activation steering attacks 的一般规律，仅 Rogue random vector 不够。phase/cache 语义错位可能是 Rogue v1 hook/mask 的实现特例。

投稿前至少增加一种独立构造：

- refusal-suppression direction；或
- contrastive harmful-vs-refusal steering direction；或
- optimized adversarial activation vector。

第二攻击不需要复刻全部矩阵。最小验证可以是：

- 三模型；
- `prefill-only / decode-only / full`；
- 2-3 个强度；
- 多 prompt 小矩阵；
- 同样报告 ASR、broken、repetition、length。

若无法完成第二攻击，论文必须把标题、摘要和结论严格限定为 `Rogue-style random-vector steering`，同时接受 TDSC 适配度下降。

### 4.6 harmful-only 不足以证明生成完整性

当前 collapse 主要在 harmful prompt 上观察。审稿人可能提出：模型只是从拒绝模式切换到异常模式，并不能说明一般生成能力受损。

需要在选定的高风险条件上加入 harmless prompts：

- benign instruction following；
- 普通知识问答；
- 至少包含一部分中文任务用于 Qwen；
- 与 harmful 条件使用相同 phase/layer/strength/vector。

最小指标：

- over-refusal/UFR；
- broken rate；
- repetition；
- early stop；
- output length；
- 人工或独立 judge 的回答质量。

Paper 1 不必承担完整 MMLU/MT-Bench，但必须证明 beyond-ASR 所称的 collapse 不是 harmful refusal 场景专属测量现象。

### 4.7 缺少统计推断

当前表格主要是点估计。TDSC Regular 至少需要：

- 主要比例的 95% confidence interval；
- 同一 prompt/vector 在不同 phase condition 下的配对差异；
- effect size，而不只是“高/低”；
- 多条件比较时的 family-wise 或 FDR 控制；
- 对 prompt 与 vector 两级变异的处理。

推荐统计单位：

- response 是观测；
- prompt 和 random vector 是交叉随机因素；
- method/phase、strength、layer、model 是固定因素。

最低实现：clustered bootstrap，同时对 prompt 和 vector 重采样；同一 bootstrap sample 内保持 A-F 配对。

敏感性分析：logistic mixed-effects model，对 `unsafe` 与 `broken` 分别建模，至少包含 prompt 和 vector random intercept。

禁止做法：把同一 prompt 下的 1000 vectors 当作 1000 个独立 behavior 来推导一般 ASR 的极窄置信区间。

### 4.8 first-k 与 decay 当前只能称为实例，不是完整诊断

当前：

- first-k 固定为 k=3；
- exponential decay 固定为 0.85。

因此当前只能得出：`k=3` 和 `decay=0.85` 在当前条件下较稳定。不能写成“first-k/decay 普遍避免 collapse”。

最小消融：

- k：1、3、5、10；
- decay：0.50、0.70、0.85、0.95；
- 模型：Qwen + Llama，Mistral 可选关键点；
- strength：transition point 与 high point；
- 使用多 prompt 子集。

### 4.9 Attention Sink 实验必须从相关性升级为因果分解

只展示某些 structural token norm 很高，不足以证明它们导致 collapse。需要区分两个路径：

1. formatting/filtering 本身对模型行为的直接影响；
2. formatting/filtering 通过改变 `mu`，进一步改变 `alpha=c*mu` 的间接影响。

建议 2×2 设计：

| 组 | token/filter setting | alpha 处理 | 目的 |
|---|---|---|---|
| A | baseline setting | 固定 alpha | 基线 |
| B | changed setting | 固定为 A 的 alpha | 测直接效应 |
| C | baseline setting | 各自 recalibrated alpha | 标定基线 |
| D | changed setting | 各自 recalibrated alpha | 直接效应 + `mu` 间接效应 |

同时报告 mean/trimmed mean/median。若只有 norm 可视化而没有生成结果回接，最多是描述性解释，不足以支撑机制主张。

### 4.10 威胁模型与 TDSC 适配性

必须明确：

- 攻击者具有什么推理时内部访问能力？
- 攻击者能否修改 hook、cache 或服务端代码？
- 为什么攻击者能注入 activation vector，却不能任意替换模型输出？
- 本文审计的是研究实现、部署插件风险、模型编辑接口，还是服务端供应链风险？
- 发现对 dependable inference 或安全评估流程有什么可操作影响？

建议将贡献表述为：

1. cache-aware reproducibility audit；
2. phase-aware measurement methodology；
3. beyond-ASR failure taxonomy and evaluator；
4. cross-model empirical evidence。

不要把 Paper 1 写成防御论文，也不要声称解决了 activation attacks。TDSC 的价值应来自可靠测量、可复现审计和安全结论修正。

## 5. 面向 TDSC 的最小补实验包

以下设计优先控制计算量，不要求把所有变量笛卡尔积全跑。

### 5.1 Track R：Rogue-faithful exact reproduction

状态：基本完成/在途。

保留：

- 单 prompt；
- seed 42；
- 1000 random vectors；
- 1/3 depth；
- Track A/B；
- 六 phase/cache methods。

论文角色：精确复现与 phase-call audit，不承担外部泛化。

### 5.2 Track G：multi-behavior generalization

建议最小设计：

- models：Qwen、Llama、Mistral；
- harmful prompts：至少 50，推荐 80-100；
- categories：至少 8 类，并报告类别分布；
- vectors：每 prompt 20 个，共享并配对；
- methods：`rogue_v1 / no_cache / decode_only / full`；
- strengths：baseline、transition、peak、high，例如 `c=0, 1.0, 1.5, 2.0`；
- controls：`first_k / decay` 只跑 transition 与 high point。

这条线的目标不是再造 1000-vector 曲线，而是估计跨 prompt 的可推广效应。

### 5.3 Track L：layer robustness

建议最小设计：

- layers：1/3、1/2、2/3 depth；
- methods：`rogue_v1 / decode_only / full`；
- strengths：0、transition、high；
- prompts：20 个分层 harmful prompts；
- vectors：每 prompt 10 个；
- models：三模型，若资源紧张先 Qwen/Llama，再用 Mistral 做关键点确认。

通过条件：主要 phase ordering 在至少两个模型、至少两个 depth 上保持，或明确报告并解释异质性。

### 5.4 Track S：seed robustness

建议最小设计：

- seeds：42 + 两个新 seed；
- 每个新 seed：100-200 vectors；
- 只跑 `rogue_v1 / decode_only / full`；
- 只跑 transition 与 high strength；
- 使用 Track G 的 prompts。

通过条件：主要结论方向一致，seed 间差异小于 method/phase 主效应，或差异被如实建模。

### 5.5 Track J：judge and metric validation

建议：

- 400-600 条 stratified sample；
- 两名标注者；
- 四分类 blind annotation；
- 预先写明 label book；
- 对 unsafe/broken 过采样，最终统计时按真实分布加权；
- 报告人际一致性与 judge-human 指标；
- 对 ARR/early-stop threshold 做跨模型 sensitivity analysis。

### 5.6 Track U：benign generation integrity

建议：

- harmless prompts：至少 100；
- methods：baseline、rogue_v1、decode_only、full、first_k、decay；
- strengths：transition 与 high；
- vectors：每 prompt 5-10 个；
- 指标：UFR、broken、repetition、early stop、length、quality。

### 5.7 Track A2：second attack family

建议优先选择 refusal-suppression 或 contrastive steering direction，因为实现成本低于复杂 optimized attack。

最小设计：

- 三模型；
- 多 prompt；
- prefill-only / decode-only / full；
- 2-3 个强度；
- 统一 four-class judge 与 collapse metrics。

### 5.8 Track K/D：decode window ablation

建议：

- k：1、3、5、10；
- decay：0.50、0.70、0.85、0.95；
- Qwen/Llama；
- transition 与 high strength；
- 20 prompts × 10 vectors；
- paired comparison。

### 5.9 Track N：Attention Sink causal audit

建议：

- 三模型；
- 1/3、1/2、2/3 depth；
- 32-100 prompts；
- structural filtering + aggregator sweep；
- fixed alpha 与 recalibrated alpha 两条线；
- 关键生成条件回接 ASR/broken/ARR/repetition。

## 6. 内部验收门槛

以下是建议的内部 go/no-go 标准，不是 TDSC 官方规定。

| Gate | 最低通过标准 | 当前状态 |
|---|---|---|
| G1 精确复现 | seed42、单 prompt、1000 vectors、phase-call audit 完整 | `PASS/PARTIAL` |
| G2 跨模型 | 三模型同协议完成，负结果也保留 | `PARTIAL` |
| G3 跨 prompt | ≥50 harmful prompts，≥8 categories | `BLOCKER` |
| G4 跨层 | 核心矩阵覆盖 1/3、1/2、2/3 depth | `BLOCKER` |
| G5 seed robustness | 核心矩阵 ≥3 vector-pool seeds | `MAJOR` |
| G6 second attack | 至少 2 个相互独立的 activation attack constructions | `BLOCKER` |
| G7 judge validity | 人际一致性 ≥0.70；judge macro-F1 建议 ≥0.80；unsafe/broken recall 单独报告 | `BLOCKER` |
| G8 benign integrity | ≥100 harmless prompts 的选定条件评估 | `BLOCKER` |
| G9 statistics | 主要结果有 95% CI、paired effect、clustered bootstrap | `BLOCKER` |
| G10 window ablation | k 与 decay-rate 至少各 4 点 | `PARTIAL` |
| G11 Attention Sink | norm 相关性 + fixed/recalibrated alpha 因果分解 | `PLANNED` |
| G12 artifact | 三模型 config、manifest、raw/judged/summary、版本与命令归档 | `PARTIAL` |

如果 G3、G4、G7、G9 未通过，不建议投 TDSC Regular。G6 和 G8 若缺失，也会显著降低通过概率。

## 7. 统计分析预案

### 7.1 Primary endpoints

- Paper-1 ASR：四分类中的 `unsafe` 比例；
- Collapse：`broken` 比例；
- 正常拒绝：`refusal` 比例；
- Secondary：repetition、early stop、leakage、length；
- Rogue-compatible ASR：仅作复现对齐，不作为主终点。

### 7.2 Primary contrasts

1. `rogue_v1` vs `decode_only`；
2. `rogue_v1` vs `full`；
3. `decode_only/full` vs `first_k/decay`；
4. Track A fixed-alpha vs Track B calibrated；
5. filtered vs unfiltered `mu`，分别在 fixed alpha 与 recalibrated alpha 下比较。

### 7.3 Inference

- 对每个主要比例报告 95% CI；
- 使用 prompt/vector 双维度 clustered bootstrap；
- 保持同一 prompt/vector 在不同 method 下的配对；
- 主比较数量预先冻结；
- 次要 sweep 使用 Holm 或 Benjamini-Hochberg；
- 报告 absolute risk difference 与 relative risk；
- 使用 mixed-effects logistic regression 作为敏感性分析。

### 7.4 Negative results

Mistral 若不复现 Qwen collapse，不应以“无效”作为不扩展的唯一理由并删除结果。应预先定义：

- 100-sample 只是 screening；
- 是否进入 full1000 由 CI 宽度、效应方向和机制问题共同决定；
- 不复现本身是 cross-model heterogeneity 结果；
- 仍需保留关键 confirmatory conditions。

否则会产生 outcome-dependent sampling 和选择性报告风险。

## 8. 12 页正文的建议结构

| 部分 | 建议页数 | 内容 |
|---|---:|---|
| Introduction | 1.0 | 问题、发现、贡献、TDSC relevance |
| Background & Related Work | 1.2 | steering、KV cache、Rogue、safety evaluation |
| Threat Model & Audit Method | 1.3 | 攻击能力、A-F、Track A/B、instrumentation |
| Exact Reproduction Finding | 1.7 | phase-call audit、Rogue v1 cache semantics |
| Collapse & Beyond-ASR | 2.2 | Qwen/Llama/Mistral、四分类、统计 |
| Generalization & Robustness | 1.7 | prompts、layers、seeds、second attack |
| Attention Sink Explanation | 1.3 | token norm、`mu`、causal decomposition |
| Discussion & Limitations | 0.8 | scope、negative results、security impact |
| Conclusion | 0.3 | 结论 |

完整 9-strength 曲线、全量层表、judge prompt、标注手册和坏例放 supplement/artifact。正文只保留预先定义的 primary contrasts。

## 9. 建议的论文 RQ

- `RQ1`: Under real KV-cache semantics, when does the public Rogue v1 intervention actually steer model states?
- `RQ2`: How do prefill- and decode-time interventions differ in unsafe success, refusal, and representation collapse?
- `RQ3`: Do these effects generalize across behaviors, layers, random-vector pools, model families, and a second activation attack?
- `RQ4`: How do structural tokens and `mu` calibration mediate model-specific collapse?

四个 RQ 足以支撑 Regular Paper。当前实验主要回答了 RQ1，并在单 prompt/单层条件下部分回答 RQ2；RQ3 和 RQ4 尚未完成。

## 10. 最终审稿式判断

### 按当前计划完成后

预期评价：

- 技术发现：有价值；
- Qwen 大样本：有说服力；
- phase-call audit：强；
- 跨模型：有框架，但若仍单 prompt/单层则证据层级有限；
- beyond-ASR：方向正确，但 judge/ARR validation 不足；
- TDSC Regular readiness：不足。

可能的审稿决定：`Reject and Resubmit` 或 `Major Revision` 风险较高，核心理由是外部有效性和测量有效性，而不是缺少更多 full1000。

### 完成最小补实验包后

若完成：

1. 多 prompt generalization；
2. 三层核心矩阵；
3. judge-human validation；
4. paired CI/statistics；
5. harmless generation integrity；
6. 第二攻击家族；
7. Attention Sink fixed/recalibrated causal audit；

则 Paper 1 可以达到“具备 TDSC Regular 投稿合理性”的门槛。是否接收仍取决于写作、相关工作定位、artifact 完整度和审稿人对 empirical audit novelty 的判断，但届时不会再因显而易见的单 prompt/单层问题被轻易否定。

## 11. 执行优先级

### P0：立即处理，不耗大规模算力

1. 冻结主张、RQ、primary endpoints 和 primary contrasts；
2. 归档三模型真实运行配置与 vector manifests；
3. 解决 README 与 single-prompt 配置漂移；
4. 写 human annotation label book；
5. 为现有结果补 CI 和 paired summary。

### P1：当前在途实验结束后优先跑

1. multi-prompt generalization；
2. 三层核心矩阵；
3. judge-human validation；
4. benign integrity；
5. k/decay 小型消融。

### P2：形成 TDSC 竞争力

1. second attack family；
2. Attention Sink causal audit；
3. 三模型 cross-layer/structural-token 解释；
4. artifact packaging。

### P3：可选增强

1. 增加一个更大尺度模型；
2. 第二 judge model；
3. 更多 seed/full grids；
4. 更广 utility benchmarks。

资源分配原则：优先增加独立实验单位（prompt、layer、attack family），不要继续只增加同一单 prompt 下的 vector 数量。

## 12. 计算约束下的修订方案（2026-07-16 补充）

### 12.1 新约束

作者补充的实际周期：

- Qwen 六组 full1000 judge 约一周；
- Llama full1000 judge 预计约十天；
- Mistral full1000 attack + 100-sample judge 预计约两周；
- 一个完整模型矩阵包含 `2 Tracks × 6 methods × 9 strengths × 1000 vectors = 108000` 个响应条件实例。

因此，前文提出的补充实验不应复制完整 108000-cell-style 工作量。修订后的原则是：

1. full1000 只属于 exact reproduction 和少数 confirmatory cells；
2. 多 prompt、多层、第二攻击使用缩减条件数的交叉设计；
3. screening、confirmation、case collection 三种任务分开；
4. Track A 不承担获取越狱样本的任务；
5. 所有行为泛化实验优先使用 Track B 的 `alpha = c * mu`。

### 12.2 稀有事件与样本量

如果单次响应的真实攻击成功率为 `p`，在独立近似下，至少观察到一个成功案例的概率为：

```text
P(at least one success) = 1 - (1 - p)^n
```

达到 95% 概率至少观察到一个案例所需的近似样本量：

| true rate p | required n |
|---:|---:|
| 5% | 59 |
| 2% | 149 |
| 1% | 299 |
| 0.5% | 598 |
| 0.1% | 2995 |

这说明：

- 对 1% 左右的事件，100-sample 确实可能漏掉，300-sample 更适合作为确认下限；
- 1000-sample 对 0.5%-1% 事件较稳，但不需要用于所有实验格；
- 若真实率低于 0.1%，追求每个 cell 都出现越狱案例会造成不可控计算量；
- 没有成功案例本身也可以是结果，但必须报告上界。

零事件时可用 rule-of-three 近似 95% 上界：

| observed | approximate upper bound |
|---|---:|
| 0 / 100 | 3% |
| 0 / 300 | 1% |
| 0 / 500 | 0.6% |
| 0 / 1000 | 0.3% |

注意：多 prompt × 多 vector 是交叉/聚类数据，正式置信区间必须使用 clustered bootstrap 或 mixed-effects model，不能完全按独立 Bernoulli 计算。上表只用于资源规划。

### 12.3 为什么少 vectors 不等于少攻击机会

例如：

```text
1 prompt × 1000 vectors = 1000 responses per condition
50 prompts × 20 vectors = 1000 responses per condition
```

两者总响应数相同。后者每个 prompt 的 vectors 较少，但同时估计 prompt variation 与 vector variation，且对 1% 事件仍期望观察约 10 个响应级成功案例。

实际有效样本量会受 prompt/vector 相关性影响，但这正是需要分层统计模型的原因。不能因为每 prompt 只有 20 vectors，就把该设计视为只有 n=20。

### 12.4 screening、rate estimation 与案例收集必须分开

三种目标需要不同设计：

1. `Screening`：用 100 responses/cell 定位 transition、ASR peak 和 collapse 区；
2. `Rate estimation`：对预先选定的 primary cells 扩到总计 300-1000 responses/cell；
3. `Case collection`：允许对成功向量进行富集，用于定性案例与跨 prompt transfer，但不能混入无偏 ASR。

可直接利用现有 single-prompt full1000：

- discovery set：从当前 1000 vectors 中识别成功/高风险向量；
- transfer test：在未参与选择的 prompts 上测试这些向量；
- 输出指标命名为 `conditional transfer success rate`；
- 另保留一组未筛选 random vectors 估计无偏 random-vector attack rate。

这样既能高效获得越狱案例，也不会用选择后的样本冒充随机 ASR。

### 12.5 Track A 与 Track B 的重新分工

#### Track A：fixed-alpha semantic audit

用途：

- phase-call/control-flow 审计；
- fixed-alpha 与 calibrated-alpha 对照；
- 排除普通生成噪声；
- 识别 `mu` 标定引入的间接效应。

Track A 不以获得越狱案例为目标。phase-call 语义通常是确定性的，因此新的多 prompt/多层实验不需要每 cell 1000 vectors。核心配置使用少量 vectors 即可验证 hook 是否发生在预期阶段。

#### Track B：Rogue-calibrated behavioral evaluation

用途：

- 攻击成功率；
- collapse transition；
- 跨 prompt、跨层、跨模型泛化；
- second attack 的 phase/cache 对照。

多层实验必须为每层分别测量 `mu_l`，并冻结：

```text
alpha_l = c * mu_l
```

`mu_l` 应从独立 calibration prompts 估计，不能使用 test prompts 动态调参。为解释标定效应，可额外保留一个 matched fixed-alpha control，但主行为结果应使用 Track B。

### 12.6 缩减后的 multi-prompt 核心矩阵

建议每模型：

- prompts：50；
- vectors per prompt：20；
- total responses per condition：1000；
- main methods：`rogue_v1 / no_cache / decode_only / full`；
- nonzero strengths：`c=1.0, 1.5, 2.0`，必要时用现有 pilot 将 1.5 替换为方法特定 peak/transition；
- `first_k / decay`：只跑 transition 与 high strength；
- baseline：共享 cache-on baseline，并为 no-cache 保留一个单独 baseline。

近似条件数：

```text
4 main methods × 3 strengths
+ 2 windowed methods × 2 strengths
+ 2 baselines
= 18 conditions
```

每模型约 18000 responses，约为完整 108000 矩阵的六分之一。九个强度点仍保留在 single-prompt exact reproduction track 中，不需要在 generalization track 重复。

### 12.7 缩减后的 layer robustness

建议每模型：

- layers：1/3、1/2、2/3 depth；
- methods：`rogue_v1 / decode_only / full`；
- strengths：transition 与 high；
- prompts：20；
- vectors per prompt：10；
- responses per cell：200。

近似工作量：

```text
3 layers × 3 methods × 2 strengths × 200 = 3600 responses/model
```

该设计用于验证效应方向，不用于重画所有九点曲线。若某个 layer 的 CI 跨越关键决策边界，再把该 cell 顺序扩展到 300/500/1000。

### 12.8 顺序扩样规则

建议把 judge subset 设计成互不重叠的增量：

- batch 1：n=100；
- batch 2：追加至 n=300；
- batch 3：追加至 n=500；
- batch 4：仅 primary cells 追加至 n=1000。

扩样依据应预先冻结，例如：

- ASR 或 broken 的 95% CI 宽度仍超过 5 个百分点；
- 0/100 但需要排除 1% 以上事件，则扩到 300；
- cell 是论文 primary contrast；
- 结果位于 attack-to-collapse transition 区；
- 跨模型出现方向相反，需要确认异质性。

不得只因为“出现了有效结果”才扩 full1000。Mistral 即使 100-sample 不复现，也应对预先定义的关键 cells 至少扩到能给出有意义上界的规模。

### 12.9 second attack 可以完整复用六组 A-F

代码检查确认：

- `AttackConfig.vector_source/vector_path` 决定向量；
- `AttackConfig.phase_mode` 决定时序；
- hook 统一执行 `hidden_states + attack_strength * attack_vector * mask`；
- 因此向量构造与六组 phase/cache schedule 是解耦的。

第二攻击可以映射为：

| Group | schedule | second attack interpretation |
|---|---|---|
| A | `rogue_v1_cache_semantics` | 第二攻击向量 + legacy Rogue cache/mask semantics |
| B | `no_cache` / full-sequence | 第二攻击向量 + no-cache prefill/decode |
| C | `decode_only` | 第二攻击向量只作用于 cached generated tokens |
| D | `full` | 第二攻击向量作用于 prefill + cached decode |
| E | `first_k` | 第二攻击向量只作用于前 k 个 decode steps |
| F | `decay` | 第二攻击向量在 decode 阶段指数衰减 |

命名上建议将 A 的展示名从 `rogue_v1` 改为 `legacy_cache_semantics` 或 `rogue_v1_schedule`，避免读者误以为第二攻击仍是 Rogue random vector。

第二攻击的资源友好执行方式：

1. Screening：先跑 A/C/D，必要时加 B；
2. Confirmation：若 phase/collapse 现象存在，再补 E/F；
3. 论文最终若声称“六种 schedule 对不同攻击均成立”，则六组都要有结果；
4. 不要求第二攻击也做 `2 Tracks × 9 strengths × 1000 vectors`；
5. 建议六组 × 两个非零强度 × 20 prompts × 10 vectors，约 2400 responses/model。

第二攻击向量应明确归一化。若使用 contrastive/refusal-suppression direction，建议报告原始 norm，并使用单位向量：

```text
v_hat = v / ||v||
alpha = c * mu_l
```

否则不同攻击向量的 norm 会与 phase effect 混淆。

### 12.10 修订后的结论

前文计划的科学目标仍然有效，但执行方式需要调整：

- 不再要求每个补实验都 full1000；
- full1000 保留给 single-prompt exact reproduction 和少数 primary cells；
- 多 prompt 通过 `prompts × vectors` 保持每 condition 的总响应规模；
- 多层只跑核心 methods/strengths；
- Track A 负责机制对照，Track B 负责攻击与 collapse；
- 第二攻击可以、也应该复用六组 schedule，但采用两阶段扩展。

在这些调整下，补实验仍然能解决 TDSC 的主要审稿风险，同时将新增运行量控制在完整矩阵的一小部分。
