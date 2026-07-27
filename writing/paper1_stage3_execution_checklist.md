# Paper 1 Stage 3 Execution Checklist

更新时间：2026-07-23

当前 baseline：`v3.5-rc2 + binding-amendment-01`

当前状态：`DESIGN-FREEZE-PASS / RUN-BLOCKED`

唯一入口：`D:\llama_prefix\writing\stage3 design\CURRENT_RELEASE.md`

## 使用规则

- 每个 checkbox 只有在对应 artifact、receipt、hash 或 test output 已保存后才能勾选。
- 不以 Codex/Claude 的口头 `PASS` 替代 machine-readable evidence。
- 不修改 frozen protocol、manifest、schema、golden fixture、expected output 或 verifier。
- 不创建 `v3.5-rc3`；implementation revision 使用独立 Git tag，例如 `paper1-stage3-impl-r0`。
- Local Codex 负责 implementation；GitHub 负责 code pinning；server Claude CLI 负责真实环境闭合和 staged execution。
- Server 不 hotfix。发现代码问题时返回本机修复，三名 subagent 全部重审，并发布新 commit/tag。
- 不再发起 open-ended TDSC design review。后续只做 implementation、data integrity 和 claim-evidence audit。

## 0. Frozen Scope

### Retained scope

- [ ] Execution profile 固定为 `compact_single_gpu`。
- [ ] Behavior model 固定为 Qwen-only。
- [ ] P1 固定为 100 harmful + 100 benign measurement prompts。
- [ ] P2 固定为 `P=50`、`V=20`、A/T、estimation-only。
- [ ] K1 只复用 P2，不新增 generation。
- [ ] Benign block 固定 `N=30`。
- [ ] Human validation 固定 `N=720`。
- [ ] Logical generation budget 固定为 5,580。
- [ ] First-pass scheduled judge budget 固定为 5,580。
- [ ] Judge development 固定为 manual/document-only、zero model calls。

### Excluded scope

- [ ] 未恢复 K2、V2、Attention experiment、rendering 2x2、stochastic block 或 phase confirmation。
- [ ] 未恢复 model-based RD/CI、power/coverage simulation 或 P/V selector。
- [ ] 未新增 model、prompt、vector、anchor、endpoint、response cell 或 human item。
- [ ] 未新增 confirmatory p-value、Boolean rejection gate 或 prospective power claim。
- [ ] Stage 3 未被写成 Attention Sink causal proof 或 cross-model explanation。

## A. Local Implementation Closure

### A1. Baseline and repository state

- [ ] 第一份读取的文件是 `CURRENT_RELEASE.md`。
- [ ] 只读取其列出的 normative inputs；未用 archive、old protocol 或 judge-subagent history 改变实现。
- [ ] 保存开始时的 Git status、baseline commit 和 frozen-file hash receipt。
- [ ] 识别用户已有修改并确认未覆盖 unrelated work。
- [ ] 建立 implementation task list，区分 local work 与 `SERVER_ONLY / DEFERRED_SERVER_BINDING`。

### A2. Static release verification

- [ ] `python -B scripts/stage3_rc2/verify_release.py` exit code 为 0。
- [ ] Base marker 为 `DESIGN-FREEZE-PASS`。
- [ ] `python -B scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py` exit code 为 0。
- [ ] Aggregate marker 为 `AMENDMENT_STATIC_VERIFICATION_PASS`。
- [ ] 验证过程未重写 frozen artifacts。

### A3. Production implementation

