# B6：Core 运行前静态证据交接

版本：`core-static-evidence-handoff-v1`；日期：2026-09-15。交给原 B 会话续作，可与 F 的 Core screen 前置核验并行；只读，不使用 GPU。

先阅读当前任务入口、C3/B5/F 报告和 Core dose screen 任务书。服务器当前根目录实现与 B4 证据副本可能存在差异，本任务只核对并交付实际文件，不凭报告摘要宣称代码一致。

## 只读核对

逐项定位并记录以下文件的实际相对路径、SHA256、来源和是否在 F run 的 source snapshot 中：

- F run 的 `run_header.json`、`resolved_config.json`、`frames.json`、`directions.json`、`directions_qwen25.pt`、`directions_llama31.pt`；
- C3 final E1 目录中的 reference snapshot、final ledger、review identity manifest、40条 selection 和 finalization manifest；
- B5 的 `mbd_nm_v212_public_expanded_e1_final_d148.json`；
- Core screen 使用的单卡 wrapper、当前 `paper1_broadening` 源码及 F source snapshot 中的相关测试；已有小型检查结果直接沿用，不为交付重跑测试。

逐项检查 F run 的 source snapshot 与当前服务器源码字节一致；若任何 mismatch，写 `SOURCE_SNAPSHOT_MISMATCH`，不要复制当前源码覆盖 snapshot，不要运行或重试 screen。确认 F run 的 frames/directions 内容与报告中的 gate、层、fold、mu、tensor hash一致；发现矛盾则写具体 `HANDOFF_BLOCKED`。

只读确认 E1 final config 与 F run 使用的配置关系：C3/B5 final digest 是 `d148...732a`，40条/6类可消费；不得把旧 C2 provisional 文件替换进 run。不要修改 canonical config、F run、C3/C2产物或共享实现，不修复 Gemma release gap。

## 交付

将必要的小型静态证据（config、frames、directions metadata/tensor、C3/B5 final 文件、source snapshot 原文件与清单）复制到新的 `writing/broadening design/report/evidence/paper1_core_static_handoff/`，保留原相对路径映射；已交付且 hash 相同的 source/data 文件可引用已跟踪路径，新增或不同版本的源文件必须实际交付。静态原件无需复制两套，不复制模型权重、完整 reviewer raw 或大缓存。F run 的47项源码/输入以 header 的实际 `source_files` 为准，不限于 Python 文件；需涵盖实际使用的 expanded source/ledger/manifest、配置、adapter 及来源许可，不能只有 hash 清单。

F2 在启动前保存 F 阶段 `run_header.json` 副本，B6 优先消费该稳定副本并标明来源；若 header 正在更新或副本尚未提供，先处理其余静态文件，不能把运行中的 header 误标为 F 阶段原件。screen 动态产物由 F2 在结束后交付，B6 不等待 screen 完成、不复制正在写入的 ledger。不要在两个任务运行期间 commit/push/pull；只整理可供用户之后一次性同步的文件清单。

所有批量 hash/检查使用项目内 `.codex-temp`，需要后台脚本时使用 `nohup`、PID、log、`.exit`；不加载模型。保存 `writing/broadening design/report/paper1_core_static_handoff_report.md`，写实际文件清单、hash、snapshot 比对、E1/Core gate、未同步项和 `FORMAL_EVALUATION_NOT_RUN`。完成一次边界自审后停止，不 commit/push。
