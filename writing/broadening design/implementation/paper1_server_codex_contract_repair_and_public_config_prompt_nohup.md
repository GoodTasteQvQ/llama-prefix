# Broadening 实现契约修复与 public config 任务书

版本：`broadening-contract-repair-v2`
前置报告：`paper1_implementation_contract_audit_report.md`、`paper1_safe_pair_review_quality_audit_report.md`
执行者：实验室 Linux 服务器 Codex
性质：最小代码/配置修复；不运行正式实验

## 1. 当前阻塞

既有审核生成器并没有调用 Codex subagent，而是用 regex/semantic-score 启发式合成 verdict；旧
ledger 声称的 `dual_codex_subagents_v1` provenance 不成立。因此旧 194 条只能保留为无效历史
证据，不能用于 construction gate。B 审计还确认：raw JSON 没有被代码绑定校验，跨记录 frame
digest 没有 fail-closed 检查，canonical config 仍指向旧 AI source，source snapshot 引用已删除
的任务文件，离线测试为 `38 passed, 2 failed`。

本任务只修复实现契约，使后续真实审核可以被正确记录。不得修改旧 ledger 以“修正”194 条。

## 2. 执行边界

- 不运行 directions、screen、generation、Judge、analysis、human packet 或 prepare；
- 不使用或覆盖 `data/safe_pairs.json`、旧 public source、旧 run、旧 ledger；
- 不改变模型、层、hook、chat template、decoder、rho、seed、fold、预算或 pair 判定标准；
- 不把启发式脚本改名为 subagent，也不接受 regex/semantic-score 作为审核替代；
- 保留旧 revision `safe-pair-semantic-overlap-v1` 与已存在的 public revision 兼容路径；
- 允许使用新的 provenance revision `public-semantic-pair-quality-v2`，但它必须表示同一科学
  判定标准的证据/实现修订，不得偷偷改变 include 条件；
- 本任务默认不 commit/push，保存实际 diff 和报告供负责人审核；不得 reset、清理或覆盖用户修改。

## 3. Linux 与 nohup

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export NX_DAEMON=false
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export PYTHONUNBUFFERED=1
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
```

所有 pytest、静态检查和契约脚本通过 `nohup`，记录 PID、日志和 `.exit`，串行等待并核对退出码。

## 4. 必须完成的最小修复

### 4.1 Raw provenance fail-closed

在 `_semantic_status` 或等价的集中 gate 中解析 `reviewer_a_raw_output`、`reviewer_b_raw_output`
为 JSON 对象，并要求每一份 raw 的 `pair_id`、`prompt_revision`、`verdict` 分别等于外层
ledger 的 pair id、review revision 和对应 reviewer 字段。raw 非法、字段缺失、pair/revision/
verdict 不一致时返回 pending/blocked，不返回 `SEMANTIC_INCLUDE`。

保留旧 revision 的已有验证；对 `public-semantic-pair-quality-v2` 使用同等严格校验。不得只
检查 raw 字符串非空。

### 4.2 Evaluation digest 一致性

在 prepare/build split 时拒绝混用多个 `evaluation_frame_digest`。digest 算法必须复用仓库已有
canonical JSON/SHA256 工具，并在代码、测试和报告中明确算法版本；不要临时引入 Python
`hash()` 或未排序字符串。digest 应由 prepare 对实际 JBB100/JBB40/benign30 frame 计算，并与
每条决定的 digest 比对；无法匹配时保持 pending/blocked。

### 4.3 Versioned public config

保留旧 `configs/paper1_broadening/mbd_nm_v21.json` 不变，新增一个版本化 public config（例如
`configs/paper1_broadening/mbd_nm_v211_public.json`），至少明确：

- design revision：`v2.1.1-public-pairs` 或已登记的等价 revision；
- safe-pair path：`data/safe_pairs_public_semantic_v1.json`；
- review ledger path：只接受本次 run 的绝对/项目相对路径；
- 其他科学字段与旧设计完全一致。

更新 loader，使旧 config 仍按旧 revision 正常加载，public config 可严格验证；不要通过把所有
revision 任意放开来绕过校验。新 config 不代表 gate 已通过，也不得用于正式 generation。

### 4.4 Snapshot contract

替换 `DESIGN_SNAPSHOT_PATHS` 中已删除的旧任务文件，只引用仓库中实际存在的科学设计、实现规范、
审阅文档和当前有效任务书。把 public source 输出、integration manifest、source manifest、
versioned config 和 review protocol metadata 纳入 source snapshot；不要复制模型权重、缓存或
整个 `.codex-temp`。

source snapshot 对缺失必需文件必须 fail closed；测试 fixture 必须能在当前 checkout 生成，不能
依赖服务器上未同步的未跟踪文件。

## 5. 测试与验收

新增或更新最小测试：

1. raw pair id、revision 或 verdict 被篡改时为 pending；
2. legacy/public/v2 revision 的合法记录仍可通过；
3. 重复 agent、非法 verdict、冲突 adjudication 仍被拒绝；
4. 混合 evaluation digest 不能进入 executable split；
5. versioned public config 能加载，旧 config 行为不变；
6. fixture/source snapshot 中所有路径存在且 source hash/identity 可追溯。

通过项目内临时目录运行 `tests/paper1_broadening`。如果仍失败，只修复本任务直接导致的契约
问题；不得删测试、放宽断言或运行 prepare。Python compile、shell syntax 和 `git diff --check`
也必须保存证据。

## 6. 报告与停止

保存：

`writing/broadening design/report/paper1_implementation_contract_repair_report.md`

报告必须包含修复前后文件、实际 diff、测试命令/PID/log/exit、测试计数、public config 路径、
snapshot 文件清单、旧 ledger 未修改证明和剩余阻塞。明确写入：
`FORMAL_EXPERIMENTS_NOT_RUN`、`SAFE_PAIR_REVIEW_NOT_RESTARTED`。

报告完成后停止，不启动 A 的新审核，不执行 source recovery。负责人审核该报告后再启动下一阶段。
