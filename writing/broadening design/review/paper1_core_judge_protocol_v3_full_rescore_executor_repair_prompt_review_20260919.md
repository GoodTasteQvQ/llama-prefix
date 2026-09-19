# Full-rescore executor repair task review

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_judge_protocol_v3_full_rescore_executor_repair_prompt_nohup.md`

## 结论

`TASK_PROMPT_REVIEW_PASS`

本任务只修复 full-rescore executor 的停止、持久化和 recovery handoff 绑定，不发送模型/Judge 请求，也不运行正式实验。真实 full rescore、Core gate 和 A/S 选择仍保持为下一道独立任务。

## 有边界审查

- 修复项均直接对应 readiness 代码审查发现：retry 耗尽继续处理、批量写证据、未强制读取 recovery handoff。
- 新增测试只覆盖失败停止、立即落盘和 handoff fail-closed，不扩展数据、模型、方向、层、剂量或指标。
- 保留旧 evidence，不要求删除历史失败文件；报告必须区分 authoritative 与 stale 文件。
- 不修改任何原实验设计或 config；不创建额外模型、数据集、批准层或分析系统。
- 明确禁止 `--live`、`FULL_RESCORE_APPROVED=1` 和任何 Judge 请求。

审查通过后保存任务书和本记录；服务器完成后必须同步报告、全部修改源码/测试和 readiness evidence 增量。
