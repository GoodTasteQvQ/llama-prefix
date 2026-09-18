# Core Judge protocol v3: approved-launcher readiness and evidence refresh

执行会话：`A-core-recovery-v3-launcher-readiness`
协议：`core-judge-protocol-v3-direct-json`
工作目录：`/data/goodtaste_workspace/llama-prefix`

## 任务目的与硬停止边界

上一阶段已补齐 bounded executor，并通过了 9 条 fixture 测试，但该模块的
`main()` 仍明确拒绝生产运行，真实 Qwen3 backend/launcher 尚未交付；同时 readiness
artifact manifest 必须在最终服务器源码和测试文件上重新生成。本任务只补齐并审计
一个受 approval gate 保护的生产 launcher，刷新完整证据，仍不执行 recovery。

本任务中模型加载、Judge 请求、binary Judge、generation、retry、recovery、full
rescore、Core screen、A/S 选择、正式 evaluation、E1/E2/E3、分析和人工审核必须
全部为 0。不得创建或猜测 recovery approval；即使服务器上残留 approval，也必须
把它视为阻断并停止，等待负责人重新审查。

旧 F2、旧 recovery、R2 probe、v2.1/v2.3 设计、canonical config、safe-pair
source/ledger、方向资产和历史结果只读。不得修改原实验设计或通用旧 runner。

## 1. 输入与同步核验

只读读取：

- `writing/broadening design/report/paper1_core_judge_protocol_v3_recovery_executor_readiness_report.md`
- `scripts/core_judge_recovery_executor.py`
- `tests/paper1_broadening/test_recovery_executor.py`
- `.codex-temp/paper1_core_judge_protocol_v3/recovery_executor_readiness/` 全部证据；
- proposal 的 13-row manifest、`final_boundary_audit.json` 和保护哈希；
- v2.3 direct-JSON design/config。

先在 Linux 服务器上按字节核验：

1. readiness `executor_source_snapshot.py` 与当前 executor 源码完全一致；
2. 测试文件实际存在，artifact hash manifest 中的每一项都存在且 SHA256 匹配；
3. 不把 Windows CRLF 转换后的本机副本当成服务器 canonical hash；
4. 旧 F2、旧 recovery、设计、config、R2、proposal evidence 的保护哈希不变。

若上述任一项失败，先刷新 readiness 证据或写
`LAUNCHER_READINESS_BLOCKED_EVIDENCE_SYNC`，不得创建 approval、加载模型或发请求。

## 2. 允许的最小实现范围

审计 `scripts/core_judge_recovery_executor.py`。如果已有等价 launcher，只需修正
契约并测试；否则新增一个独立 CLI（可命名为
`scripts/core_judge_recovery_run.py`），不得把特殊 recovery 逻辑并入旧
`run_real_judge`、screen 或 evaluation 路径。

允许修改的文件仅限：

- bounded recovery executor；
- 独立 recovery launcher/backend adapter；
- 对应离线 fixture 测试；
- 本阶段报告和证据脚本。

### 必须闭合的契约

1. canonical approval 路径保持：
   `.codex-temp/paper1_core_judge_protocol_v3/CORE_JUDGE_PROTOCOL_V3_RECOVERY_APPROVAL.md`。
   为避免扩展名歧义，该文件在代码中必须被明确定义为“完整 JSON object（不得有
   Markdown 包装）”，并校验 `status=APPROVED`、proposal/manifest/design/config
   SHA256、当前 executor/launcher code hash、13/1 请求预算、binary/retry=0 和
   direct-JSON 参数。生产路径只能从该 canonical 文件读取；不能用内存 approval
   绕过文件。内存注入仅允许在 fixture 测试中使用，且不得构造真实 backend。
2. preflight 必须在 import/construct/load 真实模型前完成；缺失或不匹配时只写
   fail-closed 证据，实际请求和模型加载均为 0。
3. launcher 必须用 v2.3 config 构造真实 Qwen3 Judge backend，并从旧 F2 受保护的
   prompt/completion/source line 读取每一条输入；不得重新生成 completion，不得
   从新数据集取代 13 条旧输入。真实 backend 必须使用：
   `enable_thinking=false`、`max_new_tokens=1296`、`strict_direct_json_v1`、
   float32、greedy、one beam、local-files-only、GPU 0；behavior decoder 512
   仅作为配置核验项。
4. executor 的 backend 返回值必须强制包含并精确匹配当前 request identity、
   `actual_call_counts={"binary":0,"four_class":1}`、`generation_retries=0`、
   `additional_judge_retries=0`、raw 和 diagnostics。不能把缺失字段当作通过。
5. 每条输入最多一次 four-class 请求，按 1..13 顺序串行处理；任一异常、非法
   JSON、身份不符、raw/diagnostics 缺失、OOM 或 timeout 立即停止，不处理下一条，
   不重试、不 resume、不调用 binary、不使用 regex/substring/legacy fallback。
6. 正式 launcher 只能接收一个全新的、此前不存在的 run directory；必须写入
   preflight、run manifest、每条 request/response/raw/diagnostics/hash、调用计数、
   release/runtime identity、artifact hash 和最终 boundary audit。不得覆盖、合并
   或回写旧 F2/旧 recovery。
7. launcher 的 CLI 可被 `nohup` 调用，但在本任务没有 approval 时只能以
   `RECOVERY_APPROVAL_BLOCKED` 退出，不能加载模型。

## 3. 零请求离线验证

```bash
cd /data/goodtaste_workspace/llama-prefix
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export CUDA_VISIBLE_DEVICES=0
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

所有测试和证据脚本使用实验室 Python，并用 `nohup` 保存 PID、log、`.exit`。只准
使用 CPU/标准库 fixture；不得载入 Qwen3、不得访问 Hugging Face、不得创建真实
approval。至少验证：

- canonical approval 是 JSON object，缺失/错误/内存绕过均 fail-closed；
- launcher 在 approval 校验前不 import/construct/load 真实模型；
- direct JSON false/1296/parser 与 decoder 512；
- 13 行顺序、旧 F2 source/hash 对应性和新 run 目录约束；
- 缺失 request identity/count/raw/diagnostics 会阻断；
- 单条失败不 retry、不处理下一条、不调用 binary；
- fixture 结果的 raw/diagnostics/event/hash 持久化；
- 旧 F2、旧 recovery、设计、config 和 proposal protection hash 未变。

## 4. 交付与状态

证据目录：`.codex-temp/paper1_core_judge_protocol_v3/recovery_launcher_readiness/`。
保存最终服务器源码/测试 snapshot、同步核验、测试 PID/log/.exit、resolved
runtime identity、code/config/design/proposal hash、artifact manifest 和 boundary
audit。

保存报告：
`writing/broadening design/report/paper1_core_judge_protocol_v3_recovery_launcher_readiness_report.md`

通过时必须写入：
`RECOVERY_LAUNCHER_READY`、`RECOVERY_APPROVAL_REQUIRED`、
`CORE_RECOVERY_V3_NOT_RUN`、`FULL_RESCORE_NOT_RUN`、`FORMAL_EVALUATION_NOT_RUN`，
并列出最终 launcher/executor code hash。失败时写
`LAUNCHER_READINESS_BLOCKED_EVIDENCE_SYNC` 或 `RECOVERY_IMPLEMENTATION_BLOCKED`。

任务完成后停止，不创建 approval，不执行 recovery，不 commit/push。只有负责人审查
本报告和新的 artifact manifest 后，才进入独立 recovery approval 阶段。
