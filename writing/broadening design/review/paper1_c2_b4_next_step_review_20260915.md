# C2/B4 完成后的下一步审阅

日期：2026-09-15；对象：C2 E1 final overlap 报告、B4 runtime handoff 报告及下一阶段任务书。

## 结论

C2 的 `E1_FRAME_READY` 只证明 200 条 HarmBench 候选已经完成预筛/near-match 双审核并产生40条选择。其派生物仍带旧 reference digest `8be3...`，而最终 scope-fix snapshot 是 `d148...`；B4 将其拒绝并报告 `E1_CONSUMER_PENDING` 是正确的 fail-closed 行为。C2 的原始 scope-fix审核有效，不需要重新发送17条或400条请求。

B4 的 `CODE_CONTRACT_PASS` 和 `CORE_REAL_SMOKE_PASS/NON_EVIDENCE` 足以解除 Core 方向构造的运行时前置；safe-pair recovery 的 `READY_FOR_CONSTRUCTION` 足以解除 construction 数据门槛。正式 E1 仍需 C3/B5 以最终 digest 重建并消费，不能把 smoke 或 provisional selection 写成论文结果。

## 任务安排

| 任务 | 会话 | 依赖 | 结果/停止点 |
|---|---|---|---|
| C3 E1 派生物最终化 | 原C续作 | C2 raw、最终700-reference snapshot | 不重审；产生同 digest 的 final ledger/identity/40条 selection；CPU PASS 或 E1_FRAME_BLOCKED |
| B5 E1 consumer handoff | 原B续作 | C3 final 文件 | 纯CPU `READY_FOR_RUN`；必要时创建 run-specific config；不运行模型 |
| Core directions/calibration | 新F会话 | B5 PASS、safe/code/smoke gates | prepare + build-directions；单卡顺序加载；不screen、不generation |

C3 与 B5 是顺序依赖。F 可以先做静态命令/资产检查，但在 B5 PASS 前不得创建正式 run 或读取过期 E1 frames；因此不安排第二个 GPU 实验与 C3 并行。论文写作、已有结果证据整理可独立进行，但不改变实验设计或运行输入。

## 边界审查

- 没有新增模型、层、方向 family、剂量、prompt、benchmark、预算或人审轮次。
- C3 只生成 final 派生副本，保留旧 provisional 文件；B5 只做消费者和 run-specific 数据路径适配。
- Core 任务允许代码已有入口自动构造 E2/E3 方向资产，但不额外设计实验块；每个扩展状态单独记录。
- 所有科学设计正文、易读版、实现规范和已批准来源 revision 只读；科学字段改变必须 `DESIGN_CHANGE_REQUIRED`。
- nohup/PID/log/exit 只用于实际批处理/GPU命令；退出0不代替业务检查；不生成运行前全项目 manifest。

结论：`NEXT_TASK_DOCUMENT_REVIEW_PASS`。当前正式 generation、Judge、analysis、human audit 和 archive 均未开始；C3/B5完成后再进入 Core directions/calibration，然后才可安排 Core dose screen。