- [ ] 实现 deterministic logical identity registry。
- [ ] 实现 P1/P2/K1/benign record schema 和 validation。
- [ ] 实现 generation producer，但本机不运行 formal generation。
- [ ] 实现 exact formal judge parser；未使用 permissive text/regex fallback。
- [ ] 实现固定 retry rule 和 terminal failure status。
- [ ] 实现 dose/alpha finite validation 和 identity collision handling。
- [ ] 实现 retained predicate、support status 和 downstream mapping。
- [ ] 复用 bound reference statistics；未自行替换算法。
- [ ] 集成 retained bootstrap、two-phase correction 和 fixed720 allocator。
- [ ] 实现 append-only receipt、artifact hash 和 provenance recording。
- [ ] 所有 server path 可配置；未硬编码本机 `D:\` 路径。

### A4. E0 and synthetic dry-run

- [ ] Freeze lifecycle golden cases 通过。
- [ ] Identity collision、missing ID 和 unexpected ID cases 通过。
- [ ] Invalid dose、zero denominator 和 nonfinite cases 通过。
- [ ] Judge parser、retry 和 terminal parse failure cases 通过。
- [ ] `SUPPORTED`、`SUPPORT_LIMITED`、`NON_ESTIMABLE_IDENTITY` 和 `NON_ESTIMABLE_ANALYSIS` cases 通过。
- [ ] Retained bootstrap golden tests 通过。
- [ ] Two-phase correction golden tests 通过。
- [ ] Fixed720 allocator golden tests 通过。
- [ ] Synthetic production-shape dry-run 通过。
- [ ] 所有 dry-run output 明确标记 `SYNTHETIC / NON-FORMAL`。
- [ ] 本机未产生任何 formal P1/P2/support/judge/human data。

### A5. Offline JSON asset closure

- [ ] 扫描 production call graph 并生成 `external_dependency_inventory.json`。
- [ ] 只把 frozen Stage 3 实际需要的 JSON 分类为 `FORMAL_INPUT`。
- [ ] `safe_pairs.example.json`、`single_prompt_bomb.json` 和旧 Stage 1 input 未被自动纳入 Stage 3。
- [ ] 现有 JSON 原始字节、字段顺序和顶层结构未修改。
- [ ] 每个 `FORMAL_INPUT` 已记录 relative path、raw SHA256、bytes、UTF-8、schema、row count 和 stable IDs。
- [ ] Raw-file hash 与 canonical prompt-frame hash 分开记录。
- [ ] Missing provenance 使用 `PROVENANCE_INCOMPLETE`，未编造 revision。
- [ ] `scripts/download_jbb_behaviors.py` 不在 server production call graph 中。
- [ ] Production loader 只从 `PAPER1_STAGE3_ASSET_ROOT/data/...` 或 repo-relative `./data/...` 加载。
- [ ] 创建 `offline_asset_manifest.json` 和 `checksums.sha256`。
- [ ] 创建 Linux-compatible offline bundle，保留 JSON 原始字节。
- [ ] 记录 bundle filename、SHA256、file count 和 total bytes。
- [ ] 在 clean temporary cache 下设置 `HF_HUB_OFFLINE=1`、`HF_DATASETS_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。
- [ ] Offline smoke test 主动阻断 HTTP/HTTPS，并确认 production path 无网络请求。
- [ ] Missing file、hash mismatch、schema mismatch 和 duplicate identity 均 fail closed。
- [ ] 最终状态为 `OFFLINE-ASSET-READY`。

### A6. Three independent subagent audits

- [ ] Subagent A 完成 protocol/lifecycle/identity/scope audit。
- [ ] Subagent B 完成 statistics/schema/numerical fidelity audit。
- [ ] Subagent C 完成 production reliability/offline/resource audit。
- [ ] 三名 subagent 都是 read-only auditor，未直接修改代码。
- [ ] 三份 audit receipt 绑定同一个 final commit/working-tree baseline。
- [ ] 每个 finding 都有 file、line、evidence、required fix 和 test command。
- [ ] 任一代码修复后，A/B/C 全部重新审计，而非只重跑失败者。
- [ ] 最终 A=`PASS`、B=`PASS`、C=`PASS`。
- [ ] 若同一根因连续三轮无进展，状态为 `IMPLEMENTATION-BLOCKED`，未伪造 PASS。

### A7. Local release gate

- [ ] Main agent 重跑 release verifier、amendment verifier、E0、offline smoke 和 synthetic dry-run。
- [ ] `git diff --check` 通过。
- [ ] Frozen file hashes 与 baseline 一致。
- [ ] Final implementation receipt 已记录 tests、audit receipts、file inventory 和 deferred server inputs。
- [ ] Local final status 为 `IMPLEMENTATION-READY`。
- [ ] Offline final status 为 `OFFLINE-ASSET-READY`。
- [ ] Receipt 明确声明“未运行正式实验”。

## B. GitHub Code Pinning and Artifact Transfer

