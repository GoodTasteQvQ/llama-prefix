# Core Judge protocol v3: independently approved recovery execution

执行会话：`A-core-recovery-v3-execution`
协议：`core-judge-protocol-v3-direct-json`
工作目录：`/data/goodtaste_workspace/llama-prefix`

## 任务目标与范围

launcher readiness 已通过。本任务只执行 recovery proposal 中冻结的旧 F2 13 条
真实 `PARSE_FAILURE` 输入，用于修复旧 Core screen 的 Judge 缺失记录。它不是
full rescore、Core screen、A/S 选择或正式 evaluation。

旧 F2、旧 recovery、R2 probe、v2.1/v2.3 设计、canonical config、safe-pair
source/ledger、方向资产和历史结果全部只读。Recovery labels 必须写入全新的 run
目录，不能覆盖、合并或回写旧文件。

## 1. 唯一 approval gate

本任务已获得负责人授权，canonical approval 文件由负责人随任务材料提供：

`.codex-temp/paper1_core_judge_protocol_v3/CORE_JUDGE_PROTOCOL_V3_RECOVERY_APPROVAL.md`

尽管扩展名为 `.md`，文件内容必须是**完整 JSON object**，不能包含 Markdown 围栏
或其他文字。服务器 Codex 不得自行创建、猜测、修正或替换该 approval。缺失、JSON
解析失败、字段缺失或任何哈希不匹配时，写入 `RECOVERY_APPROVAL_BLOCKED`，实际
Judge 请求和模型加载必须为 0。

approval 至少必须包含以下字段和值：

```json
{
  "status": "APPROVED",
  "approved_at_utc": "2026-09-18T12:40:05Z",
  "protocol": "core-judge-protocol-v3-direct-json",
  "proposal_sha256": "892e69845cb7d1520bbde12b56e3c5ab3bbabdcf59eaea906a5574978c8f29d1",
  "manifest_sha256": "673baf9e4fe442df66a7e34f0a8d0f469c1e8bb243eb8fb9fbcb89fbc4e79e1c",
  "design_sha256": "f70b1c673806585d9b6196fdddb992787fa5ff741e9be7bc8d3efc166486fbe2",
  "config_sha256": "a36b1cf0fe5f1a992fd9e5b7788d00cbf85dea79dad6028f6b07342780d4fe86",
  "code_hashes": {
    "scripts/core_judge_recovery_executor.py": "1d2339bd0081389a326592425d826aa7d4ab8638034cd74c3ffeeab717485d4a",
    "scripts/core_judge_recovery_run.py": "e2a597698311a74704432014fcb82e24dbee78f1df6b71d27353fe1c87673b32"
  },
  "maximum_four_class_requests": 13,
  "per_input_maximum": 1,
  "binary_judge_requests": 0,
  "generation_retries": 0,
  "additional_judge_retries": 0,
  "enable_thinking": false,
  "max_new_tokens": 1296,
  "parser": "strict_direct_json_v1",
  "old_f2_read_only": true,
  "old_recovery_read_only": true,
  "full_rescore_and_formal_evaluation_not_approved": true
}
```

以上内容对应本次已授权的 canonical approval。服务器只核验该文件，不得修改其
内容；只有文件存在且所有字段和 SHA256 通过，才允许继续。

## 2. 运行前预检

使用服务器正式环境和单卡离线变量：

```bash
cd /data/goodtaste_workspace/llama-prefix
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export CUDA_VISIBLE_DEVICES=0
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
```

预检必须使用当前 Linux 字节并核验：

- readiness report 为 `RECOVERY_LAUNCHER_READY`；
- proposal 13-row manifest、proposal report、v2.3 design/config SHA256；
- executor SHA256=`1d2339bd0081389a326592425d826aa7d4ab8638034cd74c3ffeeab717485d4a`；
- launcher SHA256=`e2a597698311a74704432014fcb82e24dbee78f1df6b71d27353fe1c87673b32`；
- 13 行 ordinal 顺序、old F2 source line、prompt/completion/request hash；
- old F2、old recovery、R2 和设计保护哈希；
- canonical approval 存在且内容与本任务一致；没有同一 recovery run 的残留目录、
  活动 worker 或其他冲突 approval；
