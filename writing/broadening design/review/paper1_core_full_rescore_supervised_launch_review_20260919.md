# Core 启动证据复核与下一步任务有边界审查

日期：2026-09-19

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_full_rescore_supervised_launch_task.md`，版本 `core-full-rescore-supervised-launch-v1`。

## 证据和判断

- 已读取追加报告、实际 retry-v2 shell、prelaunch/postlaunch、刚同步的 `nohup.out`、0-byte log 和 PID 文件。PID 为 `2443673`；run 与 `.exit` 未生成。
- 最新提交 `901f845` 只保存 retry-v2 shell，未变更实验实现。上一轮本地复核表明 shell、adapter 和测试的 LF 规范化 SHA256 与服务器记录一致；本地 CRLF 字节不能冒充 Linux 原始字节。
- 用户补充的外层命令为执行 `.sh` 后打印 `$?` 并列出 PID 文件。它没有等待后台进程，`launcher_script_rc=0` 和工具 exit 0 不能证明后台 Python 成功。
- `nohup.out` 只有 `.codex-temp/: .codex-temp/: Is a directory`。SFTP 后本地时间不能当成服务器原始修改时间，没有证据把该报错确定归属于第二次失败。
- 实际 shell 语法通过；没有 run 按当前 executor 的先建 run、后构造 backend 顺序支持“未到模型加载”，但不足以区分 Python 启动前退出、CPU preflight 中退出或被外部终止。历史根因仍未确定，不把进程清理或 shell 环境假设写成事实。

结论：已有同步内容足以安排一个受限的启动链路验证任务；不需要继续索取不存在的实验 raw，也不直接再次提交未经验证的 live。

## 任务修正和本地验证

改为两个项目内 shell 文件，用系统绝对路径启动 nohup，移除 `BASH_ENV/ENV` 对子 Bash 的影响，明确重定向；父 shell `wait` 子进程，真实退出码同时落在 supervisor 记录中。worker 有启动标记和 EXIT trap；SIGKILL 等不可捕获终止仍可能缺少 worker.exit，不能伪造。

先用同一链路执行标准库 15 秒等待和现有 CPU preflight；成功后同一服务器任务可执行一次 live，失败不消耗模型请求。CPU 启动至多两次，第二次只允许在有具体 shell 修复依据时使用；live 至多一次。没有新的批准文件或设计改动。

本机已从任务书提取两个原始 Bash 代码块，使用 Git Bash 做语法验证；另外只替换测试目录和解释器路径，以替身 Python 程序验证 shell 行为：

| 检查 | 结果 |
|---|---|
| 原始 worker.sh、submit.sh 的 bash -n | 通过 |
| CPU probe 正常结束，worker/supervisor 退出 0 | 通过 |
| 替身 executor 成功后执行 adapter | 通过 |
| 替身 executor 退出 17，adapter 不执行，真实退出码向上传递 | 通过 |

本地证据：`.codex-temp/core-launch-review-6j0bqn6i/summary.json`，状态 `LOCAL_SHELL_REVIEW_PASS`。本地检查未加载模型、未发送 Judge 请求，也未运行实验 fixture；它不能替代 Linux 服务器上的 CPU 启动验证。

## 一次有边界自审

- 科学规则：保持 1,200/20×60、direct JSON 1296、原 retry 与 2% gate、四组 A/S 及已有 allocator；没有增添模型、数据、剂量或正式实验。
- 启动边界：仅一个会话；先验证真实启动路径，再一次 live；工具返回 session ID 时继续监测该 session，禁止重复提交。
- 代码边界：只增 shell/证据/报告，不修实验 Python、config、manifest 或历史结果，不重跑全套测试或 1,200-row fixture。
- 结论边界：screen gate 文件不冒充 A/S；已知 runtime/release 占位字段不冒充实际核验；历史根因没有证据则保留未定。
- 交付边界：要求明确列出实际脚本、外层命令、PID/log/退出码、CPU preflight、完整新 run 和所有修改文件，避免再次只同步报告。
- 复杂度：两个短 shell 和一次 CPU 验证直接针对连续两次启动失败；不引入守护服务、调度器、泛化启动框架或新的科学审查层。

最终结论：`TASK_PROMPT_REVIEW_PASS`。可以交由原服务器会话执行；CPU gate 成功后直接继续已授权的三阶段合并任务，最终交付后再审查是否进入正式评估。