- [ ] Review staged files，确认没有 model weights、secrets、raw generations、judge outputs 或 human annotations。
- [ ] 根据 license、sensitivity 和 repository visibility 决定 JSON 是否进入 Git；默认使用独立 offline bundle。
- [ ] Commit 包含 production code、tests、schemas、manifests、checksums 和 implementation receipt。
- [ ] Commit SHA 已保存到 handoff receipt。
- [ ] 创建 annotated implementation tag，例如 `paper1-stage3-impl-r0`。
- [ ] Tag 指向已通过 A/B/C 三方审计的同一个 commit。
- [ ] Push 后从 remote 复核 tag 与 commit SHA。
- [ ] Offline bundle 通过独立受控方式传到服务器。
- [ ] 本机 bundle SHA256 和服务器接收前 expected SHA256 已记录。

## C. Server Real-Environment Closure

### C1. Immutable checkout

- [ ] Server working tree 无未记录修改。
- [ ] 使用 `git fetch --tags` 后 detached checkout 指定 implementation tag/commit。
- [ ] `git rev-parse HEAD` 与 handoff receipt 完全一致。
- [ ] Server 上不执行 source hotfix。

### C2. Offline assets

- [ ] Offline bundle SHA256 与本机 receipt 一致。
- [ ] 解压后 file count、total bytes 和 per-file SHA256 全部一致。
- [ ] `PAPER1_STAGE3_ASSET_ROOT` 指向正确资产根目录。
- [ ] Empty-cache offline smoke test 在服务器再次通过。
- [ ] Server 正式路径无法访问网络时仍可 fail-fast、无 online fallback。

### C3. Runtime and real identities

- [ ] 记录 GPU、driver、CUDA、Python、PyTorch、Transformers 和 dependency versions。
- [ ] 锁定 real checkpoint/revision/weight hashes。
- [ ] 锁定 tokenizer files 和 hashes。
- [ ] 锁定 chat template、prompt frame、base anchors 和 vectors。
- [ ] 锁定 layer、dtype、device、generation settings 和 producer code hash。
- [ ] 所有 from_pretrained 使用 local path，并在支持时设置 `local_files_only=True`。
- [ ] 生成 real identity/runtime manifests，且为 append-only/content-addressed。

### C4. Server verification and feasibility

- [ ] Base release verifier 在服务器 exit code 0。
- [ ] Amendment aggregate verifier 在服务器 exit code 0。
- [ ] E0/golden tests 在目标 runtime 通过。
- [ ] 非正式 server smoke test 未写入 formal result tree。
- [ ] 单卡 VRAM、disk、temporary storage 和 estimated runtime 满足执行要求。
- [ ] 未通过更改 dtype、decoder、model 或 protocol 来规避资源问题。
- [ ] 最终 server preflight 状态为 `SERVER-RUN-READY`。
- [ ] 若 checkpoint identity 不可锁定，状态为 `BLOCKED_EXTERNAL_INPUT` 并停止。

## D. Formal P1 Measurement

### D1. Pre-outcome freeze

- [ ] Lifecycle event 1：`IDENTITIES_AND_E0_VALID` 已记录。
- [ ] 在任何 formal P1 outcome 可见前生成 `measurement_specification_freeze.json`。
- [ ] Specification freeze 绑定 200-prompt frame、rendering/extraction、complete-case、estimand、bootstrap、RNG、failure rules、anchors 和 producer identity。
- [ ] Specification freeze 不包含 observed IDs、counts、norms、`mu`、dose、alpha、gate output 或 support status。
- [ ] Lifecycle event 2：`MEASUREMENT_SPECIFICATION_FROZEN` 已记录。

### D2. P1 execution

- [ ] 只运行固定 100 harmful + 100 benign P1 measurement prompts。
- [ ] 未增加、替换、reroll 或补抽 prompt。
- [ ] 所有 200 scheduled identities 都有 terminal state。
- [ ] Lifecycle event 3：`P1_OUTCOME_VISIBLE` 已记录。

### D3. Result/dose freeze

