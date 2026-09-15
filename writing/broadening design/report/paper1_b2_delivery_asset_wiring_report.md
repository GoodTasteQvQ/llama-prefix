# Paper 1 B2 实现交付与资产接线报告

任务书版本：`b2-delivery-asset-wiring-v2`  
报告日期：2026-09-15（Asia/Shanghai）  
工作目录：`/data/goodtaste_workspace/llama-prefix`  
分支：`stage3/impl-candidate`  
当前 HEAD：`a12d204765a6c6177d6638d1103fdfe7f9b414ab`  
工作树：dirty（保留既有用户修改；未 commit、未 push）

状态：**B2_DELIVERY_READY**

`B2_DELIVERY_READY` 只表示 core 契约、public 入口、执行版本和测试证据已经可定位并且共享代码写入已停止。它不表示 E1 overlap gate、E2 runtime gate 或 safe-pair construction gate 通过。

## 1. 范围和历史记录

本次补齐 B2 实际交付和 E1/E2 必要接线。没有重新开发实验系统，没有运行 `prepare`、`smoke`、模型加载、Gemma 探针或任何正式实验；没有修改实验参数、旧 source、旧 ledger、旧 raw、旧 run 或 canonical legacy config。

原 B2 修复报告已经找到，路径为：

`writing/broadening design/report/paper1_implementation_contract_repair_report.md`

该报告记录了 `broadening-contract-repair-v2`（2026-09-08 UTC）的实际修复和 43 passed 证据。本报告没有把它改写成新的历史记录；本次只补充当前执行版本的交付、资产接线和最终复核。

## 2. 实际差异和交付文件

相对于当前基线 HEAD `a12d204...`，共享工作树的 tracked dirty patch 为：

| 文件 | 实际差异 | 作用 |
|---|---:|---|
| `paper1_broadening/config.py` | 24 additions / 2 deletions | 保留 legacy revision；增加 public revision、路径绑定和 public Gemma layer 校验 |
| `paper1_broadening/frames.py` | 54 additions / 4 deletions | raw provenance、evaluation digest、mixed-digest fail-closed、CSV adapter 强制 |
| `paper1_broadening/orchestration.py` | 28 additions / 4 deletions | public/E1/source/ledger 快照清单；run header 使用实际 config revision |
| `tests/paper1_broadening/test_frames_directions.py` | 47 additions / 1 deletion | 为 raw 绑定和 public revision 补齐 fixture/回归覆盖 |
| `writing/broadening design/report/paper1_source_manifest_lf_canonical.json` | 8 additions | LF-canonical 修复候选；明确 `CANDIDATE_NOT_ADOPTED` |
| `writing/broadening design/report/paper1_source_manifest_lf_canonical.patch` | 12 additions | 候选 manifest 的可审阅 patch |

必要的新增 B2/core 文件：

- `configs/paper1_broadening/mbd_nm_v211_public.json`
- `tests/paper1_broadening/test_contract_repair.py`
- `writing/broadening design/report/paper1_implementation_contract_repair_report.md`

本次 B3 资产接线新增/保留：

- public source：`data/safe_pairs_public_semantic_v1.json`（416 rows）；A2 rebuilt ledger 绑定到 `writing/broadening design/report/evidence/paper1_a2_b2_delivery/a2/public_pair_quality_decisions.v2.rebuilt.json`
- E1 adapter：`scripts/adapt_harmbench_e1.py`
- E1 raw/derived files：`data/external/harmbench/` 下的 LICENSE、all CSV/metadata、standard CSV、standard JSON 和 standard metadata
- E2/public asset template：`configs/paper1_broadening/mbd_nm_v211_public_assets.json`
- A2/B2 运行依赖副本：`scripts/integrate_public_safe_pairs.py`、`scripts/rebuild_public_safe_pair_ledger_v2.py`、`scripts/retry_public_safe_pair_request.py`、`scripts/review_public_safe_pairs_v2.py` 及 A2 evidence
- review/source 证据：`writing/broadening design/review/paper1_public_safe_pair_review_protocol_revision.md`、`data/external/semantic_harmful_harmless_v1/` 及 LF-canonical 候选

