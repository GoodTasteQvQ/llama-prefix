# Core 正式生成任务：有边界自审

日期：2026-09-19；对象：`implementation/paper1_server_codex_core_formal_generation_task_nohup.md`。

结论：`BOUNDED_TASK_REVIEW_PASS`。本机任务决策为单会话执行 Core 正式 generation，结束后交付审核；当前没有需要另开并行 GPU 任务的工作。新 A-Core-generation 会话可以完整接手，旧 Restore 会话只需保留历史记录，不需要保持运行。

## 验收证据和边界

原 1,200 条记录逐条核验及 15/15 artifact hash 的结果已在 Core full rescore review 中保存。本轮只补核五份启动证据，不重复全量审计或既有模型调用。PID 2523254、真实 `.exit=0`、monitor 的完整运行终态及本次 run 一致；runtime.release 占位缺口仍如实保留，不改历史记录为 PASS。

本机用实际 F2 frames、v2.3 config 和已接受的 A/S，经现有 `_dose_rhos` + `build_core_schedule` 验证转换接口与日程：11,440 行/唯一 response IDs，两个模型各 5,720，四块 10,400/200/780/60。检查逐行剂量、层和 benign 条件，确认没有 development 行。仅本地内存计算，未创建正式运行、未完整执行依赖服务器路径的 config validation，未加载模型或 Judge。摘要：`.codex-temp/local_core_formal_schedule_review_20260919.json`。

## 有限审查结果

| 审查点 | 判断 |
|---|---|
| 科学设计 | 不改变模型/层/模板/hook/方向/剂量/decoder/数据，输入设计只读；完整保留 public expansion 与 v2.3 overlay |
| 是否重复已完成任务 | 不重跑 prepare、方向、1,200 development、rescore、screen、A/S、smoke 或启动 probe |
| 必要实现 | 唯一新增 helper 解决真实的 groups→decisions 接口及独立 run 初始化；调用既有 schedule/generation API，非另建实验框架 |
| 新旧证据隔离 | 新 header/snapshot 对应当前实现；tensor/frames 原字节复用，方向构造 identity 与本次 runtime identity 不混用 |
| 授权 | 同一任务完成最小衔接、聚焦检查和正式启动，不增加 approval/提案/专门 CPU gate 轮次 |
| nohup | 命令使用现有单卡 wrapper；薄 shell 外壳记录真实子进程退出码，不依赖下一工具调用的跨 shell wait；不把提交成功等于实验成功 |
| 进度与中断 | 直接 shell 单执行者，按 attempts 而非只按安静日志看进度；断线后先确认原 worker，禁止盲目重提 |
| 错误与缺失 | 原技术 retry 上限不变；保留崩坏/空回答/terminal failure；不新增零技术失败标准，不凭 CLI exit=0 掩盖未执行或 release 错误 |
| 交付 | 明列 helper/测试、完整 run、tensor/snapshot、报告、evidence 与 nohup 文件，避免再次只同步摘要 |
| 清理 | 不执行删除；仅沿用已保存的可备份旧 prepare 副本清单，不删除现行输入或协议历史 |

任务中的 Bash 启动片段已在本机提取后用 Git Bash `bash -n` 检查，退出 0；只做语法验证，未在本机执行 Linux 启动命令。现有源码与原实验设计没有为编写此任务而修改。无需再扩展测试范围或增加新的审核会话。

## 后续工作清单

| 模块 | 规模 | 当前状态 | 下一步 / 结果 |
|---|---|---|---|
| safe pairs / 固定划分 | 516 source、300 executable、5×40 + development100 | 已完成 | 复用，不重审 |
| Core 方向与校准 | Qwen/Llama，各 8 Rogue + 5 contrastive | 已完成 | 复用层9/11 tensor 与 mu |
| Core development / A/S | 1,200 generation + v2.3 四分类重评分 | 已验收 | 20 cells 通过，四组 A/S 已固定 |
| Core 正式生成 | 11,440 logical，两个模型各 5,720 | **本轮执行任务** | 独立 run，nohup 后交付 |
| Core 正式 Judge / 汇总 | 对 Core 正式输出按各 domain 的既有规则评分；技术缺失单列 | 待生成交付后 | four-class、设计规定的 binary 对照、完整性与配对结果；不自动混入旧协议标签 |
| E1 外部提示 | 2,320 generation | 资产和最终 overlap frame 已就绪；实验未运行 | 接线已固定 final40，继承 Core 方向/剂量，生成与 Judge |
| E2 第三架构 | 600 screen + 1,160 evaluation | 资产/runtime probe/修复已有；正式实验未运行 | 使用修复后的实际 release 证据完成该块条件核对、screen/选剂量与评估，旧 Gemma 占位不算通过 |
| E3 额外层 | 1,200 screen + 2,560 evaluation | 正式实验未运行 | 复用可核验方向资产，补足必要层校准并完成该块 screen/评估，不重跑 Core 层 |
| 分析与人工审核 | 按原设计；Core 200 + 各扩展40 的人工 packet | 待上述结果 | 汇总 bootstrap/对比，保留人工审阅真实性及缺失；不得把自动判定称人工审核 |
| 最终归档 | 各块结果、来源、协议与图表 | 待结果闭合 | 最终 hash、结果/代码归档，保留 Calibration-Frame Sensitivity 已有支持性结果 |

E1/E2/E3 是后续计划，未在本任务预先授权其执行，也不因当前 A/S 可用就宣称它们的科学结果通过。generation 规模不把 Judge、retry、smoke、activation forward 重复计入。
