# Paper 1 B4 Post-Recovery Runtime Handoff

任务书版本：`post-recovery-runtime-handoff-v1`  
日期：2026-09-15（Asia/Shanghai）  
工作目录：`/data/goodtaste_workspace/llama-prefix`  
分支/HEAD：`stage3/impl-candidate` / `a62ff22d20a900e9a48262830847e9160ee68dc2`  
工作树：dirty；启动时既有修改和未跟踪交付物全部保留，未 commit、未 push。

## 状态结论

| 项目 | 结果 | 说明 |
|---|---|---|
| Code contract | **CODE_CONTRACT_PASS** | 当前 expanded config、source/ledger/manifest、raw identity、gate、E1 reference digest 和 live snapshot 清单通过 CPU 检查 |
| Core real smoke | **CORE_REAL_SMOKE_PASS** | 已复用真实工程 smoke；`NON_EVIDENCE`，不是论文结果或正式 gate |
| E1 consumer | **E1_CONSUMER_PENDING** | 当前 C2 reference 已稳定为700条，但旧 ledger/40条选择仍绑定另一 digest 且为 provisional，未消费 |
| Formal experiments | **FORMAL_EXPERIMENTS_NOT_RUN** | 未运行 prepare、directions、screen、generation、正式 Judge、analysis、Gemma 或人审 |

本次完整阅读了当前执行索引、post-recovery 任务书、safe-pair recovery 报告、任务表（实际路径为 `writing/broadening design/paper1_broadening_notion_task_table.md`）和 20260915 design immutability audit。A2 请求/独立性核验仅复用已有 handoff 证据，没有重新审计 agent 身份；没有改写 safe-pair source、safe-pair ledger、旧 raw、旧 run 或科学设计。

## 实际实现与差异

启动时 tracked dirty 文件为 `config.py`、`frames.py`、`orchestration.py`、`test_frames_directions.py` 以及 LF-canonical 候选；B2/B3 的 expanded 资产和测试为既有未跟踪交付。本报告不把这些既有变更伪装成新的历史记录，当前执行版本交付的是它们的实际内容，并在本轮只做了 E1 消费接口的最小修复：

- `paper1_broadening/config.py`：接受 legacy `v2.1-ccf-a-target`、public `v2.1.1-public-pairs` 和 expanded `v2.1.2-public-pairs-expanded`；legacy 仍强制 `data/safe_pairs.json`。expanded config 强制绑定 source、ledger、manifest 的路径、计数和 SHA-256；public Gemma asset template 固定 layer 14。
- `paper1_broadening/frames.py`：expanded 行只能通过 `review_pair_id` 找到审核记录；raw pair identity、两侧文本、source revision/index 和 input hash 不一致时 fail-closed。保留 evaluation digest 单一性检查和旧 safe-pair review revision 兼容。新增 E1 独立 reference/schema 校验；E1 默认 revision 改为 C2 实际的 `harmbench-e1-dual-codex-overlap-v1`，仍可由调用方显式消费旧 `paper1-e1-overlap-v1` fixture。E1 reference snapshot 排除 benign30，以匹配 C2 的真实范围。
- `paper1_broadening/orchestration.py`：run header 使用实际 config revision；live source snapshot 清单为47项、design snapshot 清单为16项，覆盖 expanded source/ledger/manifest、恢复脚本、HarmBench、授权来源 revision 和当前任务输入。
- `tests/paper1_broadening/test_contract_repair.py`：补充 E1 revision 兼容、700-reference digest/scope、C2 reference identity、expanded manifest 约束测试。原有 identity/raw/digest/CSV adapter 测试保留。
- `writing/broadening design/report/paper1_source_manifest_lf_canonical.json` 和 `.patch`：仍明确 `CANDIDATE_NOT_ADOPTED`；原 source manifest 未覆盖。

实际 expanded 资产哈希如下：source `d63fd3db8ddd721bd420484c4f4b05e52e39123bbf550e8802ab0af7674723a2`（516 rows）；ledger `20892484eaa65a5925b3f625338d5a97d2fd0477293956015cfa86ad5903c8db`（509 records，300 include/209 exclude/0 pending）；manifest `61995f6a5d068c1105ca6a86b2eb704305951224630e1580eff34cfcdbdfc31d`；expanded config `d15edaeeed1b9f19203ed8271606e4ac09c174c1206ac89955badeca1e8fe720`。

