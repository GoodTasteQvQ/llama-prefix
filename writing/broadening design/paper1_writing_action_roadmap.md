# Paper 1 完成论文行动路线

版本：`paper1-writing-roadmap-v1`  
适用对象：第一次写论文的作者  
当前补充实验：留空，待实验完成后回填  
当前证据主边界：[Paper 1 Claim-Evidence Matrix](../paper1_claim_evidence_matrix.md)  
当前叙事蓝图：[Paper 1 Writing Blueprint](../paper1_writing_blueprint.md)

## 0. 先理解这篇论文要完成什么

你不是先把所有结果“写成一篇文章”，而是要完成一条可检查的证据链：研究问题 -> 实验设计
-> 结果 -> 限定主张 -> 与已有工作的关系。论文的目标不是把实验数量写得很多，也不是把
CCF-A 写进文章，而是让审稿人能够回答：

1. 这篇论文具体发现了什么？
2. 这个发现相对已有研究增加了什么认识？
3. 证据是否真的支持作者写出的每句话？
4. 别人能否根据代码、配置和数据重现关键结果？

现有 Paper 1 的稳定主线是：在被审计的 activation-steering 实现中，KV-cache/phase 语义
会改变实际干预时机；持续 generated-token steering 的高强度结果需要结合 broken、repetition
和四分类输出解释；已有 Stage 3 的 Calibration-Frame Sensitivity（P1/P2/K1）是独立的
calibration-aware Qwen case study。这里的“已有”指已登记的生成/分析结果，不等于人工验证和
两阶段敏感性已经全部完成。补充实验完成后，只把实际结果填入相应位置，不预先承诺
“跨 benchmark、跨模型或跨层复现”。

这份路线不替代导师的选题判断、目标期刊的格式要求或最终英文润色。它提供执行顺序、文件
产物、停止条件和审阅方法。每一阶段完成后再进入下一阶段，未通过审阅的阶段保留为草稿。

## 1. 当前证据和文件优先级

### 1.1 文件优先级

发生冲突时，按以下顺序解释：

1. 已归档的原始 generation/Judge/result 文件及其运行记录；
2. `writing/paper1_claim_evidence_matrix.md`；
3. 当前结果对应的 protocol/status supplement；
4. `writing/paper1_writing_blueprint.md`；
5. 组会口播稿、Notion 增量稿和旧 broad/ICLR 设计。

旧蓝图中的“尚未完成”可能反映较早时间点。写作前必须以结果目录和 claim matrix 重新核对，
不要直接复制旧段落。原始 P2 与 amended independent P2 v2 必须分开叙述；v2 的运行字段
`paper_result_eligible=false` 不能被删改，任何正式解释都必须引用对应 status supplement。

### 1.2 论文当前允许的主张

当前可以准备的主张包括：

- 被审计的公开实现与 literal sustained generation-time steering 的文字描述不完全一致；
- 在当前 Qwen/Llama、prompt、layer、direction、decoder 和离散 dose 条件下，ASR 与
  broken/repetition 组成存在描述性 regime shift；
- ASR 不能单独诊断 non-success 输出的组成和 generation integrity；
- Qwen Stage 3 的 calibration frame 会改变 measured calibration scale 和 dose geometry，
  但原始 P2 与 amended v2 必须按各自 endpoint、运行和状态边界报告。

当前不能直接写成一般 harmful-behavior 规律、模型脆弱性排名、层不变性、Attention Sink 因果
机制或 activation-steering 总体规律。补充实验部分暂时使用占位符：`[SUPPLEMENT RESULTS
PENDING]`、`[SUPPLEMENT CLAIM PENDING]`，不使用假数字或预期方向。

## 2. 阶段 A：准备写作工作区

### 2.1 建立目录和文件

在本地或服务器仓库中建立以下写作目录；不要把临时草稿混入 `results/`：