可恢复的最终相关代码、配置、source、A2 ledger 引用、测试源码和 nohup 证据已复制到：

`writing/broadening design/report/evidence/paper1_a2_b2_delivery/b2/`

该目录的 `file_manifest.sha256` 是项目相对路径清单；`checks_manifest.sha256` 单独覆盖检查的 `.pid/.log/.exit` 和检查源码。`delivery_state.json` 已与最终快照校正为 `source_files: 42`、`design_files: 13`，并记录 base commit、branch、dirty 状态。

## 3. Core 实现契约核对

### Raw 绑定和 revision 兼容

`paper1_broadening/frames.py::_semantic_status` 在 dual Codex provenance 模式下要求完整的 reviewer provenance，并解析 A/B 两份 raw JSON。每一侧 raw 的 `pair_id`、`prompt_revision`、`verdict` 必须分别等于当前 pair、外层 revision 和对应 reviewer verdict；非法 JSON、缺字段、相同 agent id 或不一致均返回 `PENDING_SEMANTIC_REVIEW`。unanimous include 才能得到 `SEMANTIC_INCLUDE`，其他组合不会被静默提升。

接受的 review prompt revision 保留：

- `safe-pair-semantic-overlap-v1`（旧兼容）
- `public-semantic-pair-quality-v1`（public 规定版本）
- `public-semantic-pair-quality-v2`（现有 rebuilt ledger 使用的实际版本）

本次没有重做 A2 的 agent 身份审计；只用当前集中校验验证 rebuilt ledger 能通过 raw/digest/status 检查。

### Evaluation digest

`build_frames` 对实际的 `{"jbb100": ..., "jbb40": ..., "benign30": ...}` 计算仓库既有 canonical JSON SHA-256，并把 digest 传入 safe-pair split。每条 dual-review decision 必须匹配该 digest；不同 decision digest 会设置 `mixed_evaluation_frame_digest=true`，并把 gate 置为非 executable 的 `PENDING_SEMANTIC_REVIEW`。

最终 contract/asset check 复核的 digest 为：

`db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`

409 条 rebuilt ledger records 的状态只有 `SEMANTIC_INCLUDE` 和 `SEMANTIC_EXCLUDE`，且 digest 单一一致。

### Config loader、canonical legacy 和 public 入口

- `default_config()`、`configs/paper1_broadening/mbd_nm_v21.json` 和 CLI 默认入口 `scripts/paper1_broadening.py` 仍指向 legacy `data/safe_pairs.json`。
- `validate_config()` 对 legacy `v2.1-ccf-a-target` 强制要求 `data/safe_pairs.json`；对 public `v2.1.1-public-pairs` 强制要求 `data/safe_pairs_public_semantic_v1.json` 和非空 `overlap_decisions_path`。
- `configs/paper1_broadening/mbd_nm_v211_public.json` 是不带 E1/E2 资产的严格 public 入口。
- `configs/paper1_broadening/mbd_nm_v211_public_assets.json` 在相同 `v2.1.1-public-pairs` 和 `linux-single-gpu-v1` 下显式接入 E1/E2；logical generation budget 仍为 `20_480`，core 参数未改变。

legacy 和两个 public config 均由最终测试实际 `load_config()` 成功加载；没有 fallback 到 AI source，也没有改写旧 canonical config。

### Snapshot 和 design revision

`paper1_broadening/orchestration.py` 当前清单包含 42 个 source snapshot 路径和 13 个 design snapshot 路径。source 清单覆盖 core modules、legacy/public/asset config、public source、实际 A2 ledger、E1 raw/derived assets、source manifest、adapter 和审核脚本；design 清单覆盖设计、实现/审核任务书、当前 B2 任务书和 LF-canonical 候选。当前 checkout 中不存在的旧 prompt 路径已不再列入。

