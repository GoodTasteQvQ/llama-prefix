# Core full rescore、screen gate 与 A/S 任务书审查

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_full_rescore_screen_as_task_prompt_nohup.md`

结论：`TASK_PROMPT_REVIEW_PASS`

## 范围审查

- 任务只把既有 1,200 条 F2 generation 的 Judge 重评分、20-cell 缺失 gate 和四组 A/S 选择串成一个交付窗口；没有增加模型、层、prompt、方向、rho、数据集或正式 evaluation。
- full rescore、screen gate、A/S 选择的输入和输出边界被分开写明，避免把 executor 的通用 gate 状态误当成四组剂量决策。
- 使用现有 `choose_doses` 规则和 v2.3 direct-JSON 预算；适配步骤仅在现有产物格式不兼容时允许最小 run-local 处理，并要求测试和不改科学设计。
- 没有引入新的 approval 文件、manifest 体系或重复的审计层；只要求既有 readiness/handoff 校验和一次收尾 hash。

## 安全与停止条件

- 明确 single GPU 0、offline、项目内临时目录、显式 Python 和一次 `nohup`。
- 真实运行前强制检查 readiness boundary、recovery handoff、输入计数和旧文件保护。
- 禁止旧 Judge 标签、binary Judge、generation、E1/E2/E3、人工审核和正式分析混入本任务。
- contract、retry 耗尽、missing 超门槛、身份或持久化异常均保留部分证据并停止，不重跑、不删结果、不改 gate。
- 旧 F2、old recovery、设计、config、manifest 和方向资产只读；科学变化必须报告 `DESIGN_CHANGE_REQUIRED`。

## 交付审查

- 报告要求列出实际命令、进程证据、四组 A/S、20-cell accounting、release、hash 和未运行阶段。
- 要求同步 raw/request/attempt/event/decision 以及所有新增源码和测试，报告不能替代结果文件。
- 任务结束后停止并等待负责人审查；没有把 `CORE_SCREEN_V3_PASS` 或 A/S ready 自动解释成正式实验结论。

未发现过度设计、重复预算或会改变原实验设计的要求，审查通过后保存并推送该任务书及本审查记录。