```text
writing/paper1_draft/
  00_scope_and_status.md
  01_claim_ledger.csv
  02_result_locator.md
  03_literature_matrix.csv
  04_outline.md
  05_figure_table_plan.md
  06_methods_draft.md
  07_results_draft.md
  08_introduction_draft.md
  09_related_work_draft.md
  10_discussion_limitations.md
  11_abstract_title.md
  12_reviewer_questions.md
  figures/
  tables/
  revisions/
```

实际写作格式可以是 LaTeX、Markdown 或 Word，但必须保留这些逻辑文件。每个文件开头记录
日期、版本、证据状态和是否经过审阅。论文源文件、图表源代码和最终导出文件分开保存。

### 2.2 先写 scope/status，而不是 Introduction

`00_scope_and_status.md` 只回答：研究问题、模型、数据、条件、当前已完成/未完成实验、
禁止主张、补充实验占位符和本轮写作版本。它必须明确：

- 这是 Paper 1 的 reproducibility/measurement/evaluation 论文，不把 Paper 2 的 defense
  方法混进来；
- Mistral、E1/E2/E3 在没有实际合格结果前不能写为完成；
- fixed720 selection、人工标签和 Judge quality 的状态不能混写；
- Calibration-Frame Sensitivity 的 P1/P2/K1 已有结果必须单独登记，不能与 v2.1 新补充实验的
  development `mu_content` 或 E1/E2/E3 合并，也不能把它写成待完成实验；
- 结果落地后的 provenance manifest 是 artifact 证据，不是运行前科学结果。

完成标准：读者只看这一页，就能知道哪些结论可写、哪些结论必须留空。

## 3. 阶段 B：建立主张—证据账本

### 3.1 `01_claim_ledger.csv` 字段

每行写一个可独立判断的主张，不要把一整段结论放在一格。推荐字段：

```text
claim_id,claim_text,claim_type,evidence_ids,result_paths,
model_scope,prompt_scope,layer_scope,condition_scope,dose_scope,
status,allowed_wording,forbidden_wording,missing_evidence,reviewer,date
```

`claim_type` 使用 `method / observation / comparison / interpretation / limitation`；`status`
使用 `SUPPORTED / SUPPORTED_WITH_BOUNDARY / PARTIAL / NOT_SUPPORTED / NOT_RUN / FORBIDDEN`。

### 3.2 逐行核对方法

对每一行执行：

1. 找到实际结果路径和结果字段；找不到就不能写成 supported。
2. 写出数据分母、缺失数量、模型/层/prompt 范围和统计方法。
3. 把“结果观察”与“机制解释”拆成两行。例如“broken 上升”与“因为某结构 token 导致”不是同一个主张。
4. 把允许措辞和禁止措辞同时写出。允许措辞必须比结果范围更窄，而不能更宽。
5. 标记是否依赖补充实验；依赖的行暂时保持 `PENDING_SUPPLEMENT`，不得用预期结果填充。

完成标准：正文中的每个数字、比较、因果词和一般化词都能回到账本的一行。

## 4. 阶段 C：阅读相关论文，但采用“证据化学习”

你提出的“让 Codex 阅读相关论文，学习写作风格和绘图风格”可以作为辅助步骤，但不能
作为论文质量控制的主方法。正确做法是学习论证结构、实验报告习惯和图表信息密度，而不是
复制词句、配色、标题或结论语气。

### 4.1 建立文献集合

分四组，每组先选 5-8 篇高相关论文，再扩展引用：

1. activation steering / representation engineering；
2. jailbreak evaluation / harmful behavior benchmark；
3. KV-cache、prefill/decode 和 inference intervention；
4. reproducibility、measurement validity、failure-aware evaluation。

优先选择正式版本，记录 DOI/arXiv、年份、venue、代码/数据链接和阅读日期。不要只看摘要；
至少阅读 introduction、method、main results、limitations、appendix 的评测定义。

### 4.2 `03_literature_matrix.csv` 字段

