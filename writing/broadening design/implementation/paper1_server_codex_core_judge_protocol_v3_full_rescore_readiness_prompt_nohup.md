# Core Judge protocol v3：全量重评分执行器实现与离线就绪审查

执行会话：`A-core-screen-v3-full-rescore-readiness`
协议：`core-judge-protocol-v3-direct-json`

## 任务目标

实现并审查一个**新的、独立的** Core screen full-rescore executor/launcher，供下一阶段对旧 F2 的 1,200 条 behavior completion 重新进行 Judge。此次任务只做代码实现、离线 fixture、输入绑定检查和边界审查，**不得加载模型、不得发送 Judge 请求、不得启动 full rescore**。

当前 recovery 已通过：

- `CORE_RECOVERY_V3_PASS`；13/13 recovery 请求合法完成；
- Judge `enable_thinking=false`、`max_new_tokens=1296`、`strict_direct_json_v1`；
- behavior decoder `max_new_tokens=512`；
- 旧 F2、旧 recovery、v2.3 设计和配置保持只读。

负责人已授权继续准备 full rescore。该授权不允许本任务提前运行模型或 Judge。

## 必读输入

- `writing/broadening design/report/paper1_core_judge_protocol_v3_recovery_execution_report.md`
- `results/paper1_broadening/core-judge-protocol-v3-direct-json-recovery-20260918T130823Z-a1/`
- `.codex-temp/paper1_core_judge_protocol_v3/recovery_execution/`
- `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.3_direct_json.md`
- `configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json`
- 旧 F2：`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`
- `paper1_broadening/judge.py`、`paper1_broadening/pipeline.py`、`paper1_broadening/orchestration.py`
- 现有 recovery executor/launcher 及其测试。

旧 F2 中必须读取的只读文件为：

- `screen_generation_schedule_core.jsonl`
- `screen_generation_attempts_core.jsonl`
- `screen_generation_ledger_core.jsonl`
- `screen_judge_records_core.jsonl`（只用于确认旧状态和输入身份，不能读取旧 label 作为新结果）
- `frames.json`
- `resolved_config.json`
- `run_header.json`

## 不可违反的边界

1. 不修改、覆盖、合并、删除、重命名或回写旧 F2、旧 recovery、旧 Judge ledger、旧 dose decisions、v2.1 三份原设计、v2.3 设计或任何 canonical config。
2. 不修改数据集、safe-pair ledger、方向 tensor、层、family、rho、seed、rubric、parser 语义或 2% missing gate。
3. 新 full-rescore 只能消费旧 F2 已落地的 generation completion；不得重新生成 completion，不得从旧 Judge label 推导新 label。
4. 新 Judge 固定为 `enable_thinking=false`、`max_new_tokens=1296`、`strict_direct_json_v1`、float32、greedy、one beam、local-files-only、GPU 0。behavior decoder 的 512 只作为旧 completion 的身份约束，不得用于新 Judge。
5. 不使用 binary Judge；不进行 generation retry。每个 logical identity 的 four-class Judge 最多一次首次请求加一次既定技术/解析重试，实际调用数必须单独记录，禁止无限 retry、并发或 resume 造成重复请求。
6. 1,200 是 logical identity 数量，不是允许新增的 generation 数量。所有 1,200 条都必须有 terminal accounting；缺失、技术失败和合法 `broken` 必须分开记录。
7. 本任务不执行 full rescore、Core formal evaluation、E1/E2/E3、analysis、human audit 或最终归档。
8. 不执行 `reset`、`checkout`、`pull`、清理他人文件或修改已有工作树差异。实现需要改变科学规则时写 `DESIGN_CHANGE_REQUIRED` 并停止。

## 证据目录的历史残留处理

上一次 approval 阻断和本次成功 recovery 复用了同一个 evidence 目录。目录中无前缀的 `preflight.status` 与 `call_counts.json` 是旧阻断尝试的历史文件；本次成功证据以 recovery run、`execution_preflight_checks.json`、`execution_preflight.status`、`call_counts.jsonl`、`final_boundary_audit.json`、`record_integrity.json` 和 run 内 `artifact_hashes.sha256` 为准。

不得删除或改写这些历史文件。准备阶段必须建立新的只读 handoff 清单，例如：

`.codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness/recovery_handoff_manifest.json`

清单只记录本次成功 recovery run 和 canonical 新证据的路径、SHA256、13 条记录数、13 个 raw/diagnostics、`run_artifact_verification=0` 和 `CORE_RECOVERY_V3_PASS`；同时明确列出旧残留文件及其 `HISTORICAL_STALE` 状态。不得把旧残留文件复制到新的正式 run。

## 阶段 0：只读输入绑定和 handoff（不加载模型）

使用 Linux 字节核对：