`create_run()` 将 `config["design_revision"]` 写入 run header，而不是固定写 legacy revision；同时记录 source/design snapshot 目录和 dirty code state。最终静态检查确认清单中的 42/13 路径全部存在。

## 4. A2 结果复用和版本区别

A2 真实请求/独立性专项核验直接复用 `paper1_a2_evidence_handoff_report.md` 及其最终 rebuilt 文件，不重复核验 agent 身份。可复用的结果是：source 416、exact overlap 7、preliminary eligible 409、A/B requests 818、final ledger 409（221 include、188 exclude、0 pending）；`actual_k=24`，小于 `min_fold_size=30`，因此 construction gate 仍为：

`BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`

A2 prepare 小文件与 B2 最终交付版本明确区分：

| 项目 | A2 prepare 快照 | B2 最终版本 |
|---|---|---|
| run / code | `public-semantic-pairs-v2-20260914T122608Z`，code commit `af84213...`，dirty | 交付 base/HEAD `a12d204...`，dirty patch 已随代码副本交付 |
| snapshot | 旧 prepare header 记录 29 source / 9 design 文件 | 当前 orchestration 清单为 42 source / 13 design，含 B2 任务、E1/E2 资产和实际 ledger |
| E1/E2 | E1 `NOT_RUN`（资产缺失），Gemma path/layer 为 null | E1 JSON/metadata 已接线；Gemma path 和 layer 14 已写入 asset config |
| ledger/config | 使用当时 `.codex-temp/.../public_pair_quality_decisions.v2.rebuilt.json` 的 resolved config | public config 使用交付目录内 A2 rebuilt ledger 路径；未重新 prepare |
| gate | `actual_k=24`、`BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS` | 仍是同一 safe-pair gate；B2 没有把它改成 PASS |

## 5. E1/E2 接线状态

### E1 HarmBench

已核对 revision `c0423b952435fcc8467108d8f25962dbae5b7de2` 的 all CSV 400 行，其中严格按 `FunctionalCategory == standard` 派生 200 行。adapter 保留 all CSV 的 0-based data-row `source_index`，并进行如下确定性映射：`Behavior -> text`、`SemanticCategory -> category`、`BehaviorID -> source_id`。物化 JSON 的 metadata benchmark 为 `HarmBench_standard_text`，原始 CSV、metadata 和 LICENSE 未修改。

`_load_e1` 现在拒绝直接读取 CSV，要求先使用 adapter 生成 JSON；asset config 指向 `harmbench_behaviors_text_standard.json` 和对应 metadata。200 条 E1 候选可读，状态是 **`READY_FOR_OVERLAP_GATE`**。

本次没有执行 E1 semantic overlap review，也没有选择最终 40 条；因此 E1 不是正式运行 gate 通过。

### E2 Gemma

复用既有 D 报告的本地资产证据，不重新下载、加载或探针。Gemma model/tokenizer 路径均为：

`/data/goodtaste_workspace/models/gemma-2-9b-it`

既有资产报告确认文件完整，模型 `L=42`，设计解析层为 zero-based `14`；`mbd_nm_v211_public_assets.json` 已显式填写该路径和 layer 14。既有 D 证据为 `RUNTIME_PROBE_PASS`，但本次只做文件/config 接线核对；E2 在本任务仍标记 **`READY_FOR_RUNTIME_CHECK` / E2_FORMAL_EXPERIMENT_NOT_RUN**。资产可读不等于 E2 runtime/dose 或正式实验 gate 通过。

### LF-canonical source manifest

`paper1_source_manifest_lf_canonical.json` 和 `.patch` 记录 UTF-8/LF、无文本或字段规范化的修复候选，保留原 manifest hash、原声明 LICENSE hash 和实际 LF LICENSE hash。候选状态明确为 `CANDIDATE_NOT_ADOPTED`；原 `data/external/.../source/source_manifest.json` 和 source 内容未覆盖。