```text
paper_id,citation,problem,claimed_contribution,
evaluation_frame,models,prompts,metrics,uncertainty,
main_figure_role,table_role,limitations,artifact,
useful_structure,not_to_copy,notes
```

每篇论文至少提取：它如何定义成功、如何处理失败输出、如何报告分母、图表回答什么问题、
限制写在哪里、代码和数据是否可复核。把“useful_structure”和“not_to_copy”同时填写，防止
把风格学习变成模仿。

### 4.3 文献学习输出

最终只产出三份内部规则，不把文献综述变成无边界阅读：

- 一页“Paper 1 相关工作差异表”：已有工作做了什么、本文补什么、本文不声称什么；
- 一页“图表设计规则”：颜色语义、误差区间、分母显示、图例和 caption 规范；
- 一页“写作语气规则”：使用限定词、报告负结果、区分 observation/interpretation 的句式。

不得复制任何一篇论文的段落、图、数据或专属术语。引用必须由作者核对原文，不让模型凭
记忆生成 citation。文献集合完成后才冻结 related-work 叙事，后续新增关键论文可登记 revision。

## 5. 阶段 D：锁定论文问题、贡献和结构

### 5.1 写一句话版本

先用中文写，再翻成英文：

> 在明确限定的模型、提示、层、方向和解码条件下，本文审计 activation-steering 的实际 phase
> semantics，并展示为什么 beyond-ASR 的 generation-failure decomposition 对解释结果是必要的。

如果补充实验得到稳定外部验证，再在不扩大范围的前提下追加一句限定性 external-validity
主张；不把它改写成“普遍规律”。

### 5.2 固定 RQ、贡献和非贡献

建议 RQ：

- RQ1：真实 KV-cache 执行中干预发生在哪个 phase？
- RQ2：持续 generated-token steering 对 unsafe、refusal、safe、broken 和 repetition 有何影响？
- RQ3：哪些现象跨 Qwen/Llama 共享，哪些是模型或实现特定的？
- RQ4：calibration frame 如何改变 measured dose geometry 和 fixed-support estimates？

贡献最多写三到四条；每条贡献必须有一个结果锚点。单纯“我们进行了很多实验”不是贡献。
明确不贡献：新攻击算法、新防御方法、一般安全保证、Attention Sink 因果解释和模型排名。

### 5.3 `04_outline.md` 推荐结构

1. Introduction：问题、风险、研究问题、贡献、边界。
2. Background and Reproduction Target：steering、KV-cache、ASR、failure labels、threat model。
3. Phase-aware Audit：hook、mask、prefill/decode trace 和 phase 结果。
4. Failure-aware Behavioral Evaluation：ASR、四分类、ARR、repetition、collapse 诊断。
5. Cross-model and Breadth Evidence：Qwen/Llama 及补充实验占位或已完成 block。
6. Calibration-aware Case Study：P1、原始 P2、amended P2 v2、K1，严格区分证据线。
7. Discussion：测量含义、复现含义、对评测设计的启示。
8. Limitations and Conclusion：范围、缺失实验、不能推导的机制和未来工作。

补充实验完成前，第 5 节只写已有 Qwen/Llama 证据；使用明确占位符，不预写结果方向。

## 6. 阶段 E：先写 Methods 和 Results，再写 Introduction

### 6.1 Methods 写作顺序

按以下顺序完成 `06_methods_draft.md`：

1. Threat model 和 reproduction target；
2. 模型、checkpoint、layer、hook site、template、decoder；
3. phase/mask/cache instrumentation；
4. direction、dose、prompt frame 和数据分割；
5. four-class Judge、binary ASR、ARR/repetition；
6. missingness、bootstrap、人工审核和 provenance；
7. Calibration-aware Case Study：已有 P1/P2/K1 的 frame 定义、固定支持集、endpoint 和结论边界；
8. 补充实验方法占位。

每个小节结束写“本节允许支持的结论”。Methods 不混入结果数字，不写“我们发现”。

### 6.2 Results 写作模板

每个结果小节使用固定四段：

