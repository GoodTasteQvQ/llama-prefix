# 实现提示词与写作路线的有边界审阅

日期：2026-09-05。审阅为本次交付的自审，不等于独立代码评审或论文同行评审。

## 1. 服务器实现提示词

对象：[服务器实现提示词](../implementation/paper1_server_codex_implementation_prompt.md)。
结论：`PASS / PROMPT REVIEW ONLY`。尚未由服务器执行，不是 CODE_REVIEW=PASS。

| 检查 | 结论与处理 |
|---|---|
| 入口 | 使用用户新目录，引用当前两份规格；路径带空格明确加引号 |
| 范围 | 实现 core/E1/E2/E3；缺资产路径需 fixture 覆盖，不能以缺 Gemma 为由只交骨架 |
| 过度实现 | 不加入调度平台、多代理体系、全库重构、新实验或覆盖率目标 |
| 保存与测试 | 允许保存开发工作文件以运行 tests；审查通过才能标最终交付，消除“未保存无法测试”的循环 |
| 完成与受阻 | CODE_REVIEW、runtime、资产、正式实验分开；外部缺项不假通过，代码缺陷不能冒充外部受阻 |
| 审阅边界 | 一轮完整审查、最多两轮定向修复复查；科学正确性问题阻断，排版偏好不触发新架构 |
| 测试风险 | mock 端到端只能作 fixture；允许至多 24 generation + 4 Judge 的非正式安全 smoke，含重试 |
| 运行权限 | 不启动正式 dose screen/evaluation、下载大模型或 Git push；smoke 不替代正式 gate |
| 科学稳定性 | 不改 v2.1/20,480 预算、endpoint、哈希时点，不将旧协议重新引入 |
| 有边界失败 | 无法修复或输入冲突则报告 BLOCKED/草稿，不能为满足“必须通过”伪造 PASS |

审阅后未发现需要扩大实现范围的问题。服务器仍需真正实现/执行测试和审查，本文不能替代。

## 2. 论文写作路线

对象：[Paper 1 完成论文行动路线](../paper1_writing_action_roadmap.md)。
结论：`PASS / ROADMAP REVIEW ONLY`。它是写作执行计划，不是论文完成或投稿保证。

| 检查 | 结论与处理 |
|---|---|
| 证据优先级 | 原始结果 > claim matrix > protocol/status supplement > blueprint；避免复制过时蓝图 |
| 当前结果 | 原始 P2、amended P2 v2、K1、clean/benign/fixed720 分开登记，未把 `paper_result_eligible=false` 擅自改写 |
| 补充实验 | 明确留空，使用占位符；禁止预写方向、数字或“已完成” |
| 文献阅读 | 保留阅读相关论文的想法，但改成 citation/方法/图表/限制的结构化矩阵，不复制文字或图表 |
| 初学者流程 | 先 scope/status 和 claim ledger，再文献、outline、Methods/Results、Introduction，最后摘要 |
| 图表 | 每张图绑定研究问题、输入、estimand、分母、不确定性和 caption claim，不追求装饰性风格 |
| 审阅 | H1-H6 覆盖事实、统计、论证、artifact、语言和反向审稿；P0/P1 未解决不能定稿 |
| 过度设计 | 不要求一次读完所有论文、不一次重写整篇、不新增实验/工作流平台；每周任务控制在可完成范围 |
| 提交边界 | 目标期刊、格式、许可证和匿名化列为最后核对项，不提前承诺 CCF 等级 |

### 审阅后的剩余限制

路线没有代替最新文献检索、目标期刊选择、英文母语润色或导师意见。补充实验完成后仍需
重新更新 claim ledger、图表计划和 H1-H6 审阅；不得把本路线的 `PASS` 理解为论文通过。

## 3. 本轮交付自检

- [x] 服务器 Codex 实现提示词已保存。
- [x] 实现提示词要求代码完成后审查，且把代码缺陷与资产缺失分开。
- [x] 论文行动路线已保存，补充实验部分留白。
- [x] 实现提示词与写作路线均有独立边界审阅。
- [x] `paper1_minimal_broadening_experiment_design_v2.1_readable.md` 已完成静态一致性审阅。
- [x] 易读版已补入既有 Calibration-Frame Sensitivity 问题，明确它不是问题三的替代，也不是 v2.1 新增扩展。
- [x] 易读版只改变说明层次和术语密度，不改变 v2.1 的科学范围、预算、停止边界或哈希时点。
- [x] 严格 v2.1 设计仍是服务器实现的唯一规范；易读版不能替代严格版。
- [ ] 新增易读版尚未提交或推送；是否提交/推送需由后续 Git 操作单独处理。

## 4. v2.1 易读版审阅

对象：[v2.1 易读实验设计](../paper1_minimal_broadening_experiment_design_v2.1_readable.md)。
结论：`PASS / READABILITY COMPANION ONLY`。

审阅确认：

- 版本标识为 `MBD-NM v2.1-ccf-a-target`，没有发现旧 v2.0 字段。
- 核心预算 `12,640`、扩展预算 `7,840`、总预算 `20,480` 与严格版一致；表格中的方向数量没有重复乘以两种 family。
- E1 外部提示、E2 第三架构、E3 额外层位点的目的、资产门槛和“不满足则不运行”边界与严格版一致。
- safe-pair 的 construction/development/evaluation 分工、A/S 剂量选择、人工审核上限和结果落地后生成 provenance SHA256 均被保留。
- 文档明确排除 Mistral，并明确不把扩展完成或正结果当作 CCF-A 的自动条件。
- 文档只使用说明性表格和段落，没有新增实现接口、统计规则或实验单元；因此不会给服务器 Codex 引入第二套规范。
- Calibration-Frame Sensitivity 已单独列为校准问题，并限定为已有 Qwen 支持性案例；没有把 calibration scale 的变化扩大为结构因果或一般 collapse 结论。
- 对原始/严格实验设计的复核确认：Stage 3 P1/P2/K1 本身已有完整定义；v2.1 严格版现已明确登记其为既有证据输入，不重跑、不计入 20,480 预算，并与新 `mu_content` calibration 区分。
- 论文行动路线现已在 scope/status、Methods、Results 和第一周核对任务中单独登记 Calibration-Frame Sensitivity；补充实验占位不会覆盖这条已完成证据线。

审阅边界：易读版用于作者和导师理解研究设计，不能单独作为代码实现依据；若易读版与严格版出现冲突，以严格版及其审阅记录为准。
