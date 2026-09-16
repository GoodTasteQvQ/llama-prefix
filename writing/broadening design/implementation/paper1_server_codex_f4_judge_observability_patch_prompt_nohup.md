# F4：Judge 解析失败可观测性最小修复

版本：`judge-observability-patch-v1`；交给新 F4 会话。该任务只修复未来运行的证据留存，不恢复或重算 F2 结果。

## 输入与前置结论

先阅读：

- `writing/broadening design/report/paper1_core_screen_parse_forensic_report.md`
- `writing/broadening design/report/paper1_core_dose_screen_report.md`
- `writing/broadening design/implementation/paper1_server_codex_post_audit_task_index.md`
- 原实验设计三份只读文件

F3 已确认：F2 的 13 条失败在当前重试预算内不可恢复，原始 Judge completion/diagnostics 在异常路径未持久化。因此本任务不得把旧 F2 记录改成可解析结果。

## 允许修改

- 共享实现：`paper1_broadening/judge.py`
- 仅为验证该行为新增或修改聚焦测试：`tests/paper1_broadening/`
- 本任务报告：`writing/broadening design/report/paper1_judge_observability_patch_report.md`
- 其余脚本、日志、PID、`.exit` 和测试临时输出放项目内 `.codex-temp/paper1_f4_judge_observability/`

执行前记录 `git status` 和上述文件已有 diff/未跟踪状态；不得重置或覆盖已有用户修改。

## 必须保持不变的行为

1. 不改变 four-class/binary parser 的接受集合、模板、rubric、semantic split、decoder、retry 上限、label 或 missing 规则。
2. `PARSE_FAILURE` 仍然是失败；不得由 completion 猜测 `safe`、`refusal`、`broken` 或 `unsafe`。
3. `actual_call_count`、request identity 和现有成功解析记录的字段语义保持不变。
4. F2 run、F2 ledger、Judge records、dose decisions、source snapshot、配置、E1/C3 文件和三份原实验设计完全只读。

## 实现要求

- 当 `_final_completion` 已得到 raw/diagnostics 但 semantic split 或 strict parse 抛出 `JudgeParseError` 时，`four_class` 应保留该次调用的原始 completion、可用 diagnostics 及明确的错误信息。
- 如果异常发生在 raw/diagnostics 尚未生成的位置，仍返回 `raw=null`、`diagnostics={}`，但要有可区分的 observability 状态；不得伪造内容。
- 不要把异常改成成功，也不要改变 retry 控制流。保持与现有 ledger/报告兼容；字段新增必须是向后兼容的证据字段。

## 离线测试

使用项目 Python 环境和项目内临时目录，通过 `nohup` 保存 PID、日志、`.exit`。不下载、不加载模型或 Judge、不使用 GPU、不联网。

至少覆盖：

1. fake tokenizer/runtime 让 `_final_completion` 在已生成 raw 后 split 失败；断言返回 `PARSE_FAILURE`，原文/diagnostics 被保留，调用次数仍为 1。
2. fake runtime 让失败发生在 raw 生成前；断言仍为失败且 raw/diagnostics 为空，不生成伪造值。
3. 已有成功 four-class 解析、binary 解析和 retry 相关测试继续通过。
4. Python compile、`git diff --check` 和聚焦 pytest 通过；退出码与业务断言分别记录。

## 输出与停止条件

报告必须列出：实际修改文件、修改前后行为边界、测试命令/PID/log/exit、未修改的 F2 原件和原实验设计、是否需要新 run。明确写入：

`F4_IMPLEMENTATION_PATCH_PASS`（仅当测试和边界审计都通过）

以及：

`F2_CORE_DOSE_SCREEN_REMAINS_BLOCKED`
`FORMAL_EVALUATION_NOT_RUN`

完成一次有边界自审后停止。不要运行 prepare、screen、generation、Judge 或正式 evaluation；不要 commit/push。若发现必须改变 parser/rubric/retry 或修改科学字段，立即停止并报告 `DESIGN_CHANGE_REQUIRED`。
