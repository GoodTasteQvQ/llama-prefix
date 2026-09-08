# Paper 1 Claim-Evidence Matrix

更新时间：2026-08-12

状态：当前写作和结果解释的唯一主张边界。Stage 3 科学设计入口为
`writing/stage3 design/README.md`。

## 状态定义

- `SUPPORTED`：已有本地可复核结果，可在限定边界内写入正文。
- `SUPPORTED_WITH_BOUNDARY`：方向已有证据，但只能使用矩阵中的限定措辞。
- `PARTIAL`：已有先导或描述性证据，尚不能作为强结论。
- `DESIGN COMPLETE / NOT RUN`：对应模块的科学设计完整，但该模块没有 paper-run 结果；不表示整个 Stage 3 均未运行。
- `NOT SUPPORTED`：当前证据不支持；只能写 limitation/future work。
- `FORBIDDEN`：与当前设计或证据直接冲突，不得写入论文。

## 当前证据登记

| ID | 证据 | 当前状态 | 位置 |
|---|---|---|---|
| E01 | Qwen A-F phase-call audit | completed | `实验notion/notion_md/assets/qwen_phase_call_audit_alpha_or_c_1.csv` |
| E02 | Qwen 六方法 Track A/B full1000 judge | completed | `results/stage1_phase_aware/formal/qwen25/judge_summaries/qwen25_stage1_qwen3_v2_all6_full1000_judge_summary_from_judged.json` |
| E03 | Llama 六方法 Track A/B full1000 judge | completed | `results/stage1_phase_aware/formal/llama31/judge_summaries/llama31_stage1_qwen3_v2_full1000_judge_summary.json` |
| E04 | Qwen/Llama cross-model figures | completed | `results/stage1_phase_aware/formal/cross_model_paper1/tdsc_style_figures/` |
| E05 | Stage 2 failure-aware analysis | completed but narrative needs Llama-full1000 refresh | `实验notion/notion_md/阶段2 Decode Collapse 诊断.md` |
| E06 | Stage 3 compact calibration design | design complete; P1/P2/K1 executed under the registered design | `writing/stage3 design/paper1_stage3_experiment_design.md` |
| E07 | Stage 3 implementation tests | completed for P1, support, P2 raw materialization, and K1; remaining blocks are not yet implemented/run | `tests/stage3/` |
| E08 | Mistral formal judged summary | not located | no current result claim permitted |
| E09 | Stage 3 P1 Qwen calibration measurement | completed; `ESTIMABLE`; prespecified primary gate passed | `results/p1-qwen25-paper-20260807T044847Z/p1_measurement_result.json` |
| E10 | Stage 3 Qwen support and P2 raw paired estimates | completed; A/T supported; raw P2 `ESTIMABLE`; both simultaneous 95% intervals include zero | `results/p2-materialized-qwen25-paper-20260808T051044Z-v1/p2_raw_result.json` |
| E11 | Stage 3 K1 four-cell matched profile | completed; `ESTIMABLE`; descriptive only on the common 951-coordinate frame | `results/k1-materialized-qwen25-paper-20260808T051044Z-v1/k1_result.json` |
| E12 | Accepted amended independent T/H P2 descriptive result, `paper1-stage3-p2-independent-th-v2` (`P2-U(T)` and `P2-B(H)`; `M_T=976`, `M_H=966`; `COMPLETED_PARSED=3942`, `TERMINAL_JUDGE_FAILURE=58`). This is an independent amended P2, not a replacement, correction, or extension of the original P2; descriptive endpoint estimates only; amended P2 statistics, bootstrap, and K1 were not run; `paper_result_eligible=false` | `PARTIAL` (descriptive only; not paper-result eligible) | `.codex-temp/stage3_p2_amended_th_descriptive_report_v1/report.md`; `/data/goodtaste_workspace/paper1_stage3_runs/p2-amended-th-materialized-qwen25-paper-20260822T051005Z-v1/p2_independent_raw_result.json`; amendment: `writing/stage3 design/paper1_stage3_protocol_amendment_p2_v2.md` |

E12 边界：此条目只登记 amended P2，不修改或覆盖原始 P2 证据记录、原始 P2 endpoint、统计结果或结论，也不修改或覆盖 C9 现有原始 P2 主张；原始 P2 与 amended P2 必须分开报告。该条目保留当前协议中的禁止边界，不新增显著性、p 值、置信区间、因果或一般安全结论，也不因结果方向写“支持”或“反对”性质的强主张。

## 主张—证据矩阵

