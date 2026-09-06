# 服务器 Codex 实现提示词

版本：`server-handoff-v1`。此文件全文可直接作为任务提示词发送给服务器 Codex。
对应科学设计 `MBD-NM v2.1-ccf-a-target`、实现规格 `linux-single-gpu-v1`。

## 任务与输入

你是本次补充实验的代码实现负责人。请在 Linux 项目
`/data/goodtaste_workspace/llama-prefix` 中完成实现、验证、修复和有边界代码审查。
不要只交计划或代码骨架。全部必需代码完成且代码审查通过后，保存可交付版本和审查记录，
然后停止；不要接着启动正式实验、写论文或推送 Git。

依次阅读以下文件，路径含空格，命令参数必须加引号：

1. `writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md`。
2. `writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md`。
3. `writing/broadening design/review/` 下的 `paper1_minimal_broadening_design_review.md` 和 `paper1_ccf_a_implementation_review.md`。
4. 任务书指出的现有代码和相关 tests，再决定最小改动位置。

科学定义以第 1 份文件为准，实现/环境契约以第 2 份为准。本提示词补充本次执行权限、交付
和审查边界，不重新定义实验。老的 broad/ICLR 协议、旧路线图中的 Mistral/三模型要求、旧
Stage 3 哈希 contract 不作为本次新增实验要求。若两份当前文件存在影响结果的真实冲突，
记录具体位置并暂停依赖该决策的实现，继续无关模块；不能凭经验改科学设计。

先确认版本、分支、HEAD 和工作区修改。文档已同步才开始；无需固定在旧 commit `1dd4ef9`。
不回滚、覆盖或顺手提交他人改动。本任务不需要创建新平台、另开任务或组织多代理审查。

## 执行范围与权限

- 实现 core、E1、E2、E3 的配置、离线资产发现、frames、方向、calibration、phase、generation、
  Judge、accounting、人审抽样、统计、绘图、恢复和 post-run archive。E1/E2 缺资产不能仅留
  TODO；数据适配器和调度路径要用 fixtures 实现并验证，真实运行状态另记 NOT_RUN。
- 使用任务书的 Linux 单卡配置：显式正式 Python、项目内 TMPDIR/TMP/TEMP、HF 离线环境
  和 local_files_only=True，默认物理 GPU 0、逻辑 cuda:0，一个 GPU worker 串行工作。
- 必要依赖安装和隔离环境创建已获授权，先使用已有环境，不无关升级；不自动改正式 torch/
  Transformers、不自动改 Judge float32、不使用第二卡/量化/CPU offload 来掩盖运行失败。
- 本次不下载大型模型、不发起全量实验、development dose screen 或任何正式 evaluation。
  不把 JBB 中的 HarmBench 来源行冒充 E1，不用其他模型替换缺失的 Gemma。
- 不采集/生成真实人工标签，不重抽既有 fixed720，不修改历史原始结果或既有协议。
- 开发中允许保存源文件和测试输出，这是执行测试的必要步骤。“审查通过后保存”指通过后
  标记最终交付版；未通过的工作文件只能保留为草稿，不能伪造 PASS，也不能删除问题记录。

## 实施顺序

1. 按任务书设置环境后，做只读预检并输出资产报告。默认 Python 为
   `/data/goodtaste_workspace/envs/llama-prefix/bin/python`；不要用 `(base)` 或裸 python。
2. 写一张简短“需求 -> 实现函数/配置 -> 测试”的对照表，放最终实施报告中，不另造审批系统。
3. 优先完成可离线运行的 frames、确定性 allocator、identity、missing/accounting、Judge
   解析、人审、统计和 archive；随后接入真实模型 backend 与串行 CLI/wrapper。
4. 按现有 repo 风格复用局部函数。默认建议目录不必逐个照抄；新增抽象必须服务于当前流程。
   若修改共享函数，检查其所有现有调用方并跑受影响的回归测试，不重构整个 Stage 3。
5. 完成 core/E1/E2/E3 的 prepare/dry-run 配置及预算表。科学逻辑上限为 core 12,640 +
   extension 7,840 = 20,480；说明 A=S/clean 去重，Judge/重试/smoke/activation forwards 分账。
   真实资产缺失只限制对应 block，不能让 prepare 无法报告其他 blocks。
6. 完成薄 CLI 和 `scripts/run_paper1_broadening_single_gpu.sh`，脚本 LF 行尾，空参数只帮助；
   交付经过实际 CLI 检查的 Bash 命令、nohup/PID/日志/退出码/恢复说明。
7. 做下面规定的验证，再按有边界审查闭环修复。通过后保存最终文件和报告，结束本任务。

## 验证范围

先用无网络、无 GPU 模型的 fixtures 验证下列高风险行为，结果必须来自实际执行：

