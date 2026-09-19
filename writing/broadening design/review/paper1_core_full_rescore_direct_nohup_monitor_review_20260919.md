# Core 直接 nohup 监控任务书审查

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_full_rescore_direct_nohup_monitor_task.md`

结论：`TASK_PROMPT_REVIEW_PASS`

- 取消了没有科学信息增益、且未实际执行的 CPU probe；已有 readiness/preflight 继续作为 live 前置条件。
- 只允许一次新的 live 提交，使用绝对 Python 路径、明确文件重定向和单卡离线环境；不使用 `nohup.out` 判断成功。
- executor 和 CPU adapter 分离：executor 完成且 accounting 通过后才运行 adapter；失败不重试、不补请求。
- 要求同一会话轮询 PID、日志、run 和 terminal accounting；会话中断后先恢复原状态，禁止盲目重新提交。
- 保持 1,200/20×60、1296 direct JSON、原 retry、2% gate、四组 A/S 和旧输入只读边界；未增加模型、数据、剂量或批准层。
- 要求同步实际 PID/log/exit/monitor、完整 run 和修改文件，避免只交付报告。

未发现过度设计或科学范围漂移，审查通过。