- [ ] 只生成一次 `measurement_result_dose_manifest.json`。
- [ ] Manifest 记录 scheduled identities、terminal states、complete-case frames 和 exclusion reasons。
- [ ] 记录 pooled numerator/denominator、content-token count、token shares、`mu_all_tw`、`mu_content_tw` 和 `median_content_norm`。
- [ ] 记录 numerator-frame hash、`rho_A/rho_T/rho_H`、`c_A/c_T/c_H`、pre/post-dtype alpha 和 producer hashes。
- [ ] Decimal/binary64 representation、timestamp、parent hash 和 self hash 完整。
- [ ] Zero denominator、nonfinite、missing parent 或 formula mismatch 正确产生 `P1_DOSE_NON_ESTIMABLE`。
- [ ] Lifecycle event 4：`MEASUREMENT_RESULT_DOSE_FROZEN` 已记录。
- [ ] P1 receipt 已保存，随后停止；未提前启动 judge/support/confirmation。
- [ ] 人工复核 manifest 后明确给出 `P1-CONTINUE` 或 `P1-BLOCKED`。

## E. Judge, Support, Confirmation and Human Validation

### E1. Judge freeze

- [ ] Manual/document-only judge development 完成，model/judge call count 为 0。
- [ ] `judge_development_ledger.json` 已记录。
- [ ] Lifecycle event 5：`JUDGE_DEVELOPMENT_MANUAL_COMPLETE` 已记录。
- [ ] `judge_freeze.json` 绑定 judge checkpoint/tokenizer/template/runtime/dtype/parser/retry 和 producer hashes。
- [ ] Judge freeze 发生在第一条 formal support response 产生前。
- [ ] Lifecycle event 6：`JUDGE_FROZEN` 已记录。

### E2. Support execution

- [ ] Lifecycle event 7：`FORMAL_SUPPORT_GENERATION_STARTED` 已记录。
- [ ] A/T/H 各 300 scheduled rows，合计 900-row support ledger。
- [ ] 每个 scheduled identity 只使用固定 retry，不 reroll、不补抽。
- [ ] Completed empty/collapsed response 可由 valid `broken` label retained。
- [ ] Technical/model/parse/identity/dose failures 按 retained predicate 排除。
- [ ] 每个 anchor 正确映射为 `SUPPORTED`、`SUPPORT_LIMITED` 或 `NON_ESTIMABLE_IDENTITY`。
- [ ] `support_execution_manifest.json` 记录完整 ledger、calls/retries、labels、counts、status 和 hashes。
- [ ] Lifecycle event 8：`SUPPORT_EXECUTION_MANIFEST_FROZEN` 已记录。

### E3. Behavior confirmation

- [ ] `behavior_confirmation_freeze.json` 在任何 confirmation output 可见前锁定 identities。
- [ ] 固定 P2、harmful-clean、benign-steered 和 benign-clean blocks 未扩样。
- [ ] Lifecycle event 9：`BEHAVIOR_CONFIRMATION_FROZEN` 已记录。
- [ ] Lifecycle event 10：`FORMAL_CONFIRMATION_GENERATION_STARTED` 已记录。
- [ ] Total logical generation 保持 5,580。
- [ ] Total first-pass scheduled judge 保持 5,580。
- [ ] K1 只复用 P2 output，未新增 generation。
- [ ] 每个 block 完成后保存 append-only execution receipt。

### E4. Fixed720 human validation

- [ ] Automated-label-producing judge identity 在规定时点前已冻结。
- [ ] Fixed720 allocator 使用冻结 population、strata、priority 和 tie-break。
- [ ] Human sample lock 记录 `N_h`、`n_h`、inclusion probability、selected IDs、shortfall 和 hash。
- [ ] Human annotation package 与自动标签按 protocol 要求隔离/blind。
- [ ] Annotation rubric、annotator identity、adjudication 和 missing annotation rule 已锁定。
- [ ] 最终 human item count 为 720；未补抽或扩大样本。
- [ ] Two-phase correction 使用绑定 reference implementation。
- [ ] Positivity、Kish ESS、maximum normalized weight 和 quality gates 已执行。

## F. Statistical Analysis and Result Artifacts