- 配置为 `enable_thinking=false`、Judge `max_new_tokens=1296`、
  `strict_direct_json_v1`，且 `runtime.decoder.max_new_tokens=512`。

预检必须在真实模型构造前完成。不要调用通用 `run_real_judge`，不要使用旧
legacy parser 或自动 retry。若任何检查失败，生成报告后停止，不修改源码或设计。

## 3. 受限 recovery 运行

使用新的唯一目录，例如：

`results/paper1_broadening/core-judge-protocol-v3-direct-json-recovery-<UTC>-<shortid>/`

运行命令必须使用 `nohup`，并保存 PID、日志和 `.exit`：

```bash
mkdir -p .codex-temp/paper1_core_judge_protocol_v3/recovery_execution
RUN_DIR="results/paper1_broadening/core-judge-protocol-v3-direct-json-recovery-<UTC>-<shortid>"
nohup /data/goodtaste_workspace/envs/llama-prefix/bin/python \
  scripts/core_judge_recovery_run.py \
  --run-dir "$RUN_DIR" \
  > .codex-temp/paper1_core_judge_protocol_v3/recovery_execution/recovery.log 2>&1 &
PID=$!
echo "$PID" > .codex-temp/paper1_core_judge_protocol_v3/recovery_execution/recovery.pid
wait "$PID"
echo "$?" > .codex-temp/paper1_core_judge_protocol_v3/recovery_execution/recovery.exit
```

执行规则固定为：

- 按 manifest ordinal 1..13 顺序处理；每条最多一次 four-class Judge；
- 使用旧 F2 原 prompt、completion、domain、Qwen3 Judge 和本地 tokenizer；不重新
  生成 completion；
- `enable_thinking=false`、Judge `max_new_tokens=1296`、
  `strict_direct_json_v1`、且 `runtime.decoder.max_new_tokens=512`；使用
  float32、greedy、one beam、local-files-only、GPU 0；
- binary Judge=0、generation retry=0、additional Judge retry=0；禁止并发、resume、
  retry、regex/substr 修复、手工标签、completion-derived label 或 legacy fallback；
- 每条请求前后持久化 request identity、input hash、raw、diagnostics、parser status、
  output hash 和调用计数；raw 或 diagnostics 缺失时记录真实缺失状态；
- 任一异常、超时、OOM、非法 JSON、thinking marker、identity mismatch 或证据缺失
  立即停止，不处理下一条。

## 4. 交付与停止

证据目录：`.codex-temp/paper1_core_judge_protocol_v3/recovery_execution/`。
至少保存 approval copy/hash、resolved config、runtime/Judge identity、13-row
request index、recovery events、Judge records、release、run manifest、PID/log/.exit、
artifact hash 清单和 final boundary audit。

保存报告：
`writing/broadening design/report/paper1_core_judge_protocol_v3_recovery_execution_report.md`

报告必须写明：

- `CORE_RECOVERY_V3_PASS`（13/13 合法且证据完整），或
  `CORE_RECOVERY_V3_FAIL`、`RECOVERY_APPROVAL_BLOCKED`；
- actual four-class、binary、generation retry、additional retry、model load 计数；
- `CORE_SCREEN_V3_NOT_RUN`、`FULL_RESCORE_NOT_RUN`、`FORMAL_EVALUATION_NOT_RUN`；
- old F2/old recovery 未覆盖、未合并、未回写；recovery labels 与旧 1,187 成功标签
  保持独立；
- 若成功，只表示 recovery 完成，不代表 full rescore 或科学结论。

预期不修改任何源码、设计、配置或旧结果。若必须修改，立即停止，列出修改文件及
SHA256，并将修改文件、测试和证据一并同步；不得在未重新审查和重新批准前运行。
任务完成后停止，不启动 full rescore 或正式实验。
