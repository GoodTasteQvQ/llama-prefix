# Core Judge protocol v3 direct-JSON probe task review

审查日期：2026-09-18
审查结论：`REVIEW_PASS`

## 审查依据

Phase 0 报告为 `DIRECT_JSON_IMPLEMENTATION_OFFLINE_PASS`，聚焦测试 45 passed，
完整测试 85 passed，编译和 diff 检查通过。最终边界审计为 PASS，模型加载和
Judge 请求均为 0；历史设计、旧 F2、旧 recovery、v2 probe 均保持不变。

## 边界审查

- probe 仅使用原 v2 probe 的 6 条固定输入，最多 6 次请求。
- 每条最多一次 four-class 请求，binary/generation/additional retry 均为 0。
- Phase 0 离线实现检查使用 `max_new_tokens=512`；本次 probe 固定使用
  `enable_thinking=false`、`max_new_tokens=1296` 和
  `strict_direct_json_v1`。不提高到 1296 以上，不切回 thinking。
- 发送请求前必须核验 resolved config、Judge identity 和 diagnostics 的实际
  budget 均为 1296；若仍为 512 或其他值，fail-closed 停止且不发送请求。
- 任一条失败立即停止；不发送剩余请求，不创建 recovery 或 full-rescore run。
- Probe 通过后只停在 `READY_FOR_V2.3_DESIGN_REVIEW`，v2.3 设计、recovery、
  全量重评分和正式实验仍需后续批准。
- direct JSON 严格要求两个键、合法 label、非空 rationale，并拒绝额外文本、
  fences、thinking marker 和 parser fallback。
- v2.1、旧 F2、旧 recovery、旧 ledger、canonical config 和 v2 probe 均只读。

## 过度设计审查

任务不增加模型、数据集、prompt、方向、剂量、统计指标或人工审核，不重复生成
behavior completion，也不执行无关的正式实验。新建独立 probe run 和完整证据
清单是验证输出协议所必需的最小记录。

结论：`REVIEW_PASS`，可交给服务器 `A-judge-v3` 执行。