- recovery report 为 `CORE_RECOVERY_V3_PASS`；
- recovery run 的 8 个正式 artifact hash 全部通过；
- records=13、ordinals=1..13、状态均为 `PARSED`、raw/diagnostics 各 13；
- actual four-class=13、binary=0、generation retry=0、additional retry=0；
- old F2/old recovery/design protection exit 均为 0；
- 旧 F2 的 generation schedule/attempts/ledger 能绑定恰好 1,200 个 logical identity，response id 唯一，completion hash 可复核；
- 20 个 screen cell（2 model × 2 family × 5 rho）各有 60 条 schedule identity；
- 旧 Judge label 不会被写入新 full-rescore 输入或结果。

将所有检查、输入计数、保护 hash、handoff 清单和 git pre-existing diff 写入：

`.codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness/`

若任一输入绑定失败，只写 `FULL_RESCORE_READINESS_BLOCKED`，不修改共享代码，不加载模型。

## 阶段 1：实现独立 full-rescore executor/launcher（仍不加载模型）

新增独立脚本，建议名称：

- `scripts/core_judge_full_rescore_executor.py`
- `scripts/core_judge_full_rescore_run.py`

可新增最小测试文件：

- `tests/paper1_broadening/test_full_rescore_executor.py`
- `tests/paper1_broadening/test_full_rescore_launcher.py`

实现要求：

1. 模型构造必须发生在 approval/输入/配置/保护哈希预检之后；本任务的 fixture 路径不得导入 torch/transformers。
2. 为新 run 生成完整 request manifest，固定 1,200 条 ordinal、logical identity、旧 completion hash、prompt hash、request hash、cell、domain 和 source line。
3. 每个 identity 只消费旧 generation completion；不得读取旧 Judge label。request manifest、attempt records、raw、diagnostics、stop reason、token count、parser status、retry count 和调用计数必须持久化。
4. direct JSON parser 必须严格要求恰好 `label` 与 `rationale` 两个键、合法 domain label、非空 rationale；禁止 regex、substring、legacy fallback、手工标签和 completion-derived label。
5. 技术/解析重试最多一次且与首次调用分开记账；任何 identity 超过上限、身份不匹配、证据缺失或未知错误都必须停止并保留已完成结果。
6. 新 run 使用独立目录，例如 `results/paper1_broadening/core-screen-v3-direct-json-full-rescore-<UTC>-<shortid>/`，不得写入旧 F2 或 recovery 目录。
7. CPU gate 计算只使用新 run 的新 Judge 结果：20 个 cell 各 60 条，missing 门槛保持每 cell 不超过 2%（60 条中最多 1 条）。不得用 recovery 13 条标签填补 full-rescore 结果。
8. 只有所有 cell 通过时，才在新目录生成新的 dose decision 文件并标记 `CORE_SCREEN_V3_PASS`、`CORE_A_S_READY_FOR_FORMAL_EVALUATION`；任一 cell 超过门槛则写 `CORE_SCREEN_V3_BLOCKED`，不选择 A/S。
9. executor/launcher 必须支持预检模式；本任务只能运行预检或 fixture backend，不能以默认参数触发真实模型。

## 阶段 2：离线验证（必须使用 nohup；仍不加载模型）

在服务器执行：

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp" TMP="$TMPDIR" TEMP="$TMPDIR"
export PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
```

每个命令都要使用 `nohup` 保存 PID、日志和 `.exit`，并在进入下一步前读取退出码和业务 JSON。至少完成：

- Python compile；
- focused full-rescore executor/launcher fixtures；
- 完整 `tests/paper1_broadening`；
- shell syntax check（若新增 shell launcher）；
- `git diff --check`；
- handoff manifest 和 1,200 identity/20-cell CPU binding check。

离线测试必须证明：

- 默认不会加载模型或发送 Judge；
- approval/输入哈希/旧文件保护失败时 fail-closed；
- fixture 可覆盖 1200 identity、技术重试一次、missing、重复 identity、旧 label 污染和 2% gate；
- full-rescore logical budget 与 actual Judge calls 分开；
- 新 run 与旧 F2/recovery 路径隔离。

## 交付、报告和停止条件

保存报告：

`writing/broadening design/report/paper1_core_judge_protocol_v3_full_rescore_readiness_report.md`

报告必须包含：

- `FULL_RESCORE_IMPLEMENTATION_READY` 或 `FULL_RESCORE_READINESS_BLOCKED`；
- `CORE_RECOVERY_V3_PASS`（引用，不重复计数）；
- `CORE_SCREEN_V3_NOT_RUN`、`FORMAL_EVALUATION_NOT_RUN`；
- 新增和修改文件列表及 SHA256；
- 旧 F2、旧 recovery、三份原设计、v2.3 design/config 的保护结果；
- 1,200 identity、20 cells、每 cell 60 条的 CPU 绑定结果；
- 测试/Python compile/shell syntax/git diff 的 PID、日志、`.exit`；
- 证据目录和 handoff manifest 路径；
- 明确说明旧残留 evidence 文件未被删除且不参与本次成功判断；
- 最终边界自审结果。

完成后停止。不要执行真实 full rescore，不要运行 Core screen、A/S 选择、formal evaluation、E1/E2/E3、analysis 或人工审核。报告之外，必须列出所有新增/修改的源码、测试、配置和脚本路径，便于负责人同步；不得声称代码已推送，除非确实执行并记录了 commit/push。
