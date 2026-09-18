# Core Judge protocol v3: recovery executor readiness and bounded-runner repair

执行会话：`A-core-recovery-v3-executor-readiness`
协议：`core-judge-protocol-v3-direct-json`
工作目录：`/data/goodtaste_workspace/llama-prefix`

## 任务目的与停止边界

recovery proposal 已冻结旧 F2 的 13 条真实 `PARSE_FAILURE`，但在执行 recovery
前必须确认代码能严格实现 proposal 的“一条一次、失败即停、direct JSON”契约。
本任务只审计并在必要时补齐一个受限 recovery executor；不执行 recovery。

本任务的实际模型加载、Judge 请求、generation、binary Judge、retry、full
rescore、Core screen、A/S 选择、正式 evaluation、E1/E2/E3、分析和人工审核必须
全部为 0。不得创建 recovery approval，不得把 readiness 结果当作 probe 或科学
结果。

旧 F2、旧 recovery、R2 probe、v2.1/v2.3 设计、canonical config、safe-pair
source/ledger、方向资产和历史结果只读。不得修改原实验设计；不得修改通用旧
`run_real_judge` 的既有 retry 语义来“顺便”适配 recovery。

## 1. 输入与保护

只读读取并记录 SHA256：

- `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.3_direct_json.md`
- `configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json`
- `writing/broadening design/report/paper1_core_judge_protocol_v3_recovery_proposal_report.md`
- `.codex-temp/paper1_core_judge_protocol_v3/recovery_proposal/recovery_input_manifest.jsonl`
- `.codex-temp/paper1_core_judge_protocol_v3/recovery_proposal/artifact_hashes.sha256`
- proposal 的 `final_boundary_audit.json`、`protected_asset_checks.json`、
  `future_recovery_constraints.json`。

核对 proposal 事实：13 条唯一输入；v2.1.1 base source=416；当前 expanded
overlay=516/509/300、5×40、development=100、unused=0、actual_k=40；overlay
只影响方向构造，不改变 recovery 输入或 Judge 协议。

将当前源码快照和 git commit 记录到 readiness 证据中。若发现旧 F2、设计、
config、R2 或 proposal evidence 已变化，写 `READINESS_BLOCKED_PROTECTED_ASSET`
并停止。

## 2. 必须实现的最小 executor 契约

先审计现有实现。若已有等价的 bounded executor，只需验证并补测试；若不存在，
新增最小独立入口（可放在 `paper1_broadening/` 或 `scripts/`），不要把 recovery
特殊规则散落到通用 screen/evaluation 路径。允许修改的范围仅为：

- direct-JSON Judge runtime 的配置接线；
- recovery executor/CLI；
- 与上述两项直接对应的离线测试和文档报告。

不得改变旧 F2 使用的通用 runner 的行为、旧 parser、旧 retry 规则或历史 artifact。
若实现需要扩大到这些范围，停止并写 `RECOVERY_IMPLEMENTATION_BLOCKED`，不要自行
扩大任务。

executor 必须在真正加载模型前 fail-closed 校验：

1. 唯一 approval 路径为
   `.codex-temp/paper1_core_judge_protocol_v3/CORE_JUDGE_PROTOCOL_V3_RECOVERY_APPROVAL.md`；
   缺失、`status` 非 `APPROVED` 或 proposal/manifest/design/config/code hash
   不匹配时，直接退出，实际请求和模型加载均为 0；readiness 任务本身不得创建该文件。
2. 输入 manifest 恰好 13 行，logical identity 唯一，且每行指向旧 F2 的真实
   `PARSE_FAILURE`；执行顺序固定为 manifest 顺序。
3. runtime 必须明确记录并强制：
   - `enable_thinking=false`；
   - `max_new_tokens=1296`；
   - `parser=strict_direct_json_v1`；
   - behavior generation decoder 仍为 `max_new_tokens=512`；
   - local-files-only、float32 Qwen3 Judge、greedy、one beam、单卡 GPU 0。
4. 每条输入最多一次 four-class Judge；binary=0、generation retry=0、additional
   Judge retry=0；禁止并发、自动 resume、legacy parser fallback、regex/substr
   修复、手工标签或 completion-derived label。
5. 任一失败、超时、OOM、非法 JSON、identity mismatch 或 evidence 缺失立即停止；
   不发送下一条请求。每条请求前后持久化 request identity、raw、diagnostics、
   parser status、调用计数和输入/输出 hash；raw 不可用写 `RAW_UNAVAILABLE`，不伪造。
6. recovery 输出必须进入新的 run 目录；不得覆盖、合并或回写旧 F2/旧 recovery，
   不得在 executor 内执行 full rescore 或正式 evaluation。

## 3. 离线验证（仍然零请求）

使用实验室 Python 和仓库内临时目录；不要访问 Hugging Face：

```bash
cd /data/goodtaste_workspace/llama-prefix
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export CUDA_VISIBLE_DEVICES=0
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

所有长命令使用 `nohup`，保存 PID、log、`.exit`；测试可用 CPU/标准库 fixture，
不得加载真实模型。至少覆盖：

- direct 配置解析为 false/1296/strict_direct_json_v1，decoder 仍为 512；
- 缺失或错误 approval 在模型构造前阻断；
- 13 行 manifest 的唯一性/顺序校验；
- 单条 parse/technical failure 不触发 retry，且不会处理下一条；
- raw/diagnostics 可观测性和 `RAW_UNAVAILABLE` 语义；
- old F2 与设计/config protection hash 不变；
- executor 不会启动 full rescore、screen、binary 或 generation。

不得用真实 Judge 请求替代 fixture 测试，也不得为了通过测试降低契约。

## 4. 交付报告与状态

证据目录：`.codex-temp/paper1_core_judge_protocol_v3/recovery_executor_readiness/`。
保存源码快照、输入/输出 hash、测试 PID/log/.exit、manifest 检查、approval
fail-closed 检查和最终 boundary audit。

保存报告：
`writing/broadening design/report/paper1_core_judge_protocol_v3_recovery_executor_readiness_report.md`

若无需代码修改且所有检查通过，写：
`RECOVERY_EXECUTOR_READY`、`RECOVERY_APPROVAL_REQUIRED`、
`CORE_RECOVERY_V3_NOT_RUN`、`FULL_RESCORE_NOT_RUN`、`FORMAL_EVALUATION_NOT_RUN`。

若完成最小代码修复且检查通过，写：
`RECOVERY_EXECUTOR_REPAIRED`、`RECOVERY_APPROVAL_REQUIRED`，并列出所有修改文件
及 SHA256；旧设计、旧 F2 和旧 recovery 仍必须 `UNMODIFIED`。新的 code hash 必须
成为后续 approval 的必需字段，旧 proposal approval 不得复用。

若任何保护、契约或离线测试失败，写 `RECOVERY_IMPLEMENTATION_BLOCKED`，不创建
approval、不加载模型、不发送请求。

完成边界自审后停止，不 commit/push。服务器 Codex 不得自行批准 recovery，也不得
继续执行下一阶段。
