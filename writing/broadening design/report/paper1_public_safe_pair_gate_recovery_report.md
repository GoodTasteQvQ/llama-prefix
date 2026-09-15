# Paper 1 Public Safe-Pair Gate Recovery Report

任务书版本：`public-safe-pair-gate-recovery-v3`  
任务书：`writing/broadening design/implementation/paper1_server_codex_public_safe_pair_gate_recovery_prompt_nohup.md`  
续作入口：`paper1_server_codex_e_resume_after_a3_b3_prompt_nohup.md`
设计修订：`MBD-NM v2.1.2-public-pairs-expanded`
日期：2026-09-15（Asia/Shanghai）
工作目录：`/data/goodtaste_workspace/llama-prefix`  
分支：`stage3/impl-candidate`  
HEAD：`9f39921`；工作树保留既有 dirty changes。

## 结论

safe-pair 数据 gate 已通过：source 516、preliminary eligible 509、executable 300、`actual_k=40`。5 folds 各40，development=100，unused=0，construction/development 不相交，gate 为 `READY_FOR_CONSTRUCTION`。新增来源只启用第一候选；第二候选未启用。

本任务没有加载模型或运行 directions、screen、generation、Judge、analysis、smoke 或正式实验。`FORMAL_EXPERIMENTS_NOT_RUN`。

## 前置与边界

已读取 E4 任务书、当前执行索引、A2 handoff、B3 delivery 和设计不可变性审计。B3 状态为 `B2_DELIVERY_READY` 且已停止共享代码写入；设计审计为 `DESIGN_IMMUTABILITY_AUDIT_PASS`。

A2 最终依据仍为 `rebuilt_summary.json` 与 `public_pair_quality_decisions.v2.rebuilt.json`：旧 source 416、exact overlap 7、preliminary 409、executable 221、`actual_k=24`。旧409条未重审，7条 exact overlap 未补审，失效 v1 的194条未使用。旧 source SHA256=`009a58760b4b22b445a53b6ca52213af3ae98cb5f9dc04d0c2f70192231b3cce`；旧 ledger SHA256=`f5d9ce975a5214b2c8ffdd343497cf35ceb565d1904ee809d872ad284a4f34fe`，自审确认均未改变。

新增修订只改变 append-only source 集合、身份和 provenance；模型、层、hook、decoder、rho、seed、fold、development、evaluation frame、判定标准和逻辑预算均未改变。`20,480` 仍是正式 logical generation budget，reviewer API 请求不计入该预算。设计正文未修改。

## 来源与冻结

唯一启用来源：`https://github.com/fevziegeyurtsevenler/turkish-over-refusal-set.git`，commit `13682bf03c9e7805b81df2eab7e23fb2512e560b`；数据 `data/turkish_over_refusal.jsonl` SHA256=`5e1910a1dfb129de7c68ee875143e2e810056efec895dec9b1b5cf663709f396`；Apache-2.0（`LICENSE`/`NOTICE.md`）。来源有120个显式 pair_id，每个一条英文 safe 和一条英文 harmful，另含土耳其文行；土耳其文行只保留在 snapshot，未纳入。未翻译、生成、改写、截断、拼接或重新配对。

Candidate 2 `agentic-prompt-injection-boundary-pairs` 只作调查记录，未启用、未冻结、未审核：GitHub URL 为 `https://github.com/3nesdeniz/agentic-prompt-injection-boundary-pairs.git`，固定调查提交 `30af820d093245ee2863e4b10a3efbfbddb4d3e1`，数据为 `train.jsonl`/`validation.jsonl`/`test.jsonl`（SHA256 分别为 `98fc7ea70a45215ba50d21efcd79cfed33afcbc1ac95d0fc388066b42cea2238`、`1e5f483277ca776f0bb7d26c1a85ca4cd6d73f8d30f638c75265d82a6de751c3`、`034523eefaec18c291f9daa7699037acb0e7a91b1aeb1b205878b124f6e18f10`），许可为 CC BY 4.0（LICENSE SHA256=`9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94`）。该候选为合成、单作者抽样复核来源；本次未因其质量作否定，而是因第一候选整批完成后已达到 gate，按停止规则不启用第二来源。

Batch 1 在 reviewer 请求前冻结：selected=`turkish-over-refusal-set:1`…`:100`（numeric pair_id 升序）；not selected=`:101`…`:120`；precheck exclusions=0；每条通过两侧英文、非空、真实 pair identity、旧416/JBB100/JBB40/benign30及批内 normalized exact 检查。evaluation digest=`db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`。

