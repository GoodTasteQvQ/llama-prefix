# F3：Core screen 13 条 Judge 解析失败取证

版本：`core-screen-parse-forensic-v1`；交给新 F3 会话。该任务是只读取证，不是重新运行 screen。

先阅读 F2 报告、Core 静态交接报告、当前任务入口和原实验设计。使用 F2 原 run：
`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`。

## 目标与硬边界

1. 从 `screen_judge_records_core.jsonl`、generation ledger/attempts 和 schedule 中准确定位全部 13 条 `PARSE_FAILURE`，补齐每条的 model、family、rho、prompt/direction identity，并核对其 `actual_call_counts.four_class=2`。
2. 只读保存原始 four-class completion、diagnostics、response hash、Judge template/rubric hash 和 parser 返回值；判断每条失败属于：A）原始 completion 含可解析语义但 parser 缺陷；B）completion 确实没有有效 semantic final channel；C）身份/记录关联错误。不得凭 broken/unsafe 结果猜标签。
3. 检查 13 条是否集中在同一模型、rho、模板、长度或终止行为；只做描述性统计，不改变 label、missing 规则或 screen 结果。
4. 复核 F2 的 1,200 logical generation、1,200 首次 Judge、13 次既定技术 retry 计数，确认没有重复 generation、binary Judge 或隐藏调用。

禁止加载被测模型或 Judge，禁止调用任何新的 Codex/Judge 请求，禁止修改 F2 run、ledger、dose decisions、源码、配置、原实验设计、E1/C3 文件。不要删除或覆盖 raw。所有小型脚本和输出放项目内 `.codex-temp/paper1_f3_parse_forensic/`，批量读取可用 `nohup`，保存 PID、日志和 `.exit`。

## 决策输出

- 若能以现有 raw 证明是 parser/记录关联缺陷，只在 `.codex-temp/` 保存最小修复草案和离线测试建议，不实施修复，不重新 Judge；报告标 `PARSER_DEFECT_CANDIDATE`，并明确需要后续授权。
- 若 completion 本身不可解析，报告 `UNRECOVERABLE_UNDER_CURRENT_RETRY_BUDGET`；不得把缺失改成 safe/refusal，也不得自行追加 retry。
- 若发现身份或计数不一致，报告 `SCREEN_EVIDENCE_INCONSISTENT`；保持 F2 阻断。
- 如果要新增 Judge 调用、改变 parser/rubric、由 completion 推断标签或改写任何 F2 记录，立即停止并报告 `DESIGN_CHANGE_REQUIRED`，等待单独批准；本任务不执行这些动作。

保存 `writing/broadening design/report/paper1_core_screen_parse_forensic_report.md`，列逐条证据、分类、计数复核、未修改文件、命令/PID/log/exit 和 `FORMAL_EVALUATION_NOT_RUN`。完成一次有边界自审后停止，不 commit/push。