## Core 契约核对

- Safe-pair split 为 source=516、preliminary=509、executable=300、`actual_k=40`、5 folds=`[40,40,40,40,40]`、development=100、unused=0、construction/development disjoint，gate=`READY_FOR_CONSTRUCTION`。
- Safe-pair evaluation digest 为 `db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`，当前所有 expanded decisions 使用同一 digest。不同 digest、伪造 internal alias、重复 `review_pair_id`、raw 文本篡改或 input hash 不匹配均不能进入 executable split。
- `default_config()`、legacy config 和 CLI 默认入口仍指向 `data/safe_pairs.json`；public v1 和 expanded v2.1.2 使用各自显式 source/ledger。没有 AI-source fallback。
- 恢复脚本已保存 append-only source、batch freeze/hash、source revision 和 license provenance；当前 source 最后100行保留 `turkish-over-refusal-set:*` 与 `review_pair_id` 一一绑定。恢复产物是既有证据，本轮没有重跑 recovery prepare。
- 既有 recovery run header 记录 source snapshot 47、design snapshot 15，生成时的 code commit 为 `9f39921...` 且 dirty；当前 live orchestration 清单为47/16，新增当前 post-recovery task 输入。由于任务明确禁止重跑 prepare，这个历史快照没有被伪造为当前运行快照；live 清单的所有路径已在当前契约检查中逐项存在。
- 原实验设计正文、易读版、实现规范和已批准 `paper1_public_safe_pair_source_expansion_revision.md` 未修改；未触发 `DESIGN_CHANGE_REQUIRED`。

## E1/E2 资产与 C2 消费

HarmBench 已接线为固定 revision `c0423b952435fcc8467108d8f25962dbae5b7de2`：all CSV 400 行，严格由 `FunctionalCategory == standard` 得到 200 条 JSON；source index、BehaviorID、SemanticCategory 和文本保持原值。`_load_e1` 拒绝直接读 CSV，要求先使用 deterministic adapter。E1 资产本身为 `READY_FOR_OVERLAP_GATE`，不等于 E1 正式 gate。

Gemma asset config 已固定本地 model/tokenizer `/data/goodtaste_workspace/models/gemma-2-9b-it`、layer 14；本轮只核对接线，未加载或重复探针。E2 仍不是正式 runtime/dose gate。

当前 `.codex-temp/paper1_e1_final_overlap/reference_snapshot.json` 为 `C2_FINAL_SAFE_SOURCE_ROLE_SNAPSHOT`，范围是 JBB100 + 实际 300 construction/development safe pairs 的600个 role reference，共700条，digest=`d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`；benign30 明确不在该 E1 forbidden reference 集合。`review_input_manifest.json` 仍写明 reviewer results not present，near-match queue 为17。

现有 `e1_overlap_ledger.json`、`near_match_review_ledger.json`、`harmbench40_selection.json` 和 `review_identity_manifest.json` 仍绑定旧 digest `8be3f0b5ba135f7f8b0bcf09e8005612f4536b25f1fde8e355036203f5f8253a`；selection 虽有40条，但状态是 provisional，不能消费。当前 CPU consumer 输出为：candidate=200、reference=700、near queue=17、selected=0、`E1_SEMANTIC_OVERLAP_REVIEW_PENDING`。这只是 E1 overlap 的独立消费者状态，不是 safe-pair 审核意见，也不是 human 结果。

因此 E1 是 **PENDING** 而不是 BLOCKED：待 C2 在同一个 `d148...732a` 下补齐两侧语义结果并重建 ledger、identity manifest 和40条选择后，仅需用当前 consumer 做一次 CPU 复核；本轮不重审、不修改 C2 文件。

## Core smoke 证据

复用 `.codex-temp/paper1_broadening_smoke-final/smoke_report.json`：顶层 `PASS`、`evidence_status=NON_EVIDENCE`，两个非 evaluation benign prompt，24 次 generation 和4次 four-class Judge。报告核验了 clean/zero-alpha token IDs 相等、public_v1/decode_only 的 prefill/decode_cached trace、decode-only 非零注入、rogue/contrastive 两类向量、有限层和 no silent no-cache fallback，以及行为模型释放后才加载 Judge；Qwen/Llama 不并存，Gemma/HarmBench 未加载。该 smoke 只证明工程 runtime 路径，不构造正式方向、不提供 unsafe 论文证据。