冻结产物：`.codex-temp/paper1_source_recovery_v2/batch1_freeze.json`、`batch1_freeze_review_started.json`、`batch1_pairs.json`、`batch1_candidate_order.json`、`candidate1_precheck.json`；来源修订：`writing/broadening design/review/paper1_public_safe_pair_source_expansion_revision.md`。

## 真实双审核

审核目录：`.codex-temp/paper1_source_recovery_v2/batch1_review_run/`。使用 `public-semantic-pair-quality-v2` 和 `public-safe-pair-quality-ledger-v2`。每个 pair 两个真实、隔离、read-only Codex 请求，保留实际 prompt/input hash、evaluation digest、thread、raw event/output、attempts、时间和 hash。

- 100 pairs，200 canonical requests，200/200 valid raw，200 unique thread，invalid=0，pending=0；
- A：include 93 / exclude 5 / uncertain 2；B：include 83 / exclude 13 / uncertain 4；
- batch decisions：79 include、21 exclude；只有双方 include 才纳入；
- 技术 retry：`turkish-over-refusal-set_22.a`、`_43.a` 各一次相同输入重试；198 次一次完成，2 次两次完成；未为改变合法 exclude/uncertain 重试。

raw audit：`.codex-temp/paper1_source_recovery_v2/batch1_review_run/batch1_raw_audit.json`。batch ledger：`public_pair_quality_decisions.batch1.json`，SHA256=`8c19b4806e7a68ad637503d2d506d8f227b95d0c9d5fe3e13eb24f6b93d3af93`；summary SHA256=`d7d345f2b0f60f300d9244a136bbccd3c7be7b9cf4df34d28a5bd611c354fc74`。完整 raw 保留在该目录；没有用 PID 冒充 reviewer 证据。

独立只读 protocol self-check 复核了 raw/ledger/source/config：A/B 各100 primary envelope、各200 event stream、200 unique thread、所有 raw/ledger hash 与 request binding 一致；未发现 schema、计数、身份或内容不一致。`batch_freeze_sha256` 在 manifest 中指向原始不可变 `batch1_freeze.json`（SHA256=`692de996944ab12abf5fb84e8cff27fc08e39a4064af7afa49813fe80f244825`）；review-start 状态另存为 `batch1_freeze_review_started.json`（SHA256=`e819b67239f11d4db9286625e5a19b9e93309f9eca9ad81890d1aea4b7a33ddc`）。这是 provenance 文件命名差异，selected IDs、文本和审核输入一致，不影响数据结果。候选冻结副本无 `.git` 目录，但同内容候选 clone 的 fixed commit、数据 hash 和 LICENSE hash 已核验。

## 整合产物

旧416行逐字保留，新行只追加。新增行保留原始 `turkish-over-refusal-set:*` pair_id、source line index、dataset、commit 和 file。为兼容现有内部 `safe-pair:{source_index}` identity，新增行带 `review_pair_id`，loader 仅用该字段绑定新增 raw；旧416行绑定不变。

- source：`data/safe_pairs_public_semantic_v2_expanded.json`，516 rows，SHA256=`d63fd3db8ddd721bd420484c4f4b05e52e39123bbf550e8802ab0af7674723a2`；
- ledger：`data/safe_pairs_public_semantic_v2_expanded_ledger.json`，509 records，SHA256=`20892484eaa65a5925b3f625338d5a97d2fd0477293956015cfa86ad5903c8db`；include 300 / exclude 209 / pending 0；
- manifest：`data/safe_pairs_public_semantic_v2_expanded.manifest.json`，SHA256=`61995f6a5d068c1105ca6a86b2eb704305951224630e1580eff34cfcdbdfc31d`；
- config：`configs/paper1_broadening/mbd_nm_v212_public_expanded.json`，SHA256=`d15edaeeed1b9f19203ed8271606e4ac09c174c1206ac89955badeca1e8fe720`；
- integration script：`scripts/recover_public_safe_pair_batch1.py`；summary：`.codex-temp/paper1_source_recovery_v2/expanded_summary.json`，SHA256=`6714cbd6198cce900772a58aa129c5872aa139450451b9a222b7854514457796`。

`config.py` 增加 expanded revision/path 校验，`frames.py` 增加 `review_pair_id` provenance 绑定并修正 preliminary count 统计，`orchestration.py` 增加 expanded source/ledger/config/recovery snapshot；均为本次 source/provenance 适配，不改变科学字段。

## Gate、测试与 prepare

最终 frames：`results/paper1_broadening/public-safe-pair-recovery-v2-final-20260915T041534Z/frames.json`。

