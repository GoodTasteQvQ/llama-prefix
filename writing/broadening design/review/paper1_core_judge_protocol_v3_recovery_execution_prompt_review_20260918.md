# Core recovery execution prompt boundary review

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_judge_protocol_v3_recovery_execution_prompt_nohup.md`

审查结论：`PASS`

## 证据基础

- launcher readiness 报告为 `RECOVERY_LAUNCHER_READY`。
- 12 条 executor/launcher fixture 测试通过。
- blocked CLI 在 approval 缺失时 exit 3，模型加载和 Judge 请求均为 0。
- 当前 executor、launcher、测试文件的 Linux SHA256 已与报告一致。

## 范围审查

- 只运行 proposal 冻结的 13 条旧 F2 `PARSE_FAILURE`。
- 不运行 full rescore、Core screen、A/S 选择、正式 evaluation、E1/E2/E3、分析或
  人工审核。
- 不使用通用旧 `run_real_judge`，不改变旧 retry/legacy parser 语义。

## Approval 与失败闭合

- approval 是负责人创建的 canonical JSON object；任务不会自行创建或猜测 approval。
- approval 绑定 proposal、manifest、v2.3 design/config、executor 和 launcher 的
  当前源码 SHA256。
- 任意缺失、哈希不匹配、非法 JSON、thinking marker、身份错误、raw/diagnostics
  缺失或运行时异常都立即停止；binary/retry 永远为 0。

## 证据与同步要求

- nohup、PID/log/.exit、每条 request/raw/diagnostics/hash、release 和 boundary audit
  均有明确路径。
- 预期不修改代码；如服务器确需修改，必须停止、列出文件和 SHA256，并同步修改文件
  后重新审查，不能沿用旧 approval。

## 非过度设计审查

- 不新增数据集、模型、请求规模或统计指标。
- 13 条 recovery 是当前 gate 所需的最小范围，后续 full rescore 仍保持独立批准。
- approval、运行和归档边界清楚，无重复 probe 或额外审查轮次。

结论：任务书可保存并推送。负责人仍需实际创建并确认 canonical approval，服务器
Codex 才能发送最多 13 条请求。