1. 这一节要回答什么问题；
2. 实验条件、分母和统计方法；
3. 观察到的数值和不确定性；
4. 这一结果支持什么、不能支持什么。

先写 phase audit，再写行为结果，再写 cross-model，再写 Calibration-Frame Sensitivity。
对于原始 P2 和
amended P2 v2，分别给运行身份、endpoint、保留样本和区间；禁止用一张表把两者合并成一个结果。

### 6.3 Introduction、Related Work、Discussion

- Introduction 最后写，避免在结果未知时夸大问题或贡献。
- Related Work 按问题缺口组织，不按论文逐篇流水账；每段最后说明本文位置。
- Discussion 只解释已在结果中出现的模式。把可能机制写为 hypothesis，并明确未测量部分。
- Limitations 不要写成道歉；逐条说明限制如何影响主张范围。

## 7. 阶段 F：图表和绘图审阅

### 7.1 `05_figure_table_plan.md`

每张图填写：`figure_id / research_question / input_files / unit_of_analysis / x/y / estimator /
uncertainty / denominator / panel_role / main_or_appendix / caption_claim / limitation`。

推荐主图：

1. phase/cache execution schematic；
2. phase-call audit；
3. ASR 与 broken/repetition 强度关系；
4. 四分类 composition 与模型异质性；
5. calibration frame 的 dose geometry；
6. 补充实验外部/架构/层证据（完成后决定是否入主文）。

每张图只回答一个问题。不能把不同 endpoint、不同分母或不同 Judge 版本放在同一个无说明
面板中。颜色在全文固定：unsafe、refusal、safe、broken 四类保持同一语义；不要只靠颜色，
同时使用图例、线型或文字。所有 error bar 写明 CI 类型、bootstrap 层级和有效分母。

### 7.2 图表生成和核对顺序

1. 由原始结果生成中间表，不从截图或手工抄数；
2. 保存绘图脚本、输入文件列表和运行命令；
3. 图中数字与 claim ledger 自动或人工逐项核对；
4. 检查字体、轴、legend、色盲可读性、单位、零值和缺失值；
5. 写 caption，caption 单独读也不能超出主张；
6. 再决定主文/附录位置。

不要为了模仿相关论文而加入 3D 图、装饰性图、没有 estimand 的 radar chart 或无法解释的
热图。绘图风格服务于比较和审计，不服务于制造视觉冲击。

## 8. 阶段 G：逐轮写作流程

每次只处理一个小节，使用以下循环：

1. 选定小节和一个问题；
2. 列出需要引用的 evidence ids 和数字；
3. 先写事实句，再写解释句，再写边界句；
4. 用 Codex 做“只查事实和逻辑”的审阅；
5. 自己核对原始结果和引用；
6. 更新 claim ledger、figure/table plan 和 revision log；
7. 保存通过审阅的版本。

交给 Codex 的每次写作任务只允许修改指定小节，并附：目标读者、证据路径、允许主张、禁止
主张、引用列表、字数范围和是否可以使用补充实验占位符。禁止让 Codex 一次重写整篇论文，
也不要让它在没有结果路径时补数字、补 citation 或补实验结论。

## 9. 阶段 H：论文审阅协议

### H1 科学事实审阅

- 每个数字能否在结果文件找到？
- 分子、分母、缺失、模型、层、prompt、dose 是否一致？
- 原始 P2/v2 是否混淆？是否把 descriptive/estimation-only 写成 causal/significant？
- 是否把 proposed supplement 写成已完成？

### H2 统计和不确定性审阅

- 点估计与 CI 是否来自同一 endpoint 和同一数据版本？
- bootstrap 层级、有效样本、区间类型是否写清？
- 是否出现没有预先定义的 post-hoc threshold、p-value 或显著性星号？
- Judge parse failure、technical failure 和 broken 是否分开？

### H3 论证和贡献审阅

