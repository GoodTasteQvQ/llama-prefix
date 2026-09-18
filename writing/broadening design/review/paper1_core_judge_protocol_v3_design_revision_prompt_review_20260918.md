# Core Judge protocol v3 v2.3 design revision task review

审查日期：2026-09-18
审查结论：`REVIEW_PASS`

## 依据

R2 报告记录 `DIRECT_JSON_PROBE_PASS`：6 条固定输入全部成功，6 次 four-class
请求，binary/generation/additional retry 均为 0；19/19 边界检查通过，45 项
artifact hash 校验通过。R2 明确未创建 v2.3、recovery、full rescore 或正式实验。

## 任务边界

- 只创建 v2.1 的 v2.3 direct-JSON 版本化副本和一个 run-specific config。
- 设计正文、数据、模型、层、方向、剂量、generation budget、统计指标和扩展
  规模保持不变；只记录 Judge protocol revision。
- config 只改变版本标识和 Judge 的 `false/1296/strict_direct_json_v1`；behavior
  decoder 仍为 512，不能误改。
- 只做文本/config/loader/离线测试和 hash 审计；不加载模型、不发送请求，不创建
  recovery 或 full-rescore 批准。
- 任务完成状态应为 `DESIGN_REVISION_V2.3_WRITTEN`、
  `DIRECT_JSON_PROBE_PASS_REFERENCE_ONLY`、`FORMAL_EVALUATION_NOT_RUN` 和
  `READY_FOR_RECOVERY_APPROVAL`；任何失败都停止并写 `DESIGN_CHANGE_REQUIRED`。
- v2.1、canonical config、R2 run、旧 F2/recovery/v2 probe 只读。

## 过度设计审查

任务没有新增模型、数据集、prompt、方向 family、剂量、统计方法或实验规模；没有
重复 R2 请求，也没有提前执行下一阶段。两个新文件和对应 hash/config-diff 证据
是让后续 recovery 使用版本固定协议所需的最小产物。

结论：`REVIEW_PASS`，可交给服务器 `A-judge-v3-design-revision` 执行。