| ID | 论文主张 | 状态 | 当前证据与边界 | 允许的正文措辞 | 更强主张所需条件 |
|---|---|---|---|---|---|
| C1 | `use_cache=True` 下公开 Rogue v1 更接近 prefill-dominant，而非持续 generated-token steering | `SUPPORTED` | E01 直接显示 Qwen `generated_steered_calls=0`；主张限定于所审计公开实现和配置 | `the public v1 implementation is not fully aligned with a literal sustained generation-time interpretation` | 若写跨模型执行语义，补归档 Llama/Mistral phase-call 表 |
| C2 | 在评估的离散强度网格内，持续 decode/full steering 从 attack-success 较高区域转为 high-strength collapse-dominated composition | `SUPPORTED_WITH_BOUNDARY` | E02/E03：Qwen 与 Llama full1000 均出现中强度 attack peak 与 high-strength broken/repetition；仍主要是固定 prompt/layer/vector/decoder 条件 | `within the tested grid, attack success peaks before high-strength outputs become collapse-dominated` | 不得称为已识别的连续 transition point、自然 threshold 或一般 dose-response；多 prompt/层后才能扩大行为范围 |
| C3 | ASR 衡量攻击成功，但不能诊断 non-success 的组成 | `SUPPORTED_WITH_BOUNDARY` | E02/E03/E05 同时报告 unsafe/refusal/safe/broken 与 ARR/repetition | `ASR alone is insufficient for generation-integrity diagnosis` | human validation 后可强化 judge-level measurement validity |
| C4 | Qwen 与 Llama 共享中强度 attack peak、持续 decode 高强度 collapse、first-k/decay 稳定但弱的定性 ordering | `SUPPORTED_WITH_BOUNDARY` | E02/E03 支持共同 ordering，但 onset/严重度、短拒答和 metric artifact 不同 | `the qualitative ordering replicates across Qwen and Llama under the evaluated conditions` | 不要求相同 peak/onset；不得写共同机制或模型排名；若写三模型必须完成 Mistral |
| C5 | Llama 比 Qwen 更易受攻击或更不稳定 | `NOT SUPPORTED` | 峰值、层、模板和输出模式不同，但没有匹配的跨模型脆弱性 estimand/推断 | 只能报告各模型数值和异质性 | 匹配 prompt/layer/dose 加正式跨模型 contrast |
| C6 | first-k/decay 可以减少 collapse | `SUPPORTED_WITH_BOUNDARY` | E02/E03 只支持 `k=3`、`decay=0.85` 的两个固定实例 | `the evaluated first-k and decay settings remained more stable but weak` | sweep 后才能声称 schedule-family 规律 |
| C7 | Qwen/Llama 的 high-strength 低 ASR 主要来自 collapse，而非稳定拒绝增强 | `SUPPORTED_WITH_BOUNDARY` | sustained decode 在 `c=2` 出现约 89%-99% broken，并伴随 repetition | `lower ASR coincides with collapse rather than robust refusal` | 限定当前条件；不可外推所有 activation steering |
| C8 | all-token versus content-token calibration frame 改变 `mu` calibration | `SUPPORTED` | E09：`mu_all_tw=441.4951`、`mu_content_tw=62.1641`；`delta_select_tw=6.1021`，单侧 95% 下界 `6.0529>0.10`，P1 primary gate PASS | `the token frame materially changes the measured calibration scale and intervention-dose geometry under the fixed Qwen setup` | 不得外推为其他模型、层、模板或攻击构造的普遍规律 |
| C9 | calibration estimator 是否对应 Qwen unsafe/broken 行为差异 | `PARTIAL` | E10：`P2-U(A)=+0.01027`，同时 95% CI `[-0.01334,0.03387]`；`P2-B(T)=+0.00410`，CI `[-0.00477,0.01297]`。两区间均包含 0 | `the calibration statistic changes, while the prespecified raw behavioral contrasts remain uncertain` | 完成 fixed720 human validation 和 matched two-phase sensitivity；仍不得将 raw P2 改写为确认性正结果 |
| C10 | Attention Sink 或 structural token 导致跨模型 collapse 差异 | `FORBIDDEN` | 当前设计无 attention-weight 或跨模型 Stage 3 实验；P1/P2 不能支持该因果链 | 不得写结果性或因果性表述 | 需要独立的跨模型 causal design；不属于当前 Stage 3 |
| C11 | 现象已在 Qwen、Llama、Mistral 三模型验证 | `NOT SUPPORTED` | E08 不存在；当前只有 Qwen/Llama formal summary | 写 `across Qwen and Llama` | Mistral config/raw/judged/summary/log 全部归档 |
| C12 | 结论适用于一般 harmful behaviors | `NOT SUPPORTED` | Stage 1/2 当前 full1000 主要来自单 prompt × random vectors | 明确写 conditional evidence | 匹配的多类别、多 prompt 设计与聚类推断 |
| C13 | 结论不依赖特定层 | `NOT SUPPORTED` | 当前主要模型各使用一个固定层 | 把 layer 写入实验边界 | 跨 depth 核心矩阵 |
| C14 | 结论适用于 activation steering 总体，而非 Rogue-style attack family | `NOT SUPPORTED` | 当前只有 Rogue-style random-vector family | 题目/摘要限定 activation-steering implementation audit | 第二独立攻击构造 |
| C15 | benign integrity 或 human validation 已完成 | `DESIGN COMPLETE / NOT RUN` | P1/P2/K1 已完成，但 harmful-clean 50、benign 630 和 fixed720 human validation 尚未运行 | 不得写 benign integrity、judge quality 或 human-corrected P2 已有结果 | 完成剩余 680 个模型响应、fixed720 allocation/annotation 和 two-phase sensitivity |
| C16 | 在所审计实现中，hook scope、mask application 与 KV-cache execution 共同形成 operational phase semantics | `SUPPORTED_WITH_BOUNDARY` | E01 与 A-F instrumentation 直接记录 prefill/cached-decode/full-sequence/generated-token calls | `the realized intervention phase depends on the combined hook, mask, and cache execution semantics` | 限定公开 v1 与审计配置；跨实现规律需要独立 instrumentation |
| C17 | K1 四分类组成描述 | `SUPPORTED_WITH_BOUNDARY` | E11：在四 cell 共同 951 坐标上，T all/content unsafe 为 9.15%/1.47%，refusal 为 69.72%/79.81%；K1 只有 cell-wise 描述性区间 | `at T, the common matched profile descriptively shifts toward more unsafe and less refusal under all-token calibration` | 不得把 K1 cell-wise 区间当成 arm contrast 区间，也不得用 K1 将 P2 升级为检验或确认性结论 |

