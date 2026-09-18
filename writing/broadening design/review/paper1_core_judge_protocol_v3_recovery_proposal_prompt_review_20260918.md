# Core Judge protocol v3 recovery proposal task review

审查日期：2026-09-18
审查结论：`REVIEW_PASS`

## 依据

R2 probe 已 6/6 通过，v2.3 design/config 已完成且离线测试通过；两者均明确未执行
recovery。旧 F2 中有 13 条解析失败输入，下一阶段需要独立 recovery，不能把新协议
直接混入旧 ledger。

## 边界审查

- 当前任务只读旧 F2 和 v2.3/R2 资产，冻结 13 条输入并生成 proposal。
- 实际 Judge 请求为 0；不加载模型，不创建 active approval，不运行 recovery。
- 未来 recovery 上限固定为 13 次 four-class request，零 binary、generation retry
  和 additional retry；使用 direct JSON 1296，失败即停。
- 旧 1,187 条成功记录、旧 13 条失败记录和新 recovery ledger 分开保存，旧文件不回写。
- 记录 416 base source 与 516 expanded overlay 的差异，防止后续设计/数据混写；这不
  会改变 recovery 输入或实验预算。

## 过度设计审查

任务没有新增模型、数据集、prompt、方向、剂量、统计指标或正式实验。冻结 manifest、
hash 和 overlay 记录是获得可审查 recovery approval 所需的最小证据。

结论：`REVIEW_PASS`，可交给服务器 `A-core-recovery-v3-proposal` 执行。
