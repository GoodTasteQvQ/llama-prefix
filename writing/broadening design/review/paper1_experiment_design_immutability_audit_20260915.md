# 实验设计不可变性审阅

日期：2026-09-15。对象：`MBD-NM v2.1.1-public-pairs` 原实验设计及 A3/B3/E 任务结果。

## 检查结果

1. 设计正文 `paper1_minimal_broadening_experiment_design_no_mistral.md` 的最近一次科学变更来自提交 `6a21b29`：safe-pair source 从历史500条 AI生成文件改为416条公开 paired source，并同步记录动态 `k` 公式、source revision、公开数据审核方式和规模影响。
2. 该变更发生在此前用户明确要求替换未经验证 safe pairs、检查规模并修订实验设计之后；它没有改变模型、层、hook、prompt、decoder、rho、seed、E1/E2/E3矩阵、20,480 logical generation预算或门槛，因此属于必要且合理的 source/design revision，而不是服务器执行时的随意修改。
3. 本轮 A3、B3、E 的报告均声明没有修改科学参数或原设计正文。A3只交付证据，B3只修改实现契约/配置/资产接线，E只调查候选来源并在启动审核前停止；没有证据表明本轮发生了新的设计正文修改。
4. B3的 `B2_DELIVERY_READY` 只代表实现交付和接线可定位；A2 safe-pair gate仍为221条、`k=24`，E1/E2和正式实验仍未通过。不能把实现报告或候选来源调查当作设计批准。

## 今后硬约束

- 服务器 Codex 默认不得编辑或覆盖 `paper1_minimal_broadening_experiment_design_no_mistral.md`、易读版、实现规范或已通过审阅文件。
- source增补、许可/identity修订只能新建独立 revision 文档，记录原因、影响和未改变的科学字段；不得静默改旧 revision。只有实验负责人明确授权后，才可把新 revision绑定到新 run-specific config。
- 实现 bug 修复只能改代码、测试和运行配置；若需要改变 scientific rule、样本规模、模型/层/预算/endpoint，必须停下并报告 `DESIGN_CHANGE_REQUIRED`，等待负责人书面授权。
- 每个后续任务报告都必须列本次修改文件清单，并明确“设计正文未修改”或列出已授权 revision；不能仅凭口头回执声称未改设计。

## 有边界自审

本审阅只比较设计正文的版本历史、A3/B3/E报告和任务范围；没有扩大为重新审阅实验科学合理性。结论：`DESIGN_IMMUTABILITY_AUDIT_PASS`。当前正式实验仍为 `FORMAL_EXPERIMENTS_NOT_RUN`。
