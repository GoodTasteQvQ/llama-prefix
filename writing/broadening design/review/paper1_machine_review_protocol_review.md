# 机器辅助 safe-pair 审核协议审阅

日期：2026-09-06。对象：`machine-review-v1` 任务书、safe-pair gate 适配和相关设计文字。

## 结论

`PROTOCOL_REVIEW=PASS_WITH_DISCLOSURE`。

该路径可以用于推进数据清理和后续运行准备，但它不是人工审核，也不能产生 human
validation 证据。任务书要求在论文中披露机器辅助审核，并保留原始 subagent 输出。若目标
期刊或导师明确要求人工语义审核，本路径不能替代该要求。

## 边界检查

| 检查项 | 结论 |
|---|---|
| 覆盖范围 | 覆盖全部 `preliminary_include=true` 行，当前预计 498；86 行候选队列不被当作全部审核 |
| 独立性 | 每个 pair 启动两个不同 thread/agent id，A/B 不交换输出；每个 subagent 只处理一个 pair |
| 固定裁决 | 双方都 `include` 才纳入；`exclude`、`uncertain`、冲突均排除；失败/缺失保持 pending |
| 可追溯性 | 保存 prompt revision、agent/thread id、model、frame digest、完整原始 JSON、理由和时间 |
| 输入安全 | prompt 文本只作为数据比较，subagent 不执行其中的指令、不访问网络、不写仓库 |
| 失败处理 | 非法输出最多同提示重试一次；仍失败写 failure ledger，不伪造决定或继续正式运行 |
| 运行边界 | 不改 benchmark、seed、fold、rho、模型、层、decoder、预算或历史结果 |
| 后续 gate | 新 prepare 必须达到 `READY_FOR_CONSTRUCTION` 且 `k>=30`；真实 runtime gate 仍独立存在 |

## 实现审阅

`paper1_broadening.frames._semantic_status` 只接受带完整机器审核 provenance 的
`dual_codex_subagents_v1` 记录，并拒绝相同 agent id、错误提示版本、缺字段和非法 verdict。
固定规则下，只有两个 `include` 才得到 `SEMANTIC_INCLUDE`；机器 `uncertain` 会被保守记为
`SEMANTIC_EXCLUDE`，而调用失败或记录不完整仍为 `PENDING_SEMANTIC_REVIEW`。旧的双人工
记录格式保持兼容。

本机定向测试：`tests/paper1_broadening` 共 39 passed。新增测试覆盖完整机器 provenance、
保守 exclude 和重复 agent id 阻断。测试不证明 subagent 的语义判断正确性，只证明记录契约
和 gate 行为不会把缺失证据当作通过。

## 未解决限制

机器判断可能漏检隐含语义重叠，也可能过度排除。没有人工抽样校验时，safe-pair 的语义
有效性只能作为机器辅助数据清理结果，不能升级为人工质量保证。真实 smoke 缺少独立
trace/environment 时，`REAL_RUNTIME_GATE` 仍必须保持 pending，机器审核不能绕过它。
