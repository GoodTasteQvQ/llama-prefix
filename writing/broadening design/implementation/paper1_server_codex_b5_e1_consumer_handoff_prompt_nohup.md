# B5：E1 最终消费复核与 Core 运行入口交接

版本：`e1-consumer-handoff-v1`；日期：2026-09-15。交给原 B 会话续作，等待 C3 报告和 final 派生文件后执行。

先阅读当前任务入口、C3 报告、B4 报告、expanded config/source/ledger/manifest 和设计不可变性审计。B4 已通过代码契约和真实工程 smoke；本任务不重新做 safe-pair 审核，也不重跑 B4 smoke。

## 复核范围

1. 确认 C3 final E1 ledger、identity manifest、40条 selection 和 reference snapshot 使用同一 `d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`，revision 为 `harmbench-e1-dual-codex-overlap-v1`，不再使用旧 provisional digest。
2. 使用当前 E1 consumer/`build_frames` 的 CPU 路径验证：candidate=200、exact=9、near queue=17、selected=40、至少6个原生类别，frames 中状态为 `READY_FOR_RUN`。禁止通过删除 queue、改 prompt 或绕过 digest 校验得到 PASS。
3. 如现有 canonical expanded config 仍指向旧 provisional 文件，只创建一个明确命名的 run-specific final config 或最小路径适配；保留 canonical config 原文和 hash，不改模型、层、hook、template、decoder、rho、seed、split、预算或 endpoint。

## 边界

- 本任务只做 CPU 消费和配置交接；不加载模型，不运行 prepare、build-directions、screen、generation、Judge、analysis 或 human packet。
- 只允许修改直接相关的 E1 adapter/validator、final config 引用和测试。已有50项测试无需因报告重复运行；若实际代码改动，补跑相关完整套件并记录 `nohup`/PID/log/exit。
- 原实验设计正文、易读版、实现规范和已批准来源 revision 默认只读。任何科学字段必须改变时立即停止并报告 `DESIGN_CHANGE_REQUIRED`，不得自行创建设计新版本。

保存 `writing/broadening design/report/paper1_e1_consumer_handoff_report.md`，分别列 `E1_CONSUMER_PASS/PENDING/BLOCKED`、final 文件路径/hash、config 绑定、CPU 业务结果、实际修改文件和设计保护检查。没有新模型证据时保留 `FORMAL_EXPERIMENTS_NOT_RUN`。完成有边界自审后停止，不 commit/push。
