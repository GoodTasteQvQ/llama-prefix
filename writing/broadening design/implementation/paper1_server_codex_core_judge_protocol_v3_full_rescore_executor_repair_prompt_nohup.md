# Core Judge protocol v3：full-rescore executor 最小修复与离线复核

执行会话：`A-core-screen-v3-full-rescore-repair`
协议：`core-judge-protocol-v3-direct-json`

## 任务目标

修复 full-rescore readiness 审查发现的执行器证据和停止语义缺口。此任务只做源码/测试修复、只读输入绑定复核和离线验证，**不得加载模型、不得发送 Judge 请求、不得运行真实 full rescore、不得运行 Core screen、A/S 选择或正式评估**。

当前 readiness 的输入绑定已通过：1,200 identities、20 cells、每 cell 60 条；13 条 Core recovery 已通过。修复必须继续使用 v2.3 direct-JSON：Judge `enable_thinking=false`、`max_new_tokens=1296`、`strict_direct_json_v1`；behavior completion 仍来自旧 F2，decoder 512 只是旧 completion 的身份约束。

## 必读材料

- `writing/broadening design/report/paper1_core_judge_protocol_v3_full_rescore_readiness_report.md`
- `writing/broadening design/implementation/paper1_server_codex_core_judge_protocol_v3_full_rescore_readiness_prompt_nohup.md`
- `scripts/core_judge_full_rescore_executor.py`
- `scripts/core_judge_full_rescore_run.py`
- `scripts/build_full_rescore_readiness.py`
- `scripts/full_rescore_boundary_audit.py`
- `tests/paper1_broadening/test_full_rescore_executor.py`
- `tests/paper1_broadening/test_full_rescore_launcher.py`
- `.codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness/`
- `.codex-temp/paper1_core_judge_protocol_v3/recovery_execution/`

## 不可违反的边界

1. 不修改任何原实验设计、v2.3 设计、canonical/run-specific config、safe-pair/JBB/HarmBench 数据、方向 tensor、旧 F2、旧 recovery、旧 Judge ledger 或旧 dose decisions。
2. 只允许修改本次 readiness 新增的四个脚本和两个 full-rescore 测试；如需修改其他文件，先写 `DESIGN_CHANGE_REQUIRED` 并停止。
3. 不删除 readiness evidence 中的旧失败尝试。报告必须区分 authoritative successful artifacts 与历史 stale artifacts。
4. 不下载模型、不联网、不升级环境、不使用双卡；所有验证使用服务器正式 Python、项目内 `.codex-temp` 和 `CUDA_VISIBLE_DEVICES=0`。
5. 不创建或猜测任何 live approval，不设置 `FULL_RESCORE_APPROVED=1`，不调用 `--live`。

## 必须修复的三个问题

### 1. retry 上限耗尽必须停止后续 identity

当某 identity 的技术失败或 strict direct-JSON parse failure 在允许的最后一次尝试后仍失败时，executor 必须：

- 写出该 identity 的完整 attempt/raw/diagnostics/stop reason/call count；
- 将其记为 missing/technical failure/parse failure，而不是合法 label；
- 设置全局 stopped 状态并立即停止后续 identity；
- 结果中 `stopped_on_contract_failure` 或等价字段必须可区分；
- 禁止把“重试耗尽”当成继续处理的普通结果。

新增 fixture 覆盖：第 1 条两次技术失败时只调用第 1 条两次，不能调用第 2 条；第 1 条两次 parse failure 时同样停止。已有“一次技术失败后第二次成功”测试必须继续通过。

### 2. 每次尝试必须立即持久化

真实运行可能在 1,200 条中途被中断。executor 必须在每次 backend 返回后立即追加并 flush/fsync 至少以下证据：

- `attempt_records.jsonl`：ordinal、attempt、request identity、status、raw/raw hash、diagnostics/diagnostics hash、token/stop 信息和 error；
- `events.jsonl`：request、response、parsed/failure 等事件；
- 已完成 identity 的 `request_records.jsonl`，或者等价的可恢复记录。