- source=516；preliminary=509；executable=300；`actual_k=40`；fold sizes=`[40,40,40,40,40]`；development=100；unused=0；disjoint=true；
- frame 中旧7条 exact-overlap 仍是 preliminary 预检排除，不属于 semantic-review pending；新增 ledger 的 pending 为0；
- evaluation digest 单一且为 `db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`；
- safe-pair gate=`READY_FOR_CONSTRUCTION`；这不代表 E1/E2 或正式实验 gate。

最终 prepare 目录：`results/paper1_broadening/public-safe-pair-recovery-v2-final-20260915T041534Z/`，包含 `run_header.json`、`resolved_config.json`、`frames.json`、`plan.json`、`identity_plan.json`、`overlap_review_queue.json`。source snapshot 共47项，包含 expanded source、manifest、ledger、config 和恢复脚本；`loaded_identities` 为空。E1 为 `NOT_RUN / E1_SEMANTIC_OVERLAP_REVIEW_PENDING`（17 queue）；E2/E3 未运行。

离线测试：`tests/paper1_broadening` 45 passed，最终测试 PID=1245295，exit=0。最终 prepare PID=1247227，exit=0。整合最终 PID=1240937，exit=0。所有 `.pid/.log/.exit` 在 `logs/paper1_broadening/recovery-v2-*`；首次 wrapper 缺失 `.exit`、两次失败重试均如实保留，未作为通过证据。

## 执行证据索引

实际长步骤均在 Linux 临时目录中以 nohup 执行，并保留以下文件：

| 步骤 | 实际命令/对象 | worker PID | log | exit |
|---|---|---:|---|---|
| batch freeze | `.codex-temp/paper1_source_recovery_v2/prepare_batch1_freeze.py` 的 batch 1 冻结 | 1173417 | `logs/paper1_broadening/freeze-batch1-final-20260915T004604Z-1173414-28987.log` | wrapper 未生成；以冻结 JSON/hash 核对 |
| dual review | `run_batch1_reviews.py`，200 canonical requests | 1174036 | `logs/paper1_broadening/batch1-dual-review-20260915T004915Z-1174033-22407.log` | runner 未生成；不以 PID 代替审核证据，以 `progress.json` 200/200、raw audit 和 ledger 为准 |
| integrate | `scripts/recover_public_safe_pair_batch1.py` | 1240937 | `logs/paper1_broadening/recovery-v2-integrate-20260915T034405Z-1240935-24982.log` | `...24982.exit=0` |
| tests | `python -m pytest tests/paper1_broadening -q -p no:cacheprovider` | 1245295 | `logs/paper1_broadening/recovery-v2-tests-final-20260915T040546Z-1245292-12647.log` | `...12647.exit=0` |
| prepare | `run_paper1_broadening_single_gpu.sh prepare --config mbd_nm_v212_public_expanded.json` | 1247227 | `logs/paper1_broadening/recovery-v2-prepare-final-20260915T041534Z-1247223-7413.log` | `...7413.exit=0` |

整合的两次失败尝试（PID 1239248、1240005，exit=1）以及无 exit 的首次 wrapper（PID 1238341）均保留，未计为通过。完整 reviewer event/raw 不依赖 nohup PID，位于 `.codex-temp/paper1_source_recovery_v2/batch1_review_run/`。

## 有边界自审

| 检查 | 结果 |
|---|---|
| 复用A2最终221，不使用194；不重审旧409，不补审7条 | PASS |
| 最多两个来源，实际一个；第一批完整后达标，不启用第二批 | PASS |
| reviewer前冻结顺序、预检排除、选中/未选中 | PASS |
| 两侧英文、pair identity、source index、license、commit 可追溯 | PASS |
| 200真实A/B请求、隔离、raw、thread、attempt、schema | PASS |
| 双include才纳入；新增79 include/21 exclude | PASS |
| 旧 source/ledger/raw/run 未覆盖；append-only source/config/ledger/manifest | PASS |
| N/k、5 folds、development、unused、disjoint、digest | PASS |
| 设计正文和科学字段未改变 | PASS |
| E1 overlap、E2 runtime/dose、模型实验 | NOT RUN / 独立 pending |
| 未误启动模型、directions、screen、generation、Judge、analysis | PASS |

原任务执行期间未 commit/push；收尾时用户后续明确授权仅将本报告提交到 GitHub。本次只提交本报告，其他 dirty/untracked 交付物和完整 raw 仍按上述路径保留供同步；到达明确 safe-pair gate 后停止，不自动启动后续 C/D 或 Core 阶段。

**FORMAL_EXPERIMENTS_NOT_RUN**
