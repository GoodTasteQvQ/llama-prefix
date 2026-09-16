# E2R：Gemma release 序列化最小修复

版本：`gemma-release-serialization-patch-v1`；交给新 E2R 会话。该任务只修复未来方向构造 run 的生命周期记录，不重建 F run，也不运行 E2。

## 输入与前置结论

先阅读：

- `writing/broadening design/report/paper1_e2_gemma_release_gap_audit_report.md`
- `writing/broadening design/report/paper1_core_direction_calibration_report.md`
- `writing/broadening design/report/paper1_core_screen_parse_forensic_report.md`
- `writing/broadening design/implementation/paper1_server_codex_post_audit_task_index.md`
- 原实验设计三份只读文件

E2 审计已确认：`_build_e2_assets()` 调用了 layer-14 `runtime.release()`，但没有把真实返回值写入 Gemma model record；F run 的 Gemma release 只能标记 `UNVERIFIED_NOT_PASS`。这是 metadata gap，不是科学设计变更。

## 允许修改

- 共享实现：`paper1_broadening/pipeline.py`
- 仅为验证该行为新增或修改聚焦测试：`tests/paper1_broadening/`
- 本任务报告：`writing/broadening design/report/paper1_e2r_release_serialization_patch_report.md`
- 其余脚本、日志、PID、`.exit` 和测试临时输出放项目内 `.codex-temp/paper1_e2r_release_serialization/`

执行前记录 `git status` 和上述文件已有 diff/未跟踪状态；不得重置或覆盖已有用户修改。

## 实现要求

1. 在 `_build_e2_assets()` 中保留 layer-14 `runtime.release()` 的真实返回对象，并原样写入 `output["models"]["gemma2_9b_it"]["release"]`。字段集合应与 Qwen/Llama release schema 一致；不得手工构造全 true 字段。
2. release 抛异常时必须 fail-closed：返回 `BLOCKED` 和具体 `release_error`，不得写 `COMPLETED`、伪造 release 或继续生成正式 E2 资产。
3. 保持 layer-0 probe 的现有处理边界；不因 schema 对齐增加新的科学字段或额外模型调用。
4. 保持 model/tokenizer revision 的真实语义：没有明确 revision 时继续为 `UNKNOWN`，不得从目录名猜测或回填外部旁证。
5. 不改变层公式、方向数量、fold、mu、模板、decoder、seed、预算或任何科学设计字段。

## 离线测试

使用项目 Python 环境和项目内临时目录，通过 `nohup` 保存 PID、日志、`.exit`。不下载、不加载 Gemma 或其他模型、不使用 GPU、不联网。

至少覆盖：

1. fake `BehaviorRuntime`、fake frames/tensor 运行 `_build_e2_assets()`；断言 Gemma model record 原样包含 release，key 集合与 Qwen/Llama 对齐，方向 tensor/mu/layer 字段不变。
2. fake layer-14 runtime 的 `release()` 抛异常；断言结果为 `BLOCKED`，包含具体错误，没有合成 PASS。
3. regression：Qwen/Llama/E3 release 记录路径和现有测试保持通过；Gemma revision 缺失时仍为 `UNKNOWN`。
4. Python compile、`git diff --check` 和聚焦 pytest 通过；退出码与业务断言分别记录。

## 输出与停止条件

报告必须列出：实际修改文件、F run 未修改证明、测试命令/PID/log/exit、schema 对照、未修改的原实验设计和配置。明确写入：

`E2R_IMPLEMENTATION_PATCH_PASS`（仅当测试和边界审计都通过）

以及：

`F_RUN_GEMMA_RELEASE_REMAINS_UNVERIFIED`
`E2_FORMAL_EXPERIMENT_NOT_RUN`
`FORMAL_EVALUATION_NOT_RUN`

完成一次有边界自审后停止。不要运行 prepare、build-directions、screen、generation、Judge 或正式 evaluation；不要回填 F run `directions.json`；不要 commit/push。若发现必须改变科学字段或重建 F run，立即停止并报告 `DESIGN_CHANGE_REQUIRED`。
