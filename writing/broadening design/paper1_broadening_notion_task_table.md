# Paper 1 补充实验任务表

设计正文：`MBD-NM v2.1.1-public-pairs`；服务器已登记独立来源修订 `v2.1.2-public-pairs-expanded`。状态更新：2026-09-15，已同步 C3、B5 与 Core direction/calibration 三份回执；本表记录执行进度，不修改科学设计。

| 模块 | 规模 | 当前状态 | 结果 |
|---|---:|---|---|
| Public safe-pair 数据准备与审核 | 516对source；509对经双审核；300对可执行；5×40 construction + 100 development | 数据gate通过 | 新增100对中79 include/21 exclude；合计300 include/209 exclude，k=40、unused=0；不再补来源或重审 |
| 运行准备与代码交付 | E新增identity/config/snapshot适配；core smoke最多24 generation+4 Judge，预算单列 | B4、C3、B5完成 | `CODE_CONTRACT_PASS`；`CORE_REAL_SMOKE_PASS/NON_EVIDENCE`；E1 final consumer 为 `READY_FOR_RUN`，仅新增 run-specific config |
| E1 消费收尾 | 200候选；9 exact；17 near；180 include；最终40条 | `E1_CONSUMER_PASS` / `E1_FRAME_READY` / `READY_FOR_RUN` | 最终 digest=`d148...732a`；6类覆盖；C3 final 保留旧 provisional，B5 纯 CPU 复核通过；尚未进行 E1 generation |
| Core 方向构造与 calibration | Qwen/Llama 各 8 个 Rogue + 5 个 contrastive；核心层分别为 9/11 | `CORE_DIRECTIONS_READY` | 已完成 `prepare + build-directions`；Qwen `mu_content=56.86973966266515`（1172 tokens），Llama `7.615247755784255`（1170 tokens）；fold/sign/float32 unit-norm/runtime identity 已审计 |
| Core dose screen | 1,200 次 generation | 未开始 | 尚未确定各模型、方向构造的 A/S 剂量 |
| Core 正式评估 | 11,440 次 generation；JBB-100、benign-30；2 模型、2 phase、A/S | 未开始 | 尚无正式 generation、Judge 或 analysis 结果 |
| Core Judge 与统计分析 | four-class Judge；binary Judge 独立记账；paired endpoint + bootstrap | 未开始 | 尚无可报告的 `Delta_unsafe`、`Delta_broken` 或 missingness 结果 |
| 输出人工审核 | Core最多200条（160概率+40诊断）；E1/E2/E3各40条，总上限320 | 未开始 | 输出生成及自动判断后制作盲标包；safe-pair机器审核不替代本项人审 |
| E1 外部提示验证 | HarmBench standard 40条；2模型；预算2,320次generation | frame ready；正式验证未开始 | 40条已选且6类覆盖；consumer 已通过，待 Core dose 锁定后以 final E1 frame 运行 |
| E2 第三模型验证 | Gemma-2-9B-it；JBB-40；独立screen600次；正式评估1,160次generation | 自动方向资产完成；正式实验未开始 | 层14；已构造4 Rogue + 5 contrastive，但 Gemma release 未序列化是记录缺口；仍需 screen、必要 phase 核验和独立剂量 |
| E3 额外层验证 | Qwen/Llama 各 2 个额外层；screen 1,200 次；正式评估 2,560 次 generation | 自动方向资产完成；正式实验未开始 | Qwen层7/20、Llama层8/23 已构造；仍等待 Core dose 和额外层 screen gate |
| 结果归档与论文数据交接 | 已运行模块的 generation、Judge、analysis、human、provenance | 未开始 | 所有实验结束后生成最终 manifest，并更新结果与主张对应关系 |

## 总规模

| 范围 | Generation 上限 |
|---|---:|
| Core | 12,640 |
| E1/E2/E3 及扩展 screen | 7,840 |
| 合计 | 20,480 |

当前顺序为 Core development screen（另行授权并锁定 A/S）-> Core evaluation/Judge/分析 -> E1 -> E2 -> E3 -> human audit/archive。C3、B5 与 Core prepare/build-directions/calibration 已完成；正式 generation 预算仍为20,480，smoke、技术重试和 Judge 单独记账。详见 [当前任务入口](implementation/paper1_server_codex_post_audit_task_index.md)。
