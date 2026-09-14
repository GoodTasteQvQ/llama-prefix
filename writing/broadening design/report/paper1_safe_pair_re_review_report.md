# Paper 1 safe-pair v2 re-review report

执行日期：2026-09-14 UTC。执行依据：`writing/broadening design/implementation/paper1_server_codex_safe_pair_re_review_prompt_nohup.md`。B2 contract repair 已完成；本任务完成审核、ledger rebuild、离线测试和一次新 prepare 后停止。`FORMAL_EXPERIMENTS_NOT_RUN`。

## Final status

最终 gate：`BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`。审核 provenance 完整，但 executable safe pairs 只有 221，动态规则得到 `actual_k=min(80,(221-100)//5)=24<30`，因此没有 construction folds 或 development allocation，也没有进入任何 GPU 模型阶段。

## Review execution

- Public source：`data/safe_pairs_public_semantic_v1.json`，416 rows；pair id、harmful 文本和 harmless 文本均各自唯一。
- 独立 preliminary eligible：409 pairs，要求 818 requests。
- 完整 run：`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-v2-20260908T111917Z/`。
- 完成度：818/818 request records；A=409、B=409；818 个唯一 Codex thread id。
- 每条 request 均保存完整 system/developer/user prompt 及 SHA256、pair input JSON SHA256、evaluation digest、模型/revision/reasoning 参数、UTC 时间、isolation evidence、raw event JSONL、raw output 与 SHA256。
- reviewer A 的 `safe-pair:341` 截断 raw 使用独立真实 Codex retry raw：`raw/a/safe-pair_341.a.retry.json`；旧截断 raw 未作为结果使用。
- 运行方式为 A/B 严格串行；A 不可见 B，B 不可见 A；单 request 的 HTTP 429 按授权最多重试 100 次并保留 attempts。没有使用 regex、semantic-score、embedding 阈值、本地模型批处理、旧 ledger 或批量启发式替代。
- 中断的 `public-semantic-pairs-v2-20260908T112042Z` 仅有 5/818，不进入本次 ledger；旧 ledger 保留为 `INVALID_REVIEW_HISTORY`。

## Rebuilt ledger

重建脚本：`scripts/rebuild_public_safe_pair_ledger_v2.py`；nohup 日志：`logs/paper1_broadening/rebuild-public-safe-pair-ledger-v2-20260914T122122Z.log`，exit=0。

新 ledger：`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-v2-20260908T111917Z/public_pair_quality_decisions.v2.rebuilt.json`。

- schema/status：`public-safe-pair-quality-ledger-v2` / `COMPLETE`
- invalid requests：0；pending：0
- A verdict：include 293 / exclude 100 / uncertain 16
- B verdict：include 285 / exclude 106 / uncertain 18
- unanimous include：221；其余 188 按规则裁决为 exclude
- ledger SHA256：`f5d9ce975a5214b2c8ffdd343497cf35ceb565d1904ee809d872ad284a4f34fe`
- 818 unique agent ids；`rebuilt_summary.json` 保存独立统计和 hash。

## Offline test and prepare

- Public config：`configs/paper1_broadening/mbd_nm_v211_public.json`，仅将 `overlap_decisions_path` 指向上述 rebuilt ledger；旧 canonical config 未修改。
- 离线测试命令通过 nohup 执行：`logs/paper1_broadening/public-safe-pair-re-review-tests-v2-20260914T122401Z.log`，exit=0，`43 passed in 11.52s`。
- 唯一新 prepare：run `public-semantic-pairs-v2-20260914T122608Z`，目录 `results/paper1_broadening/public-semantic-pairs-v2-20260914T122608Z/`；日志 `logs/paper1_broadening/public-safe-pair-re-review-prepare-v2-20260914T122608Z.log`，exit=0。
- prepare header：code commit `af842139abb8c88c29c99e85a85752e2b42fe5da`，dirty worktree=true；resolved config SHA256 `6515a6a9423b23c92f6819e9ec9f5c6045931cb6c464be471395230dbb8abfc3`。
- frames：source_count=416；独立 preliminary eligible=409；prepare 后用于 split 的 executable=221（frames 中的 `preliminary_eligible_count` 在无 pending 时记录该最终 split 集合）；exact evaluation overlap=7；near-match queue=43；evaluation digest=`db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`；mixed digest=false；role isolation 标记 construction/development disjoint=true、evaluation role=`JBB_and_benign_only`。
- E1/E2/E3 均未调度：E1 资产/metadata 缺失，E2 Gemma 未配置，E3 等待 core gates。

## Boundary self-audit

本次未修改旧 source、旧 ledger 或旧 run；未使用旧 verdict/rationale 作为新 reviewer 输入；未启动 source recovery、directions、screen、generation、Judge、analysis、human packet、smoke 或任何正式模型实验；没有为达到 250 放宽规则。当前无审核、prepare 或实验后台进程。任务在 `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS` 后停止，等待负责人决定是否另行授权 source recovery。
