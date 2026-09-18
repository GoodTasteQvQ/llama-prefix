# Core Judge protocol v3 direct-JSON R2 probe task review

审查日期：2026-09-18
审查结论：`REVIEW_PASS`

## 依据

预算修复报告和边界审计确认：direct-JSON 现在严格解析为
`enable_thinking=false`、`max_new_tokens=1296`、`strict_direct_json_v1`；
legacy 默认仍为 `true/1296/strict_final_json_v1`。聚焦测试 38 passed，完整
`tests/paper1_broadening` 为 87 passed，导入预检、编译和 diff 检查通过，模型
加载和 Judge 请求均为 0。旧 R1 批准因代码哈希变化失效。

## R2 边界

- 只使用旧 F2 中原 probe 的六条固定输入，最多六次 four-class Judge 请求。
- 使用修复后的八个代码哈希和独立 `DIRECT_JSON_PROBE_APPROVAL_R2.md`；不使用
  旧 R1 批准或旧 R1 run。
- 预算固定为 1296，无 thinking、binary Judge、generation retry 或 additional
  retry；首条失败立即停止。
- 发送前再次核验 resolved config、Judge identity 和 diagnostics 均为 1296。
- 不创建 v2.3 设计，不执行 recovery、full rescore、A/S 选择、正式 evaluation、
  E1/E2/E3、analysis 或 human review。
- 旧 F2、旧 recovery、v2 probe、v2.1 设计、canonical config、方向、safe-pair
  数据和 behavior completion 只读。

## 过度设计审查

R2 只验证修复后的 Judge 输出协议能否在真实模型上产生严格 JSON；没有新增模型、
数据集、prompt、统计指标或实验规模，也没有重跑旧请求。独立 run、raw/diagnostic
证据和边界审计是验证该协议所需的最小记录。

结论：`REVIEW_PASS`，可交给服务器 `A-judge-v3-r2` 执行。