## 离线验证

所有本轮检查使用项目内 `.codex-temp`，通过 nohup 保存 PID、日志和 `.exit`；退出码和业务输出均已核对：

| 检查 | PID | 实际结果 | exit |
|---|---:|---|---:|
| E1 CPU consumer | 1338223 | `E1_CONSUMER_PENDING`；700 refs、17 queue、0 selected、digest=`d148...732a` | 0 |
| current contract check | 1339212 | `CODE_CONTRACT_PASS`；516/509/300、k=40、live snapshot 47/16 | 0 |
| `tests/paper1_broadening` | 1339643 | `50 passed in 10.97s` | 0 |
| Python compileall | 1340036 | `paper1_broadening`、scripts、tests、B4 checks | 0 |
| `bash -n` | 1340128 | 全部项目 shell scripts | 0 |
| reused smoke evidence check | 1340233 | `CORE_REAL_SMOKE_PASS`、`NON_EVIDENCE`、24 generation/4 Judge | 0 |
| B4 delivery materialization | 1342363 | 102 files present (101 content hashes plus manifest metadata) | 0 |

对应日志均在 `logs/paper1_broadening/`，例如：

- `b4-e1-consumer-cpu-final-20260915T112325Z-1338219.{pid,log,exit}`
- `b4-contract-check-current2-20260915T112806Z-1339208.{pid,log,exit}`
- `b4-pytest-current-20260915T112952Z-1339639.{pid,log,exit}`
- `b4-pycompile-current-20260915T113057Z-1340032.{pid,log,exit}`
- `b4-bash-n-current-20260915T113139Z-1340124.{pid,log,exit}`
- `b4-smoke-evidence-current-20260915T113213Z-1340229.{pid,log,exit}`

早期直接使用系统 Python 的失败和第一次旧断言失败均保留，未计入通过证据；修正解释器/PYTHONPATH 和检查条件后才采用上述 exit=0 结果。

## 实际交付

当前版本交付目录为：

`writing/broadening design/report/evidence/paper1_post_recovery_runtime_handoff/`

该目录含当前 `paper1_broadening` 全包、相关 scripts/stage3/Judge/activation guard、全部 broadening tests、legacy/public/expanded configs、516-row source、509-record ledger、manifest、HarmBench 原始/standard 资产、来源 README/LICENSE/metadata、授权 source revision、LF-canonical 候选、A2 rebuilt ledger、恢复 prepare 小文件、C2 reference/queue/provisional 状态、smoke report、本轮 checks 和 `file_manifest.sha256`。交付状态记录在同目录 `delivery_state.json`。

完整 reviewer raw events 未复制，仍保留在 `.codex-temp/paper1_source_recovery_v2/batch1_review_run/`；expanded ledger 的 raw 路径指向该原目录。这样没有把可能含敏感运行信息的 raw 提交到小型交付目录，但当前工作区的 runtime identity 检查仍可定位原始 raw。模型权重和缓存没有复制。

## 剩余阻塞与边界自审

1. C2 的最新 reference snapshot (`d148...`) 与四个 derived ledger/selection 文件 (`8be3...`) 不一致，且 reviewer results 尚未齐全；这是唯一需要 E 接手的 E1 consumer pending。不得把 provisional 40 条写成可运行 gate。
2. Safe-pair data gate 已为 `READY_FOR_CONSTRUCTION`，但本轮没有构造方向或运行任何实验；safe-pair gate 不代表 Core/E1/E2 正式结果。
3. E2 仅完成资产接线；Gemma runtime/dose 和 E3 均未运行。历史 recovery prepare 快照未因本任务限制而重建，live snapshot 清单已逐项通过。
4. 本轮没有修改科学字段、原设计正文、safe-pair source/ledger/raw/run、旧 ledger 或 canonical legacy config；没有 commit/push；结束前没有 B4/prepare/model 进程。

边界自审结果：identity 映射、digest/gate fail-closed、snapshot 覆盖、smoke 次数和 phase 证据、E1 独立 schema、资产交付路径均已复核；发现的 C2 digest 不一致已通过消费者拒绝而非改写产物来处理。

**FORMAL_EXPERIMENTS_NOT_RUN**
