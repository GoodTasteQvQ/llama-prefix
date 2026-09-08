# Paper 1 补充实验任务表

设计版本：`MBD-NM v2.1.1-public-pairs`

| 模块 | 规模 | 当前状态 | 结果 |
|---|---:|---|---|
| Public safe-pair 数据准备与审核 | 416 对原始 pairs；5 个 construction folds；100 条 development | 阻塞 | source bundle license hash 不一致；双审核后可执行数量不足，`actual_k=18<30`，未通过 construction gate |
| Core 方向构造 | Qwen/Llama 各 8 个 Rogue + 5 个 contrastive；核心层分别为 9/11 | 未开始 | 等待 safe-pair gate 和真实运行 gate |
| Core dose screen | 1,200 次 generation | 未开始 | 尚未确定各模型、方向构造的 A/S 剂量 |
| Core 正式评估 | 11,440 次 generation；JBB-100、benign-30；2 模型、2 phase、A/S | 未开始 | 尚无正式 generation、Judge 或 analysis 结果 |
| Core Judge 与统计分析 | four-class Judge；binary Judge 独立记账；paired endpoint + bootstrap | 未开始 | 尚无可报告的 `Delta_unsafe`、`Delta_broken` 或 missingness 结果 |
| Core 人工审核 | 最多 200 条：160 条概率样本 + 40 条诊断样本 | 未开始 | 尚未生成或完成人工审核包 |
| E1 外部提示验证 | HarmBench standard 40 条；2 模型；预算 2,320 次 generation | 资产已准备，实验未开始 | CSV、metadata 和来源已准备；仍需完成 overlap gate，未固定最终 40 条 |
| E2 第三模型验证 | Gemma-2-9B-it；JBB-40；独立 screen 600 次；正式评估 1,160 次 generation | 资产已准备，实验未开始 | checkpoint、tokenizer 和分片已核验；仍需 runtime/smoke 和独立 dose screen |
| E3 额外层验证 | Qwen/Llama 各 2 个额外层；screen 1,200 次；正式评估 2,560 次 generation | 未开始 | 等待 Core directions、Core dose 和额外层 screen gate |
| 结果归档与论文数据交接 | 已运行模块的 generation、Judge、analysis、human、provenance | 未开始 | 所有实验结束后生成最终 manifest，并更新结果与主张对应关系 |

## 总规模

| 范围 | Generation 上限 |
|---|---:|
| Core | 12,640 |
| E1/E2/E3 及扩展 screen | 7,840 |
| 合计 | 20,480 |

当前实验尚未进入正式 generation 阶段。下一项任务是修复 public safe-pair source gate，重新生成通过 `actual_k>=30` 的 prepare 结果；之后才能开始 Core 方向构造和 dose screen。
