# Recovery executor readiness prompt boundary review

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_judge_protocol_v3_recovery_executor_readiness_prompt_nohup.md`

审查结论：`PASS`

## 必要性

当前通用 Judge 路径仍可能包含旧 retry/legacy parser 语义；proposal 的 13 条
recovery 不能直接复用该路径。先验证或补齐独立 bounded executor，避免未授权请求
和隐性重试。

## 范围

- 只审计/修复 executor 接线和离线测试，真实请求与模型加载严格为 0。
- 不修改 v2.1/v2.3 科学设计、旧 F2、旧 recovery、R2、canonical config 或历史
  ledger；不改变通用旧 runner 的行为。
- 不执行 recovery、full rescore、screen、正式 evaluation、扩展实验或人工审核。

## 边界与证据

- approval 文件由负责人另行提供；任务本身不得创建或猜测批准。
- direct JSON 的 false/1296/parser、decoder 512、13 行上限、一次请求、失败即停、
  raw/diagnostics 和 hash 证据均被写入可验证要求。
- nohup、PID/log/.exit、离线 fixture 和最终 boundary audit 已要求。

## 非过度设计检查

- 没有增加新的数据、模型、审查轮次、实验规模或统计指标。
- 只新增必要的 executor readiness 层；代码修改限制在 direct runtime/executor/对应
  测试，避免把恢复规则扩散到旧流程。
- readiness 通过后仍须重新绑定 code hash 并单独批准 recovery，阶段顺序保持清晰。

结论：任务书可保存并推送。它完成的是 recovery 执行前的实现就绪检查，不等同于
recovery approval 或实验运行。
