# Core full rescore 启动修复任务书审查

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_full_rescore_launch_repair_prompt_nohup.md`

审查版本：`core-full-rescore-launch-repair-v2`

结论：`TASK_PROMPT_REVIEW_PASS`

审查结论：

- 仅修复上一轮 `nohup` 的启动/重定向问题；不修改科学设计、config、manifest、executor、F2 或 old recovery。
- 上一轮 run 未创建且 model/Judge 计数为 0；本任务允许一次唯一的新 live 提交，不是恢复或重复实验。错误只按已记录事实描述，不武断推断未被证实的根因。
- 新命令明确使用绝对 Python 路径、项目内临时目录、单卡 GPU 0、离线变量和外部 stdout/stderr 重定向；先用独立 Bash 脚本做 `bash -n`，再执行一次 `nohup`，避免把目录误当作可执行命令。
- preflight、唯一提交、停止条件和交付证据均被限定；没有新增模型、数据、预算、approval 层或审计框架。
- adapter 仍只消费当前 run，失败时不继续后续阶段，旧证据不覆盖。
- 明确区分 live 收尾文件中的占位字段与真实 release 证据，不把当前 executor 尚未实现的 `runtime.release()` 误报为已验证。

未发现过度设计或科学范围漂移，审查通过。
