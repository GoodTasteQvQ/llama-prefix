# Core Judge v3 direct-JSON budget contract repair

执行会话：`A-judge-v3-budget-repair`
协议：`core-judge-protocol-v3-direct-json`

本任务只修复 Phase 1 暴露的两个预请求问题：direct-JSON 模式把预算硬编码
为 512，而当前批准的 probe 使用 1296；预检在导入本地 `paper1_broadening`
包前因 `ModuleNotFoundError` 退出。本任务不加载模型、不发送 Judge 请求，
也不执行 probe、recovery、full rescore 或正式实验。

## 事实和保护边界

Phase 1 的 `DIRECT_JSON_PROBE_BUDGET_MISMATCH` 是预请求失败。实际计数为：
模型加载 0、four-class 请求 0、binary 请求 0、generation retry 0、additional
Judge retry 0。旧 F2、旧 recovery、v2 probe、v2.1 设计、canonical config、
方向、safe-pair 数据和全部 behavior completion 必须保持只读。

当前旧 Phase 1 批准文件和旧五个代码哈希只作为历史证据；本任务完成后旧批准
不得继续用于运行。不要修改或覆盖旧 Phase 1 报告、旧 run、旧 ledger 或旧批准
文件。

## 允许的最小实现变更

1. 保留 legacy omitted-field 行为：
   `enable_thinking=true`、`max_new_tokens=1296`、semantic `</think>` split、
   `strict_final_json_v1`。
2. 将显式 direct-JSON 配置固定为本次批准协议：
   `enable_thinking=false`、`max_new_tokens=1296`、
   `parser` 或 `parser_mode=strict_direct_json_v1`。不能再把 direct 模式预算
   硬编码为 512，也不能把 512 的 behavior decoder 设置改成 1296。
3. 保持 strict direct JSON 解析规则、label domain、rationale 要求、thinking
   marker 拒绝、无 regex/substring/manual-label/fallback 行为不变。
4. Judge identity 和 per-call diagnostics 必须记录实际解析到的
   `max_new_tokens=1296`。不得修改模型、endpoint、tokenizer/chat template、
   dtype、greedy/beam、rubric、generation retry 或 2% missing gate。
5. 修复预检导入路径，使在仓库根目录使用正式环境 Python 时能够导入本地
   `paper1_broadening` 包。优先使用仓库内 `PYTHONPATH`/模块调用等最小路径
   修复；不得安装新模型、改环境、在线下载或借此重构包结构。

## 离线验证

所有检查使用单卡环境变量、Hugging Face offline 变量和 `nohup`，证据写入
`.codex-temp/paper1_core_judge_protocol_v3/budget_repair/`，每项保存 PID、
日志和 `.exit`。预检必须明确执行：

- `import paper1_broadening` 及 Judge/config 导入检查；
- legacy omitted-field 解析为 `true/1296/strict_final_json_v1`；
- direct 配置解析为 `false/1296/strict_direct_json_v1`；
- direct 配置为 512、缺字段、混合字段时 fail-closed；
- identity/diagnostics 记录 1296；
- strict direct JSON 原有接受/拒绝测试；
- 完整 `tests/paper1_broadening`、Python compile、`git diff --check`。

这些检查不得加载真实模型、调用 Judge endpoint 或读取六条 probe 输入。若导入
仍失败、测试失败或出现未授权科学变更，写失败标记并停止。

## 报告和停止条件

保存新报告：
`writing/broadening design/report/paper1_core_judge_protocol_v3_direct_json_budget_repair_report.md`。
报告必须包含：

- `DIRECT_JSON_BUDGET_CONTRACT_REPAIRED` 或明确失败标记；
- `IMPORT_PREFLIGHT_PASS` 或明确失败标记；
- focused/full test、compile、diff、PID/log/.exit 结果；
- 变更文件及 SHA256；
- 旧 Phase 1 报告、旧批准、旧 F2、旧 recovery、v2 probe 和设计文件的保护哈希；
- `DIRECT_JSON_PROBE_NOT_RUN`、`CORE_RECOVERY_V3_NOT_RUN`、
  `CORE_SCREEN_V3_NOT_RUN`、`FORMAL_EVALUATION_NOT_RUN`；
- `NEW_PROBE_APPROVAL_REQUIRED`。

边界审计必须确认模型加载和 Judge 请求均为 0，旧文件未修改，且当前旧批准因代码
哈希变化不能继续使用。不得生成新的 probe 结果、v2.3 设计或 recovery 批准文件。
本任务不 commit/push；完成后停止，等待负责人审查新报告并签发新的 1296 probe
批准文件。
