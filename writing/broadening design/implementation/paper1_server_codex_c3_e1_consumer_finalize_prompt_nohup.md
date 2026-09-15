# C3：最终 E1 overlap 派生物收尾

版本：`e1-consumer-finalize-v1`；日期：2026-09-15。交给原 C 会话续作。

先阅读当前任务入口、C2 报告、B4 报告、safe-pair recovery 报告和设计不可变性审计。C2 的语义审核已经完成；本任务只修复 C2 输出与最终 safe-source reference snapshot 的绑定，不重新审核任何 prompt。

## 输入与唯一允许的变化

- 最终 reference snapshot 必须是 C2 的 `d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`，共700条：JBB100 加实际 construction/development 的600条 safe-pair role text；benign30 不在其中。
- 只使用 C2 scope-fix reviewer A/B 的 raw/result：17个去重 near-match prompt，双方各11个 `overlap`、6个 `no_material_overlap`，0 uncertain、0 technical failure。
- C2 旧 digest `8be3f0b5ba135f7f8b0bcf09e8005612f4536b25f1fde8e355036203f5f8253a` 的 ledger、identity manifest 和 selection 保留为历史 provisional，不覆盖、不删除、不改写。

在独立新目录（例如 `.codex-temp/paper1_e1_consumer_final/`）从现有 raw、reference snapshot 和 C2 的完整200行输入 ledger 重建：

1. final `near_match_review_ledger` 和 `review_identity_manifest`，绑定 `d148...732a` 与 `harmbench-e1-dual-codex-overlap-v1`；
2. final `e1_overlap_ledger`，保留9 exact exclusions、17 semantic queue结果、174 deterministic no-near-match，最终 include=180、pending=0；
3. final `harmbench40_selection`，沿用 C2 的类别首次出现顺序和类内 source_index 轮转，保持同一40个 prompt、6个原生类别、原文和 source identity。

不得改变候选文本、reference scope、阈值、review verdict、类别顺序或选择规则。只改变派生文件中的 digest、final source binding、状态和路径引用。若 raw、输入 hash、review identity、reference digest 或40条选择无法逐项对应，停止并写 `E1_FRAME_BLOCKED`，不得重新调用 reviewer 或手工凑数。

## 验证与交付

- 用当前 E1 schema/consumer 做纯 CPU 校验，确认最终文件可得到 `READY_FOR_RUN`；不要调用模型，不运行 prepare、directions、screen、generation、Judge、analysis 或 human packet。
- 不修改共享实现、safe-pair source/ledger、JBB、benign frame、原实验设计正文、易读版、实现规范或 canonical config。若必须改变科学字段，立即停止并报告 `DESIGN_CHANGE_REQUIRED`。
- 批量 materialization、校验和测试使用项目内 `.codex-temp`，需要后台运行的步骤通过 `nohup` 保存 PID、日志和`.exit`；退出0不替代业务结果。
- 关闭写入后为 final 派生文件计算 hash；不生成运行前的全项目不可变 manifest。

保存报告：`writing/broadening design/report/paper1_e1_consumer_finalization_report.md`。报告列出旧 provisional 与新 final 的关系、digest/hash、200行计数、review/raw来源、40条清单摘要、CPU consumer 结果、实际修改文件和设计未修改声明，写 `E1_CONSUMER_PASS` 或具体 `E1_FRAME_BLOCKED`，并保留 `E1_EXPERIMENT_NOT_RUN`、`FORMAL_EXPERIMENTS_NOT_RUN`。完成一次有边界自审后停止，不 commit/push。
