# Core Judge v3 direct-JSON budget repair task review

审查日期：2026-09-18
审查结论：`REVIEW_PASS`

## 依据

Phase 1 在首个 Judge 请求前停止：direct-JSON 实现硬性要求 512，而批准配置为
1296；同时预检在本地包导入前以 `ModuleNotFoundError` 退出。模型加载、Judge
请求和重试均为 0，旧实验资产哈希保持一致。因此下一步是离线修复实现契约和
导入路径，不能直接重跑原 probe。

## 最小性与边界

- 只把显式 direct-JSON 预算契约从硬编码 512 修正为批准的 1296，并保留
  legacy 默认 `true/1296/strict_final_json_v1`。
- 只修复仓库根目录下正式 Python 环境的本地包导入预检。
- 保留 strict JSON parser、模型、模板、rubric、decoder、retry、missing gate、
  数据、方向和实验规模。
- 只做离线导入、focused/full tests、compile、diff 检查；不加载模型、不发请求。
- 旧 Phase 1 报告、旧批准文件、旧 F2、旧 recovery、v2 probe 和历史 run 不回写；
  修复后必须重新生成代码哈希并等待新批准文件。

## 过度设计审查

任务没有新增模型、数据集、prompt、请求、统计指标或实验阶段；没有重跑已完成
工作，也没有把 512 的行为 decoder 改为 1296。离线任务不加载模型、不发送
Judge 请求。新增报告和边界审计仅用于证明修复后的代码可被下一份批准文件安全
消费。

结论：`REVIEW_PASS`，可交给服务器 `A-judge-v3-budget-repair` 执行。