- 分割/overlap 状态、JBB100/JBB40、E1 选择、方向 fold 和 development 隔离；
- resid_pre、content span、unit norm、seed/index 与 E3 同向量复用；
- A/S 平局/无候选/缺失、S<=A、negative sign 的状态；禁止从 evaluation 选剂量；
- clean/A=S identity 去重、首次成功 attempt、重试/resume、空输出和 broken/missing 分离；
- phase/cache fixture、zero-alpha、首 token EOS；绝不能把 public_v1 写成固定 prefill_only；
- four-class/binary 分账、严格解析与 null、完整 scheduled/paired 分母、missing bounds；
- 已知答案 toy table 的等权估计、同步 bootstrap 和 nearest-rank、失败/零方差处置；
- 人审整数配额、N/n 权重、盲化、诊断样本单列和不足标签状态；
- archive 只在结果终结后哈希、不自哈希、不覆盖旧 manifest，能追溯实际启动源码；
- Bash 语法、环境继承、单卡限制，以及 generation 子进程退出后才加载 Judge。

同时做一个 tiny fixture 的端到端流程，覆盖 prepare -> screen -> generation -> Judge ->
analysis -> mock human -> human sensitivity -> archive；mock 输出全部标 FIXTURE，不能放入
正式结果目录或冒充 human annotation。此流程需要实际有处理逻辑，不能仅返回硬编码 PASS。
需要的 tests 应检验行为/科学不变量，不以逐行镜像实现或全库覆盖率目标增加工作量。

本提示词允许一次有限的非正式模型 smoke，目的是验证实现接入，不收集论文证据：

- 仅现有 Qwen/Llama 核心层和现有 Qwen3 Judge，串行单卡；使用两条非 evaluation 的安全
  prompts 及 smoke-only 单位测试向量。测试 clean、public_v1、decode_only 和 zero-alpha。
- 本次累计最多 24 次被测模型生成、4 次 Judge 调用，含技术重试；不跑 dose grid、额外层
  或 Gemma，不因输出不理想扩充 smoke。Smoke id 与正式 id 分开，标 NON_EVIDENCE。
- 若 GPU 正在使用、模型文件/环境不可用或额度内未解决错误，记录 RUNTIME_NOT_RUN/BLOCKED
  和具体原因，继续可完成的代码审查；不能等待共享卡空闲无限循环或侵占他人进程。
- 该 smoke 不替代正式运行前逐模型/层/family gate。外部模型和层未实测必须在报告中明列。

## 有边界代码审查

代码完成后换成审查视角：先阅读 diff，再沿一条真实 CLI 数据流检查，不能只复述测试通过。
本次做一轮完整审查；发现问题后，最多两轮集中修复和定向复查。已有测试通过且未被后续
改动影响时不重复全量跑。审查只覆盖本次改动、相关调用方及这些问题：

1. 实现是否改变了 prompt/vector/dose/model/layer/endpoint 或既有结果。
2. identity、配对、分母、失败、重试、抽样和统计是否会静默改变科学结论。
3. 本地加载、单卡/进程退出、模板、dtype、hook 和日志恢复是否真实成立。
4. 未运行、标签不足、资产缺失是否被错误标为通过；fixtures 是否泄漏到正式结果。
5. 归档是否可追溯且不覆盖；是否存在与当前请求无关的框架/重构/新实验维度。

每条发现给 severity、文件/行号、触发条件、实际影响、最小修复与复查结果。会改变科学
结果、丢失/混合记录、误报完成、超用 GPU、触发未授权正式运行的问题均阻塞通过。
纯排版、命名偏好或未来性能优化只作建议，不为其开启新一轮架构设计。

禁止通过删测试、放宽断言/阈值、隐藏失败或改设计来获得 PASS。文档的科学歧义或外部条件
确实阻塞时，报告 BLOCKED，保留草稿和已通过部分，不谎称“只有通过才停，所以现在通过”。
两轮后仍有影响正确性的未解问题，也只能如实交接，不能把审查扩展成无边界循环。

## 最终交付与完成条件

保存代码、配置示例、fixtures/tests、运行说明，以及
`writing/broadening design/report/paper1_server_implementation_completion_report.md`。报告至少包含：

- 需求覆盖表、改动路径、启动 HEAD/dirty state、实际 Python/依赖/物理 GPU 与环境差异；
- 实际测试命令、退出码/摘要、日志位置、离线端到端结果、预算核对；
- 有边界审查的发现、修复/复查、剩余非阻断建议；
- 分开的状态 `CODE_REVIEW`、`CORE_SMOKE`、`E1_ASSETS`、`E2_ASSETS`、`FORMAL_EXPERIMENTS`。

只有全部必需实现完成、离线验证通过、审查无未解阻断项，才写 `CODE_REVIEW=PASS` 并标记
本次代码交付完成。发现实际 smoke 的代码错误须修复复查，不能用 NOT_RUN 遮盖；若只是资产/
GPU 缺失，则代码可通过但对应 runtime 保持未验证，不称可直接全量正式运行。

`FORMAL_EXPERIMENTS=NOT_RUN` 是本任务预期状态；E1/E2 缺资产也允许明确 NOT_RUN，不降低
实现覆盖要求。审查通过后停止，不擅自 commit/push、下载/跑正式实验、扩展设计或开始论文。
最终向用户简要说明已保存文件、实际验证、未完成条件，以及下一步需要的最小操作。
