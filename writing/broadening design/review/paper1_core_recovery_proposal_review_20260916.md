# Core recovery proposal 边界审阅

日期：2026-09-16。

## 决策

F4/E2R 已分别通过实现与离线测试审查，但当前仍不能开始正式评估。下一步只允许由 `A-recovery` 会话生成一个受限 Core Judge recovery proposal 和输入冻结证据；该会话不得发送新的 Judge 请求。

## 必须保持的科学边界

- 旧 F2 的 1,200 generation、Judge records、13 条失败、`dose_decisions.json` 和 source snapshot 只读。
- recovery 只消费已有 13 条 generation completion；不重新生成，不改变模型、层、方向、rho、seed、模板、rubric、decoder、预算或 2% missing gate。
- 新 run 独立保存，最多 13 次新的 four-class Judge 请求；binary=0，generation retry=0。请求授权必须在 proposal 审查后单独给出。
- 新请求失败时保持 missing；不得手工标签、从 completion 推断标签、复制其他家庭的 A/S 或放宽门槛。
- proposal 阶段不加载模型、不用 GPU、不运行 Judge/screen/generation/evaluation。

## 有界自审

- [x] 任务只解决旧 F2 的 13 条 Judge 解析失败，不扩大实验设计。
- [x] 设定了明确的 13 请求上限和旧新 ledger 隔离。
- [x] 保留原 2% gate 和所有失败状态，没有自动批准 recovery。
- [x] 没有包含 E1/E2/E3 正式实验、人工审核或额外数据集工作。
- [x] F4/E2R 的代码修复不被回写到旧 F2；服务器需另行同步修改代码和测试文件。

审阅结论：`PROPOSAL_TASK_PASS`。proposal 完成并审查通过前，保持 `CORE_DOSE_SCREEN_REMAINS_BLOCKED` 和 `FORMAL_EVALUATION_NOT_RUN`。