- Introduction 提出的每个问题是否在 Results 回答？
- 每条 contribution 是否有证据而不是活动清单？
- Discussion 是否引入未测量机制？
- Limitations 是否真实影响结论而不是形式性段落？

### H4 可复现性和 artifact 审阅

- 模型、tokenizer、template、decoder、layer、代码 revision 和输入文件是否可定位？
- 图表能否由脚本和归档输入重建？
- provenance manifest 是否在结果落地后生成且不可覆盖？
- 代码/数据许可证和外部 benchmark 的再分发边界是否注明？

### H5 语言和格式审阅

- 主语、时态、术语和缩写是否一致？
- 是否过度使用 `prove / demonstrate generally / novel / significant`？
- 每段首句是否说明作用，末句是否回到研究问题？
- caption、表头、补充材料引用是否独立可读？

### H6 反向审稿人审阅

模拟三位审稿人：方法复现、统计评测、领域贡献。每位只输出 findings、证据、严重级别和
最小修复，不直接重写全文。所有 P0/P1 finding 修复后再进入下一轮；P2/P3 统一在最终
语言润色阶段处理。

## 10. 阶段 I：补充实验完成后的回填

这部分在当前先留空。实验结束后按以下顺序回填：

1. 读取每个 block 的 provenance、analysis、human audit 和 accounting；
2. 更新 claim ledger，不先改摘要；
3. 逐 block 判断 PASS / DOWNGRADED / NOT_RUN / NON_ESTIMABLE；
4. 更新 Results、图表、Limitations；
5. 再决定哪些外部/第三模型/层结果进入主文，哪些进入附录；
6. 最后更新 Abstract、Title、Introduction 和 Conclusion；
7. 重新执行 H1-H6 审阅。

如果 E1/E2/E3 失败或缺资产，报告失败本身及其影响，不追加未登记实验来“补齐”叙事。

## 11. 最终提交前清单

- [ ] scope/status 与 claim ledger 已更新到最终 run revision。
- [ ] Methods 的每个配置可由文件或 provenance 定位。
- [ ] Results 没有把 observation 写成 mechanism 或 causal claim。
- [ ] 原始 P2、amended P2 v2、K1、clean/benign、人审状态分开。
- [ ] 所有补充实验按实际状态写入，没有预期结果占位残留。
- [ ] 每张主图和表有唯一问题、分母、不确定性和可重建脚本。
- [ ] 相关工作引用已核对原文，未复制文句或图表。
- [ ] 附录包含必要 config/schema、额外分层结果、坏例子和失败 accounting。
- [ ] artifact、许可证、provenance 和代码运行说明齐全。
- [ ] H1-H6 没有未解决 P0/P1 问题；导师审阅意见已登记。
- [ ] 目标期刊格式、页数、匿名化、数据/代码政策已逐项核对。

## 12. 你现在可以执行的第一周任务

按顺序完成，不要同时写全文：

1. 建立 `paper1_draft/` 目录和 `00_scope_and_status.md`；
2. 将 `paper1_claim_evidence_matrix.md` 转成 `01_claim_ledger.csv`，先填 15-20 条主张；
3. 为每条主张补 result path、分母和 allowed/forbidden wording；
4. 核对 Stage 3 P1/P2/K1、原始 P2、amended P2 v2、harmful-clean、benign 和 fixed720 的最新状态，
   并把 Calibration-Frame Sensitivity 单独登记到 claim ledger；
5. 选 12-20 篇论文填 `03_literature_matrix.csv`，先不写 Related Work；
6. 产出一页相关工作差异表和一页图表规则；
7. 写 `04_outline.md` 与 `05_figure_table_plan.md`；
8. 先起草 Methods 的 Threat Model、Data/Model、Phase Audit 三节；
9. 对这三节做 H1-H4 审阅，再继续 Results；
10. 保持补充实验章节为占位，不写任何预期方向。

完成这些任务后，才进入 Results 和 Introduction 的逐节写作。不要等补充实验全部结束才开始
准备，也不要在证据账本未建立前追求英文表达的“像论文”。
