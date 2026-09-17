# Core recovery failure closure prompt review

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_recovery_failure_closure_prompt_nohup.md`

审查日期：2026-09-17。

## 边界审查

- 任务范围是一次只读 forensic closure；不新增 Judge、generation、screen 或正式评估。
- 任务明确禁止修改 parser、rubric、decoder、endpoint、2% gate、旧 F2、三份原实验设计和既有结果。
- 输出仅为一份收尾报告与项目内临时审计文件；不要求下载模型、安装依赖、建立新环境或提交代码。
- 所有运行检查要求项目内 `.codex-temp`、`nohup`、PID、日志和 `.exit`，符合服务器运行约束。
- `DESIGN_CHANGE_REQUIRED` 只作为决策标签和未来 proposal 的问题清单，不允许在本任务实施科学变更。
- 已明确区分 pre-existing 工作树差异，避免误删或覆盖其他会话成果。

## 过度设计检查

- 输入文件均为本次失败闭合所需的 run、F2 保护文件和既有设计；没有重复运行或扩大样本的要求。
- 核对项目是逐行、逐 hash、逐 gate 的最小交叉验证，能够覆盖当前阻断原因。
- 没有新增审阅者、人工标签、网络下载、模型加载、全量权重重哈希或不必要的统计分析。

## 结论

`REVIEW_PASS`。任务书边界清楚、无科学规则放宽、无对旧结果的回写路径，也没有超出“确认 recovery 是否可继续”的必要工作。可交给服务器 `A-closure` 会话执行。

另对 `paper1_server_codex_post_audit_task_index.md` 的状态入口做了非科学性纠偏：仅将 recovery 的当前状态从“待批准执行”更新为“已耗尽且阻断，下一步为 A-closure”，未改动实验设计、参数、结果或历史记录。
