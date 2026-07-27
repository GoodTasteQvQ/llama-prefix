# Paper 1 Claim-Evidence Matrix

更新时间：2026-07-22

状态：当前写作和结果解释的唯一主张边界。它更新 `paper1_tdsc_readiness_audit.md`
中 2026-07-16 的历史矩阵，但不覆盖或改写该历史审计。

## 状态定义

- `SUPPORTED`：已有本地可复核结果，可在限定边界内写入正文。
- `SUPPORTED_WITH_BOUNDARY`：方向已有证据，但只能使用矩阵中的限定措辞。
- `PARTIAL`：已有先导或描述性证据，尚不能作为强结论。
- `DESIGN_FROZEN / NOT RUN`：协议已冻结，但没有正式结果。
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
| E06 | Stage 3 compact calibration design | design-frozen, no formal results | `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc2.md` |
| E07 | Stage 3 design release verification | `DESIGN-FREEZE-PASS` | `writing/stage3 design/v3_5_rc2_contracts/v3_5_rc2_static_verification_report.json` |
| E08 | Mistral formal judged summary | not located | no current result claim permitted |

## 主张—证据矩阵

| ID | 论文主张 | 状态 | 当前证据与边界 | 允许的正文措辞 | 更强主张所需条件 |
|---|---|---|---|---|---|
| C1 | `use_cache=True` 下公开 Rogue v1 更接近 prefill-dominant，而非持续 generated-token steering | `SUPPORTED` | E01 直接显示 Qwen `generated_steered_calls=0`；主张限定于所审计公开实现和配置 | `the public v1 implementation is not fully aligned with a literal sustained generation-time interpretation` | 若写跨模型执行语义，补归档 Llama/Mistral phase-call 表 |
| C2 | `decode_only/full/no_cache` 在高强度下诱发 generation collapse | `SUPPORTED_WITH_BOUNDARY` | E02/E03：Qwen 与 Llama full1000 均出现 high broken/repetition；仍主要是给定 prompt/layer | `under the evaluated prompt, layer, vector distribution, and decoder` | 多 prompt/层后才能写一般 harmful-behavior 结论 |
| C3 | ASR 衡量攻击成功，但不能诊断 non-success 的组成 | `SUPPORTED_WITH_BOUNDARY` | E02/E03/E05 同时报告 unsafe/refusal/safe/broken 与 ARR/repetition | `ASR alone is insufficient for generation-integrity diagnosis` | human validation 后可强化 judge-level measurement validity |
| C4 | Qwen 与 Llama 共享 phase/cache 的定性 ordering | `SUPPORTED_WITH_BOUNDARY` | Rogue 有中高强度 peak；持续 decode 高强度 collapse；first-k/decay 稳定但弱 | `the qualitative ordering replicates across Qwen and Llama` | 不要求相同峰值；若写三模型则必须完成 Mistral |
| C5 | Llama 比 Qwen 更易受攻击或更不稳定 | `NOT SUPPORTED` | 峰值、层、模板和输出模式不同，但没有匹配的跨模型脆弱性 estimand/推断 | 只能报告各模型数值和异质性 | 匹配 prompt/layer/dose 加正式跨模型 contrast |
| C6 | first-k/decay 可以减少 collapse | `SUPPORTED_WITH_BOUNDARY` | E02/E03 只支持 `k=3`、`decay=0.85` 的两个固定实例 | `the evaluated first-k and decay settings remained more stable but weak` | sweep 后才能声称 schedule-family 规律 |
| C7 | Qwen/Llama 的 high-strength 低 ASR 主要来自 collapse，而非稳定拒绝增强 | `SUPPORTED_WITH_BOUNDARY` | sustained decode 在 `c=2` 出现约 89%-99% broken，并伴随 repetition | `lower ASR coincides with collapse rather than robust refusal` | 限定当前条件；不可外推所有 activation steering |
| C8 | structural/content token inclusion 改变 `mu` calibration | `DESIGN_FROZEN / NOT RUN` | E06/E07 已冻结 P1，但尚无 formal norm outcome | 只能写研究问题和方法 | P1 正式结果及预注册 gate |
| C9 | calibration estimator 改变 Qwen unsafe/broken 结果 | `DESIGN_FROZEN / NOT RUN` | E06 已定义 Qwen A/T paired RD，无 formal P2 结果 | 只能写 planned fixed-support estimation | P2/CI 与 matched human sensitivity 完成 |
| C10 | Attention Sink 或 structural token 导致跨模型 collapse 差异 | `FORBIDDEN` | rc2 无 attention-weight 或跨模型 Stage 3 设计；P1/P2 不能支持该因果链 | 不得写结果性或因果性表述 | 需要独立预注册的跨模型 causal design；不属于 rc2 |
| C11 | 现象已在 Qwen、Llama、Mistral 三模型验证 | `NOT SUPPORTED` | E08 不存在；当前只有 Qwen/Llama formal summary | 写 `across Qwen and Llama` | Mistral config/raw/judged/summary/log 全部归档 |
| C12 | 结论适用于一般 harmful behaviors | `NOT SUPPORTED` | Stage 1/2 当前 full1000 主要来自单 prompt × random vectors | 明确写 conditional evidence | 匹配的多类别、多 prompt 设计与聚类推断 |
| C13 | 结论不依赖特定层 | `NOT SUPPORTED` | 当前主要模型各使用一个固定层 | 把 layer 写入实验边界 | 跨 depth 核心矩阵 |
| C14 | 结论适用于 activation steering 总体，而非 Rogue-style attack family | `NOT SUPPORTED` | 当前只有 Rogue-style random-vector family | 题目/摘要限定 activation-steering implementation audit | 第二独立攻击构造 |
| C15 | benign integrity 或 human validation 已完成 | `DESIGN_FROZEN / NOT RUN` | E06 包含 benign 与 720-item human design，但无 formal outcome | 不得写已有结果 | 完成 Stage 3 execution、sample lock 和 annotation |