- [ ] 所有正式输入先通过 schema、identity、frame-hash 和 provenance validation。
- [ ] P1 使用 bound `B=10,000` reference bootstrap。
- [ ] P2/raw retained analysis 使用冻结 replicate count 和 common-success rule。
- [ ] Two-phase analysis 使用 bound `B=9,999` implementation。
- [ ] Synchronized RNG、seed serialization、member identity 和 draw order 与 golden fixtures 一致。
- [ ] `SUPPORT_LIMITED` 只降级语言，不改变固定 matrix 或 sample size。
- [ ] Identity failure 优先产生 `NON_ESTIMABLE_IDENTITY`。
- [ ] Analysis/CI failure 产生 `NON_ESTIMABLE_ANALYSIS`。
- [ ] P2 只报告 estimation-only point estimate、CI、status 和 diagnostics。
- [ ] 未生成 confirmatory p-value、multiplicity decision、power 或 rejection claim。
- [ ] 保存 machine-readable result tables、analysis logs、environment manifest 和 output hashes。
- [ ] Formal result tree 与 synthetic/E0 output tree 完全分离。

## G. Result and Claim Audit

### G1. Data integrity audit

- [ ] Git commit、protocol hashes、runtime manifests、data hashes 和 result hashes 可形成完整 provenance chain。
- [ ] Logical budget、actual calls、retry counts 和 terminal states 算术一致。
- [ ] Raw generation、judge output、human annotation 和 analysis rows 可以按 identity join。
- [ ] Missing、duplicate、unexpected ID 和 parser failure 已显式报告。
- [ ] 三名独立 auditor 分别完成 execution、statistics 和 artifact/claim audit。
- [ ] 任一正式结果修复均保留原始 artifact，不覆盖 immutable evidence。

### G2. Deterministic claim mapping

- [ ] P1 pass 且 P2 direction/CI 清晰：只允许写 calibration changes measured dose，并对应 frozen Qwen support 上的 unsafe/broken estimate differences。
- [ ] P1 pass 但 P2 uncertain/non-estimable：只允许写 calibration statistic changes，behavioral consequence remains uncertain。
- [ ] P1 gate fail：报告 frozen Qwen frame 下未发现 material calibration shift；不搜索替代 estimator/anchor。
- [ ] Human quality/CI fail：保留 automated estimate 并明确 limitation，不省略失败。
- [ ] 未写 structural token 或 Attention Sink 导致一般 collapse。
- [ ] 未把 Stage 3 写成 cross-model mechanism explanation。
- [ ] 未把 estimation-only CI 写成 significance 或 confirmatory evidence。

### G3. Paper update

- [ ] 更新 `paper1_claim_evidence_matrix.md` 中 Stage 3 evidence/status。
- [ ] 根据实际结果选择 blueprint 中唯一对应 result branch。
- [ ] 主文 Figure/Table 只使用可追溯的 formal outputs。
- [ ] Methods 记录 exact checkpoint、prompt frame、anchors、vectors、runtime、budget 和 missingness/status rules。
- [ ] Limitations 保留 Qwen-only、fixed support、estimation-only 和 no causal Attention claim。
- [ ] Abstract/Conclusion 不提前升级 Stage 3 claim。

## H. Final Completion Gate

Stage 3 只有在以下项目全部满足后才可标记 execution complete：

- [ ] Local `IMPLEMENTATION-READY`。
- [ ] Local `OFFLINE-ASSET-READY`。
- [ ] GitHub commit/tag 已固定并复核。
- [ ] Server `SERVER-RUN-READY`。
- [ ] P1 result/dose manifest 已冻结并通过复核。
- [ ] Judge/support/behavior confirmation lifecycle 完整。
- [ ] 5,580 generation、5,580 scheduled judge 和 720 human budget 无扩张。
- [ ] Reference statistical analysis 完成或按 protocol 明确 non-estimable。
- [ ] Result integrity audit 通过。
- [ ] Claim-evidence matrix 与 paper wording 已按实际 evidence 更新。
- [ ] 未新增实验设计版本，未恢复删除范围，未进行 result-driven redesign。

最终允许的阶段状态：

```text
DESIGN-FREEZE-PASS / RUN-BLOCKED
IMPLEMENTATION-READY / OFFLINE-ASSET-READY
SERVER-RUN-READY
P1-CONTINUE or P1-BLOCKED
SUPPORT-SUPPORTED / SUPPORT-LIMITED / NON-ESTIMABLE
STAGE3-RESULTS-COMPLETE or STAGE3-RESULTS-NON-ESTIMABLE
```
