# Paper 1 补充实验设计审阅

日期：2026-09-05  
对象：[实验设计](../paper1_minimal_broadening_experiment_design_no_mistral.md)

版本：`MBD-NM v2.1-ccf-a-target`  
结论：**PASS，限文档设计一致性；真实运行仍有资产、人审和 smoke 前提。**

## 审阅范围和依据

这是本次修改后的有边界自审，非独立同行评审，不表示实验已运行、CCF-A 已达标或导师已经
批准。检查研究问题、预算、数据角色、条件控制、统计、人审、版本追溯及过度设计。
依据现有主张矩阵、蓝图和落地结果，未使用旧未审核补充协议决定新实验范围。
未进行最新相关工作的系统检索或完整稿件同行评审，不能据本次自审认证 A 类竞争力。

核对到的当前状态：

| 本地证据 | 本次确认 |
|---|---|
| `data/jbb_behaviors_harmful.json` | 100 条、10 categories |
| `data/safe_pairs.json` | 500 pairs、harmful normalized unique=500；harmful 与 JBB normalized exact overlap=0，语义重叠未确认 |
| `results/harmful-clean-materialized-qwen25-paper-20260825T071017Z-v1/harmful_clean_result.json` | 50 scheduled/parsed，38 refusal、12 safe；仍为 descriptive，paper_result_eligible=false |
| `results/benign-integrity-materialized-qwen25-paper-recovery-20260825T102609Z-v2/benign_integrity_result.json` | 630 scheduled，629 parsed，1 terminal Judge failure；不得当成无缺失的新推断结果 |
| `results/fixed720-selection-owner-run/fixed720_selection.json` | 720 条 selection 已完成；不是 720 条人工标签已完成 |
| E1/E2 | 当前仓库未找到已登记 external/Gemma 资产；没有声称远端机器不存在 |

## 发现与修正

1. **把实验覆盖误当 CCF 分数。** 删除“所有扩展为正且 gate 通过才允许称 A，否则 B/C”规则。
   现在将 B 为主要目标、C 为备选表述为规划判断；A 需结合贡献新颖性、重要性和完整稿件。
   负结果或异质性也可以是论文贡献，不由程序决定等级。
2. **预算重复乘 family，且漏算跨层 screen。** `(4+3)` 已包含两 family。重新计算 E1/E2，
   加回四层 screen；增加 E1/E2 共 120 条 clean 基线。最终核心 12,640，扩展 7,840，
   总共 20,480 条逻辑 generation 上限。Judge、smoke、retry、activation forwards 单列。
3. **跨层比较方向也改变。** E3 改为复用同模型核心前 4 个向量；每层独立 mu/A/S，主张明确
   为条件化离散层结果。核心层从已有 core 子集取，不重复生成。
4. **外部类别要求和资产未定义。** 明确 E1 首选 HarmBench 标准文本，40 条、至少 4 个原生
   类别；不强制数据源提供 8 个类别或发明分类。固定轮转取样、来源/overlap gate。
   E2 首选 Gemma-2-9B-it，核心及 E3 层索引公式固定，实际 L 运行前解析。
5. **500 pairs 一旦排除一条便强制补数据。** 固定 100 development，其余按确定公式形成
   五折，每折 30-80；保留数据角色隔离，不需要为了轻微去重另造数据。
6. **人审少量样本被用于过强验证。** 160 概率样本与 40 标签定向诊断分开；extension 的
   40/block 用整数配额轮转并保留 N/n。估计加权，gold 样本不足不视为通过，不以小样本
   端点方向一致验证全体模型/层。新增人审仍上限 320，不自动扩充。
7. **missing 与 broken、技术 gate 与负结果混淆。** 空短输出合法送 Judge，broken 为有效
   类别；screen/终端/paired missing 均有分母和 2% 门槛。符号未验证和 ordering 未建立
   记录科学限制，不能自动改向量/网格。
8. **哈希冻结与迭代冲突。** 运行前只保存实际输入/配置/设计/源码副本和轻量身份；SHA256
   结果落地后生成。Analysis bug 可做新分析 revision，不为文字/分析修订重跑无关原始生成。

## 预算复核

| 项目 | 算式 | 数量 |
|---|---|---:|
| Core screen | 2*2*5*20*3 | 1,200 |
| Core harmful | 2*2*2*100*(8+5)+2*100 | 10,600 |
| Core benign | 2*30*(8+5)+2*30 | 840 |
| E1 including clean | 2*2*2*40*(4+3)+2*40 | 2,320 |
| E2 including clean | 1*2*2*40*(4+3)+40 | 1,160 |
| E3 | 2*2*4*2*2*40 | 2,560 |
| E2/E3 screen | 1*2*5*20*3+2*2*5*20*3 | 1,800 |
| **总计** | | **20,480** |

这不是实际 GPU 时间或 token 成本估计。A=S 去重、失败、short-rule 和重试会改变物理调用数，
必须在运行计划/accounting 中单列。Four-class Judge 与 Rogue binary 不能假定总共一次调用。

## 通过后的边界

设计范围只有 core + E1/E2/E3，不含 Mistral、全层 sweep、第二外部 benchmark、新防御或
优化攻击。通过的是文件内部的可执行性和解释边界，不是论文结果的保证：

- 单一固定网格可能无法建立 A/S；尤其不能把新的 content rho 与历史 all-token c 等同。
  不预先宣称一定出现 collapse，也不在 evaluation 后加点挽救正结果。
- 3-8 个方向、40 条外部 prompts 和 few-category bootstrap 没有充分 power 保证；其 CI
  只是有限 frame 的重采样区间。零效应区间宽应如实报告。
- 40 条 extension 人审不足以验证每个 strata；相关主张需受实际 gold 类别数与错分约束。
- E1/E2 资产、语义 overlap、真实 cache smoke 尚未通过；失败只阻塞对应运行/主张。
- Two direction constructions 仍不等于所有 attack families，三 checkpoint 仍不等于所有模型。

本轮到此结束设计扩展。先按明确范围实现与执行，再依完整结果及目标场所选定投稿，不为
“A 类”继续无边界堆实验。设计可以用于下一步实现，但不能作为 CCF-A 接收或论文分数证明。

静态验证记录：PowerShell 独立重算总预算 20,480；四份交付文档的版本、预算字符串、内部
Markdown 链接与代码围栏均通过检查。没有运行新实验或生产代码测试。