## 6. 离线验证证据

以下最终证据均已通过项目临时目录规则以 nohup 运行，并保留在 `writing/broadening design/report/evidence/paper1_a2_b2_delivery/b2/checks/`（同名 `.pid`、`.log`、`.exit`）。`.pid` 内容是 nohup worker PID；文件名中的数字是启动 shell tag。

| 检查 | worker PID | 日志 / exit | 实际结果 |
|---|---:|---|---|
| HarmBench CSV→JSON materialize | 1053316 | `b3-harmbench-adapter-20260914T142327Z-1053312-26327.{log,exit}` | exit `0`；200 records |
| adapter 定向测试 | 1058118 | `b3-adapter-tests-20260914T144924Z-1058114-22989.{log,exit}` | `5 passed`，exit `0` |
| Python compile | 1068628 | `b3-python-compile-final-20260914T154249Z-1068624-22868.{log,exit}` | exit `0` |
| `bash -n` | 1068635 | `b3-bash-n-final-20260914T154249Z-1068630-29979.{log,exit}` | exit `0` |
| final static/contract prerequisites | 1068480 | `b3-final-static-check-20260914T154151Z-1068476-25097.{log,exit}` | `STATIC_CHECK_PASS`，含 `git diff --check` |
| contract + asset check | 1069505 | `b3-contract-asset-check-final3-20260914T154713Z-1069501-30230.{log,exit}` | `PASS`；source 42、design 13、E1 200、ledger 409、digest 单一 |
| `tests/paper1_broadening` | 1069512 | `b3-broadening-tests-final3-20260914T154713Z-1069507-24550.{log,exit}` | `45 passed in 9.37s`，exit `0` |
| final delivery self-check | PID recorded in `b3-delivery-final-self-check-final-20260915.pid` | `b3-delivery-final-self-check-final-20260915.{log,exit}` | `PASS`；manifest 43、报告副本一致、无 B2/prepare/Gemma 进程 |

此前一次 contract check 因调用环境缺少 `PYTHONPATH` 退出 `1`；没有被计为通过，修正环境后以上 `final3` 记录 exit `0` 才是最终证据。delivery materialize 早于 `delivery_state.json` 元数据校正，exit 为 `0`；校正后的状态和最终代码哈希已重新纳入交付清单。

## 7. 建议补丁、剩余阻塞和边界自审

本任务范围内没有需要继续修改 core 的问题，故没有在 `.codex-temp` 另造未应用补丁。后续建议是：

1. E 阶段先对 200 条 HarmBench standard 候选执行独立 overlap review，再决定 40 条；不要把 `READY_FOR_OVERLAP_GATE` 当作 E1 PASS。
2. 负责人补足至少 29 条新的 executable safe pairs，使 `actual_k` 达到 30 后再进入 construction；不得从旧无效 ledger 静默凑数。
3. 在单独授权的 E2 runtime gate 中复用已接线 Gemma 路径/layer；不要因本次配置接线重复下载或探针。
4. LF manifest 候选由负责人审核后再决定是否采用；本次不改原 source manifest。

边界自审确认：

- 未运行 `prepare`、`smoke`、模型实验或正式实验；没有加载模型。
- 未修改实验科学参数、20,480 logical budget、旧 source/ledger/raw/run 或 legacy canonical config。
- A2 818 请求/独立性结论仅作证据复用，没有重复 agent 身份审计。
- E1/E2 状态分别记录，未写成正式 gate 通过。
- 交付副本、文件清单、检查清单和 hash 均可定位；代码写入已停止，供 E 接手。
- 没有 commit/push，也没有终止无关后台进程；当前无 B2/prepare/model 任务仍在运行。

剩余硬阻塞为 `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`；E1 overlap、E2 runtime/dose 和正式实验均未完成。

**FORMAL_EXPERIMENTS_NOT_RUN**
