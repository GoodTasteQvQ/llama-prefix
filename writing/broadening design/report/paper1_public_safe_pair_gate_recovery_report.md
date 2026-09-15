# Paper 1 Public Safe-Pair Gate Recovery Report

任务书版本：`public-safe-pair-gate-recovery-v3`  
任务书：`writing/broadening design/implementation/paper1_server_codex_public_safe_pair_gate_recovery_prompt_nohup.md`  
报告日期：2026-09-15（Asia/Shanghai）  
工作目录：`/data/goodtaste_workspace/llama-prefix`  
分支：`stage3/impl-candidate`  
任务调查时 HEAD：`a12d204765a6c6177d6638d1103fdfe7f9b414ab`  
任务调查时工作树：dirty

## 最终状态

本任务未完成，在候选冻结和新增双审核启动前停止：
`BLOCKED_CANDIDATE_RESEARCH_INCOMPLETE`。

这不是新增 source 的 safe-pair gate 结果。A2 已核验基线仍为
`BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`：221 条 executable pairs 只能得到
`k=24<30`，至少还需要 29 条新的 executable pairs。由于本任务没有完成一批候选的
冻结和审核，因此没有新的 `actual_k`、最终合并 ledger 或新的 gate 结论。
`FORMAL_EXPERIMENTS_NOT_RUN`。

## 前置基线与边界

本任务复用用户提供的 A2 专项核验，不重复审核旧数据：

- source：416；exact evaluation overlap：7；preliminary eligible：409；
- A/B canonical requests：818，真实独立性和隔离证据已由 A2 专项核验确认；
- 最终 rebuilt ledger：221 include、188 exclude、0 pending；
- rebuilt 文件位于 `writing/broadening design/report/evidence/paper1_a2_b2_delivery/a2/`，
  对应文件为 `public_pair_quality_decisions.v2.rebuilt.json` 和 `rebuilt_summary.json`；
- 旧 `summary.json` 中的 817 ok/1 pending 是 `safe-pair:341` retry 前的历史统计，未采用；
- 7 条 exact overlap 排除项未重新审核，旧 409 条也未重新请求或改写。

本任务只允许在 `.codex-temp/paper1_source_recovery_v2/` 调查最多两个公开 paired
source bundles，并按任务书要求在任何 reviewer verdict 前冻结每批顺序。未进入共享
代码、正式 source/config 发布、测试或 prepare 阶段；没有加载模型或启动正式实验。

## 候选来源调查

候选原件保存在：
`.codex-temp/paper1_source_recovery_v2/candidate_research/`。

### Candidate 1: turkish-over-refusal-set

- GitHub：`https://github.com/fevziegeyurtsevenler/turkish-over-refusal-set.git`
- 固定提交：`13682bf03c9e7805b81df2eab7e23fb2512e560b`
- 数据文件：`data/turkish_over_refusal.jsonl`
- 数据文件 SHA256：`5e1910a1dfb129de7c68ee875143e2e810056efec895dec9b1b5cf663709f396`
- 规模：README 声明 120 个 matched pairs、480 行，含英文和土耳其文 safe/harmful 行；
  数据行带显式 `pair_id`、`type` 和 `lang`。
- 许可：仓库 `LICENSE` 和 `NOTICE.md` 声明 Apache-2.0；LICENSE SHA256 为
  `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`。

该来源已完成结构读取和固定提交/哈希记录，但尚未按本项目的英文双侧、旧 source、
evaluation frame 和 exact/normalized 去重规则做准入裁决、转换或选行冻结；不能视为已
接受的新增 source。

### Candidate 2: agentic-prompt-injection-boundary-pairs

- GitHub：`https://github.com/3nesdeniz/agentic-prompt-injection-boundary-pairs.git`
- 固定提交：`30af820d093245ee2863e4b10a3efbfbddb4d3e1`
- 数据文件：`data/train.jsonl`、`data/validation.jsonl`、`data/test.jsonl`
- 数据文件 SHA256：分别为
  `98fc7ea70a45215ba50d21efcd79cfed33afcbc1ac95d0fc388066b42cea2238`、
  `1e5f483277ca776f0bb7d26c1a85ca4cd6d73f8d30f638c75265d82a6de751c3`、
  `034523eefaec18c291f9daa7699037acb0e7a91b1aeb1b205878b124f6e18f10`。
- 规模：metadata 声明 600 pairs、1,200 English rows、50 scenarios，含显式 `pair_id`；
- 许可：README/CITATION 声明 CC BY 4.0；LICENSE SHA256 为
  `9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94`。

该来源只完成来源结构检查，尚未启用。没有与 Candidate 1 合并，也没有以两来源的
行数或标签直接假定本项目所需的 safe/harmful 配对关系。

## 未完成项目

以下产物在任务停止时不存在或为空，不能宣称已验证：

- 没有生成 `writing/broadening design/review/paper1_public_safe_pair_source_expansion_revision.md`；
- 没有保存第一批最多 100 条 preliminary eligible 的不可变冻结顺序、完整预检排除、
  入选和未入选 ID；
- 新增 reviewer requests：0；attempts/retries：0；A/B verdicts：0；
- 没有新增 raw output、thread/workdir 隔离证据、双审 ledger、rebuilt summary、请求索引
  或最终合并 ledger；
- 没有新增 source/config/manifest 正式版本，没有执行共享代码适配或测试；
- 没有读取并确认 B2/B3 交接后再执行最终发布；没有运行 prepare；
- 没有生成 `actual_k`、fold/development/unused 分配或新的 safe-pair gate 结果；
- E1 overlap、E2 runtime/dose 和所有正式模型实验均未运行。

完整候选仓库副本仍在上述 `.codex-temp` 路径，未复制 raw reviewer 数据，也未创建压缩包。

## 有边界自审

| 检查 | 结果 |
|---|---|
| 复用 A2 最终 221，而非失效 194 | PASS |
| 不重审旧 409 条或 7 条 exact overlap | PASS |
| 候选均记录固定提交、来源 URL、数据结构和许可信息 | PASS |
| 候选批次在 reviewer 前冻结 | NOT_DONE；未到该阶段 |
| 真实双 Codex 审核和 raw provenance | NOT_DONE；请求数为 0 |
| 新旧 source 去重、ledger/schema、N/k 与互斥分割 | NOT_DONE |
| 未修改共享实现、科学参数、旧 source/ledger/run | PASS |
| 未加载模型、未执行 prepare/正式实验 | PASS |

停止原因是任务在候选冻结和双审核启动前已中止，不能由本报告把来源调查升级为
`READY_FOR_CONSTRUCTION`。本任务调查会话没有 commit/push；本文件仅作为停止状态和
已确认事实的归档报告。

**FORMAL_EXPERIMENTS_NOT_RUN**
