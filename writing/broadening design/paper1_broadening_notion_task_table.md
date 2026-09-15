# Paper 1 补充实验任务表

设计正文：`MBD-NM v2.1.1-public-pairs`；服务器已登记独立来源修订 `v2.1.2-public-pairs-expanded`。状态更新：2026-09-15，依据最终恢复报告；代码/数据和来源修订原件尚待同步。本表记录执行进度，不修改科学设计。

| 模块 | 规模 | 当前状态 | 结果 |
|---|---:|---|---|
| Public safe-pair 数据准备与审核 | 516对source；509对经双审核；300对可执行；5×40 construction + 100 development | 数据gate通过 | 新增100对中79 include/21 exclude；合计300 include/209 exclude，k=40、unused=0；不再补来源或重审 |
| 运行准备与代码交付 | E新增identity/config/snapshot适配；core smoke最多24 generation+4 Judge，预算单列 | B4通过；E1消费待C3/B5 | `CODE_CONTRACT_PASS`；`CORE_REAL_SMOKE_PASS/NON_EVIDENCE`；最终digest绑定后进入正式run |
| E1 消费收尾 | 200候选；9 exact；17 near；最终40条 | C2完成，B4拒绝旧digest；待C3/B5 | 不重审；重建同一最终reference digest的derived ledger/selection，CPU验证`READY_FOR_RUN` |
| Core 方向构造与 calibration | Qwen/Llama 各 8 个 Rogue + 5 个 contrastive；核心层分别为 9/11 | 可在B5通过后开始 | prepare后运行build-directions；记录mu_content、fold、sign和实际E2/E3自动接入状态 |
| Core dose screen | 1,200 次 generation | 未开始 | 尚未确定各模型、方向构造的 A/S 剂量 |
| Core 正式评估 | 11,440 次 generation；JBB-100、benign-30；2 模型、2 phase、A/S | 未开始 | 尚无正式 generation、Judge 或 analysis 结果 |
| Core Judge 与统计分析 | four-class Judge；binary Judge 独立记账；paired endpoint + bootstrap | 未开始 | 尚无可报告的 `Delta_unsafe`、`Delta_broken` 或 missingness 结果 |
| 输出人工审核 | Core最多200条（160概率+40诊断）；E1/E2/E3各40条，总上限320 | 未开始 | 输出生成及自动判断后制作盲标包；safe-pair机器审核不替代本项人审 |
| E1 外部提示验证 | HarmBench standard 40条；2模型；预算2,320次generation | overlap审核完成；消费待C3/B5 | 40条已选且6类覆盖；最终derived ledger与run frames通过后复用Core剂量 |
| E2 第三模型验证 | Gemma-2-9B-it；JBB-40；独立screen600次；正式评估1,160次generation | 资产接线和最小runtime探针完成 | 层14；仍需正式方向/校准、必要phase核验和独立剂量；不重下载或重复零剂量探针 |
| E3 额外层验证 | Qwen/Llama 各 2 个额外层；screen 1,200 次；正式评估 2,560 次 generation | 未开始 | 等待 Core directions、Core dose 和额外层 screen gate |
| 结果归档与论文数据交接 | 已运行模块的 generation、Judge、analysis、human、provenance | 未开始 | 所有实验结束后生成最终 manifest，并更新结果与主张对应关系 |

## 总规模

| 范围 | Generation 上限 |
|---|---:|
| Core | 12,640 |
| E1/E2/E3 及扩展 screen | 7,840 |
| 合计 | 20,480 |

当前顺序为 C3 E1 派生物收尾 -> B5 CPU consumer handoff -> Core prepare/build-directions/calibration -> Core development screen -> Core evaluation/Judge/分析 -> E1 -> E2 -> E3 -> human audit/archive。正式generation预算仍为20,480；smoke、技术重试和Judge单独记账。详见 [当前任务入口](implementation/paper1_server_codex_post_audit_task_index.md)。
