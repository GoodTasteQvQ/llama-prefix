# F3/E2 完成后的下一步审阅

日期：2026-09-16。审阅对象：F3 Core screen parse forensic、E2 Gemma release gap audit。

## 已确认事实

- F3：13 条 `PARSE_FAILURE` 全部在既定一次 retry 后仍失败；1,200 logical generation、1,200 首次 Judge、1,213 four-class calls、0 binary calls、0 duplicate identity。F2 异常路径没有持久化 Judge raw/diagnostics，因此旧标签不可恢复。
- E2：Gemma layer-14 方向资产存在，`runtime.release()` 的真实返回值未序列化；F run 的 Gemma release 只能是 `UNVERIFIED_NOT_PASS`。model/tokenizer revision 为 `UNKNOWN`，不能回填。

## 决策

正式实验继续冻结。并行执行两个最小实现任务：

1. F4：修复 Judge 失败路径的 raw/diagnostics 留存，只影响未来 run 的可观测性；不重跑 F2、不新增 Judge 请求。
2. E2R：修复 Gemma release 返回值写回方向记录，只影响未来 run 的 metadata；不重建 F run、不运行 E2。

两项完成并通过离线测试后，再单独编写受限 Core recovery proposal。该 proposal 需要明确新增调用的授权、输入（现有 generation completion）、新 run 与旧 F2 结果的隔离，以及 2% gate 的保持；在 proposal 获批前不执行任何 Judge recovery 或正式 evaluation。

## 边界审计

- 两项任务不改变 parser/rubric、retry、missing 规则、层、模型、模板、decoder、seed、rho、预算或实验设计。
- 两项任务不修改 F2 run、F2 ledger、dose decisions、F source snapshot、E1/C3 派生物、canonical config 或三份原实验设计。
- 只运行项目内离线测试；不下载/加载模型、不使用 GPU、不启动任何正式实验。
- 若实现必须改变科学字段、接受离线推断标签、放宽 2% gate 或重建旧 run，立即标记 `DESIGN_CHANGE_REQUIRED` 并停止。

审阅通过后保存 F4/E2R 任务书。当前仍保留：

`F2_CORE_DOSE_SCREEN_REMAINS_BLOCKED`
`FORMAL_EVALUATION_NOT_RUN`