写入必须使用 append-only 语义；重启/异常不能覆盖已存在记录。不要在本任务增加 resume 逻辑，除非现有代码已经支持且不会引入重复请求。新增 fixture 在 backend 于第 2 条抛出异常后检查第 1 条证据已经落盘并可解析。

### 3. full-rescore 预检必须绑定 recovery 成功交接

`verify_readiness_inputs()` 或等价的 live preflight 必须读取：

`.codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness/recovery_handoff_manifest.json`

并 fail-closed 验证：

- `status == CORE_RECOVERY_V3_PASS`；
- records=13、ordinals=1..13、raw_files=13、diagnostics_files=13；
- actual_four_class=13、binary=0、generation_retry=0、additional_retry=0；
- `run_artifact_verification == 0`；
- manifest 中记录的 canonical evidence SHA256 与 recovery evidence 当前文件一致；
- `.codex-temp/paper1_core_judge_protocol_v3/recovery_execution/preflight.status` 和 `call_counts.json` 只能作为 `HISTORICAL_STALE`，不得被误当作本次成功状态。

新增 fixture 覆盖 recovery handoff 缺失、状态不是 PASS、canonical evidence hash 不匹配时均不构造 backend、不创建模型、不发送请求。

## 运行证据增强

在不启动 live 的前提下，为后续执行准备最小的运行收尾接口：

- executor/launcher 的成功或阻断结果必须能写出 `terminal_accounting.json`、runtime/release 状态占位或实际状态、`artifact_hashes.sha256` 和 boundary status；
- 不伪造模型 release。fixture 只能标注 `FIXTURE`，不能写成真实 runtime PASS；
- live 路径继续在 preflight 后才延迟导入 Judge runtime，并保留 `FULL_RESCORE_APPROVED=1` 的显式门控。

不在本任务实现 A/S 选择或正式分析；只确保后续任务能够读取完整的新 Judge records 和 20-cell accounting。

## 阶段验证

所有命令使用 `nohup`，保存 PID、日志和 `.exit`，并把最终采用的命令和文件名写入报告。服务器环境：

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening
export TMPDIR="$PWD/.codex-temp" TMP="$TMPDIR" TEMP="$TMPDIR"
export PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
```

至少完成：

1. Python compile；
2. focused full-rescore tests，包含上面三个新增失败 fixture；
3. protocol-safe `tests/paper1_broadening` rerun；
4. manifest/input/boundary audit；
5. `git diff --check` 和 shell syntax（若脚本有 shell 改动）。

不要把旧 recovery 的 live-sensitive 测试混入本次 no-model 结论；若未过滤全套 pytest 仍会触发旧 recovery 模型路径，报告必须保留该失败原文并明确 protocol-safe 测试范围，不能声称未过滤全套通过。

## 交付与停止

报告：

`writing/broadening design/report/paper1_core_judge_protocol_v3_full_rescore_executor_repair_report.md`

报告必须写出：

- `FULL_RESCORE_EXECUTOR_REPAIRED` 或 `FULL_RESCORE_EXECUTOR_REPAIR_BLOCKED`；
- `CORE_RECOVERY_V3_PASS`（只引用，不重复计数）；
- `CORE_SCREEN_V3_NOT_RUN`、`FULL_RESCORE_NOT_RUN`、`FORMAL_EVALUATION_NOT_RUN`；
- 每个修改文件及 Linux 字节 SHA256；
- 新增 fixture 的断言和结果；
- 每个 nohup PID、日志、`.exit`；
- readiness evidence 中 authoritative/stale 文件的区分；
- 最终 boundary self-audit。

完成后停止，不 commit/push，不运行任何模型或 Judge。同步报告之外，必须列出全部修改的源码和测试文件；负责人会在本地审查后决定是否合并 full rescore、Core screen gate 和 A/S 选择。
