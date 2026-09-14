# Paper 1 补充实验任务表

设计版本：`MBD-NM v2.1.1-public-pairs`；状态更新：2026-09-14。A2 数量来自已同步报告，原始证据和 B2 修复代码待补交核验；来源扩展尚未完成。

| 模块 | 规模 | 当前状态 | 结果 |
|---|---:|---|---|
| Public safe-pair 数据准备与审核 | 416 对原始 pairs；409 对完成双审核；目标 5 folds + 100 条 development | 阻塞，补交证据并准备少量来源扩展 | A2 报告 221 include / 188 exclude，`actual_k=24<30`，至少还需29条合格新pair；旧194条失效；LICENSE差异已确认为换行问题 |
| Core 方向构造 | Qwen/Llama 各 8 个 Rogue + 5 个 contrastive；核心层分别为 9/11 | 未开始 | 等待 safe-pair gate 和真实运行 gate |
| Core dose screen | 1,200 次 generation | 未开始 | 尚未确定各模型、方向构造的 A/S 剂量 |
| Core 正式评估 | 11,440 次 generation；JBB-100、benign-30；2 模型、2 phase、A/S | 未开始 | 尚无正式 generation、Judge 或 analysis 结果 |
| Core Judge 与统计分析 | four-class Judge；binary Judge 独立记账；paired endpoint + bootstrap | 未开始 | 尚无可报告的 `Delta_unsafe`、`Delta_broken` 或 missingness 结果 |
| Core 人工审核 | 最多 200 条：160 条概率样本 + 40 条诊断样本 | 未开始 | 尚未生成或完成人工审核包 |
| E1 外部提示验证 | HarmBench standard 40 条；2 模型；预算 2,320 次 generation | 资产与临时预筛已完成，实验未开始 | 9 exact / 16 near-match为临时结果；B3核对资产接线，最终safe source分割后重算overlap并确定40条 |
| E2 第三模型验证 | Gemma-2-9B-it；JBB-40；独立 screen 600 次；正式评估 1,160 次 generation | 资产和最小runtime探针通过，实验未开始 | 原生模板/resid_pre/zero-alpha通过，层14；B3核对配置，正式runtime/smoke和剂量gate仍待完成 |
| E3 额外层验证 | Qwen/Llama 各 2 个额外层；screen 1,200 次；正式评估 2,560 次 generation | 未开始 | 等待 Core directions、Core dose 和额外层 screen gate |
| 结果归档与论文数据交接 | 已运行模块的 generation、Judge、analysis、human、provenance | 未开始 | 所有实验结束后生成最终 manifest，并更新结果与主张对应关系 |

## 总规模

| 范围 | Generation 上限 |
|---|---:|
| Core | 12,640 |
| E1/E2/E3 及扩展 screen | 7,840 |
| 合计 | 20,480 |

当前未进入正式 generation。下一步按 [当前任务入口](implementation/paper1_server_codex_post_audit_task_index.md) 并行完成 A3 证据交付、B3 实现交付/资产接线、E 候选来源调查；E 整合/审核须等 A3/B3 通过。数据、E1 overlap 和必要真实运行 gate 通过后，再安排 Core 方向构造和 dose screen。
