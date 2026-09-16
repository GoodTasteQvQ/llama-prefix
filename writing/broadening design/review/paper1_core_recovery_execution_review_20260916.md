# Core recovery execution 任务书审阅

日期：2026-09-16。

## 审阅结论

`EXECUTION_PROMPT_BOUNDARY_PASS`

任务书只允许在负责人书面批准完整存在时运行最多 13 条独立 four-class Judge 请求；批准缺失时 fail-closed。旧 F2、原实验设计、2% missing gate、rubric、parser、decoder、模型和预算均保持不变。

## 边界检查

- [x] 新 run 与旧 F2 ledger 强制隔离。
- [x] 每条输入最多一次请求，binary=0，generation retry=0，额外 retry=0。
- [x] 失败保留为 missing，不手工补标签，不从 generation completion 推断标签。
- [x] 不选择 A/S，不启动正式 evaluation；gate pass 只产生待审状态。
- [x] 要求批准文件包含 run id/path、请求上限、原 rubric、2% gate 和旧 F2 只读承诺。
- [x] Linux/nohup、PID/log/.exit、单卡和项目内临时目录均有约束。
- [x] 未增加数据集、模型、层、prompt、剂量或实验设计内容。

批准前仍保持：`CORE_DOSE_SCREEN_REMAINS_BLOCKED`、`FORMAL_EVALUATION_NOT_RUN`。
