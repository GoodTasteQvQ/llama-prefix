# Full-rescore readiness task prompt review

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_judge_protocol_v3_full_rescore_readiness_prompt_nohup.md`

## 审查结论

`TASK_PROMPT_REVIEW_PASS`

该任务被限制为全量重评分执行器的实现、离线 fixture 和输入绑定检查，不会发送模型/Judge 请求，也不会启动 formal evaluation。它把已通过的 13 条 recovery 作为只读前置证据，不把 recovery labels 混入 1,200 条新评分。

## 范围审查

- 明确绑定 v2.3 direct-JSON：`enable_thinking=false`、Judge `max_new_tokens=1296`、strict parser、behavior decoder 512。
- 明确 1,200 logical identity、20 cells、每 cell 60 条及原 2% missing gate。
- 明确 Judge 技术/解析重试最多一次并单独计数，禁止 generation retry、binary、无限重试和旧 label 回填。
- 明确旧 F2、旧 recovery、设计、配置和历史 evidence 只读；没有要求清理或重写旧文件。
- 明确 evidence 目录中旧阻断文件的 `HISTORICAL_STALE` 处理，新增 handoff 清单以消除歧义，未改变科学结果。
- 明确先实现/离线验证，再由后续任务单独执行真实 full rescore。

## 过度设计审查

- 没有增加模型、数据集、方向、层、剂量、指标或论文主张。
- 新增的 executor、launcher、fixture 和 handoff manifest 只服务于当前 1,200 条重评分的可追溯性。
- 没有要求重新生成 behavior completion，也没有要求复制整套旧结果。
- 没有引入新的批准层；负责人授权仅用于准备阶段，真实运行仍由独立 launcher 的预检边界控制。

## 保存前检查

- 任务书与 v2.3 设计、recovery report 和当前配置一致。
- 任务书要求服务器 Codex 输出所有新增/修改文件，满足后续同步要求。
- 任务书要求 nohup、PID、日志和 `.exit`，并在离线测试阶段停止。

审查通过后保存并提交任务书与本审查记录；不修改原实验设计。