## 当前允许的模型比较结论

| 比较维度 | Qwen full1000 | Llama full1000 | 允许解释 |
|---|---:|---:|---|
| Rogue peak ASR | 19.4% at `c=1.50` | 27% at `c=1.75` | 两模型都有中高强度 peak，位置和高度不同 |
| decode-only broken at `c=2` | 97% | 89% | sustained cached-decode steering 在两模型均 collapse |
| no-cache/full broken at `c=2` | about 97% | about 99% | full-sequence/sustained steering 的高强度 collapse 跨模型复现 |
| first-k/decay | ASR <=1%，broken 约0% | ASR 约2%，broken 约1% | 当前固定 schedule 更稳定，但攻击较弱 |

这些数值是描述性比较，不是模型排名。1000 个随机向量不等于 1000 个独立 harmful behaviors。

## Stage 3 结果到论文措辞的确定映射

| Stage 3 结果 | 允许结论 | 禁止结论 |
|---|---|---|
| P1 gate pass，P2 direction/CI 清晰 | token-frame calibration materially changes measured dose，并对应 fixed-support Qwen outcome differences | structural token/Attention Sink 导致一般 collapse |
| P1 pass，P2 不确定或 non-estimable | calibration statistic changes，behavioral consequence remains uncertain | 用点估计升级为行为机制 |
| P1 gate fail | 在预注册 Qwen frame 下未发现 material calibration shift | 搜索新 estimator/anchor 后宣称正结果 |
| human quality gate/CI 失败 | 报告 automated estimate 与明确 limitation | 省略失败并保留强措辞 |

## 摘要和结论检查表

- [ ] 使用 `Qwen and Llama`，除非 Mistral 正式结果存在。
- [ ] 把 Rogue binary ASR 描述为有效攻击成功指标，而不是错误标签。
- [ ] 把 four-class judge 描述为 failure-aware decomposition，而不是替代原任务。
- [ ] 所有 collapse 结论同时给出 broken/repetition 或相应不确定性。
- [ ] 模型比较只报告共同 ordering 和异质性，不做脆弱性排名。
- [ ] Stage 3 结果只限定于 frozen Qwen checkpoint/support。
- [ ] 不出现 `Attention Sink causes collapse`、`three-model validation` 或 general activation-steering claim。
- [ ] 设计完成、fixture pass 与 formal experiment result 三者严格区分。