## 当前允许的模型比较结论

| 比较维度 | Qwen full1000 | Llama full1000 | 允许解释 |
|---|---:|---:|---|
| Rogue peak ASR | 19.4% at `c=1.50` | 27% at `c=1.75` | 两模型都有中高强度 peak，位置和高度不同 |
| decode-only broken at `c=2` | 97% | 89% | sustained cached-decode steering 在两模型均 collapse |
| no-cache/full broken at `c=2` | about 97% | about 99% | full-sequence/sustained steering 的高强度 collapse 跨模型复现 |
| first-k/decay | ASR <=1%，broken 约0% | ASR 约2%，broken 约1% | 当前固定 schedule 更稳定，但攻击较弱 |

这些数值是描述性比较，不是模型排名。1000 个随机向量不等于 1000 个独立 harmful behaviors。

## Stage 3 结果到论文措辞的确定映射

当前已观察分支为：**P1 gate PASS，P2 raw 可估计但两个同时区间均包含 0**。

| Stage 3 结果 | 允许结论 | 禁止结论 |
|---|---|---|
| P1 gate pass，P2 direction/CI 清晰 | token-frame calibration materially changes measured intervention-dose geometry，并对应 fixed-support Qwen outcome differences | structural token/Attention Sink 导致一般 collapse |
| P1 pass，P2 不确定或 non-estimable | calibration statistic changes，behavioral consequence remains uncertain | 用点估计升级为行为机制 |
| P1 gate fail | 在预先规定的 Qwen frame 下未发现 material calibration shift | 搜索新 estimator/anchor 后宣称正结果 |
| human quality gate/CI 失败 | 报告 automated estimate 与明确 limitation | 省略失败并保留强措辞 |

K1 可补充报告四分类组成，但不改变当前分支。T 点 common-frame profile 中的 unsafe/refusal
迁移只能作为描述性结果，不能替代预设 `P2-B(T)` 或其 simultaneous CI。

## 摘要和结论检查表

- [ ] 使用 `Qwen and Llama`，除非 Mistral 正式结果存在。
- [ ] 把 Rogue binary ASR 描述为有效攻击成功指标，而不是错误标签。
- [ ] 把 four-class judge 描述为 failure-aware decomposition，而不是替代原任务。
- [ ] 所有 collapse 结论同时给出 broken/repetition 或相应不确定性。
- [ ] 模型比较只报告共同 ordering 和异质性，不做脆弱性排名。
- [ ] `transition` 只写离散强度网格中的描述性 regime shift，不写已识别 transition point、自然 threshold 或连续 dose-response。
- [ ] 四分类标签本身不宣称为新分类学；创新点是与 binary ASR 联合的 failure-aware protocol。
- [ ] Stage 3 结果只限定于已记录的 Qwen checkpoint/support。
- [ ] 明确写 P1 gate PASS，但 P2 raw 两个 simultaneous CI 均包含 0。
- [ ] K1 只作 common-951 frame 上的四分类描述，不写成新的 P2 endpoint 或确认性 contrast。
- [ ] harmful-clean、benign integrity、fixed720 和 human-corrected sensitivity 仍写为未完成。
- [ ] 不出现 `Attention Sink causes collapse`、`three-model validation` 或 general activation-steering claim。
- [ ] 设计完成、fixture pass 与 paper-run result 三者严格区分。
