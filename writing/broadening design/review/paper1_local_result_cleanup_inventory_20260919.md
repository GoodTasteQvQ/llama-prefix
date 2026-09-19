# 本地实验记录清理建议

日期：2026-09-19；根目录：`D:/llama_prefix`。

本文件是清理清单，不执行删除。作者指定的 `.codex-temp` 和所有 report 目录不列入清理范围。检查依据为本地文件、run header/frames、当前代码/config/测试和既有交接引用。服务器备份是否完整尚未核验。

`results/paper1_broadening/` 当前有 12 个目录，合计约 50.695 MiB。主要收益是整理目录；不建议为这点空间破坏协议变更和结果溯源证据。

## 可以在确认备份后移除的本地副本

下列 5 个目录都只有旧 prepare 的 frames/header/plan、代码与设计快照，没有正式 generation/Judge raw。当前检查未在执行代码/config/测试中发现对这些旧目录名的直接引用；历史文档仍可能引用它们。

先确认服务器或外部存储保有同一完整目录（文件清单和内容核对）；只移除本地副本，不删除唯一历史副本。也可先迁入独立本地历史存档目录。不要据此删除来源数据、审核 ledger 或 source snapshot 中引用的原始数据文件。

| 相对 `results/paper1_broadening/` 的目录 | MiB | 原因 |
|---|---:|---|
| `paper1-20260906T020956Z-a3343ef2c4` | 0.841 | 旧 AI 生成 pairs，source=500、k=79 的 prepare；已被公开 pairs 方案替代 |
| `public-semantic-pairs-20260906T105700Z` | 0.814 | source=416、k=18 的旧阻断 prepare |
| `public-semantic-pairs-v2-20260914T122608Z` | 0.976 | source=416、k=24 的旧阻断 prepare |
| `public-safe-pair-recovery-v2-20260915T035029Z` | 3.078 | source=516 的中间 prepare，frames 与最终 041534Z 完全一致 |
| `public-safe-pair-recovery-v2-final-20260915T035731Z` | 4.689 | 较早的中间 prepare，frames 与最终 041534Z 完全一致 |

合计约 10.398 MiB。后两个目录仅确认 frames 一致，整个目录的 source/design snapshot 并不等同，因此不是可以无备份直接抹去的完全重复目录。

## 当前保留的七个目录

| 目录 | MiB | 保留理由 |
|---|---:|---|
| `core-directions-calibration-20260915T140731Z-1382603` | 26.500 | 当前方向、校准、frames 和 1,200 条 generation 的唯一运行来源；即使旧 Judge 协议失效，也不能删整个 F2 run |
| `core-full-rescore-direct-20260919T094847Z-2523251` | 8.514 | 新四分类标签、screen gate 和正式 A/S 的来源 |
| `public-safe-pair-recovery-v2-final-20260915T041534Z` | 4.708 | 最终 300 executable、k=40 数据划分及 E1 overlap 交接引用 |
| `core-judge-protocol-v3-direct-json-recovery-20260918T130823Z-a1` | 0.085 | 本次 rescore readiness 引用的 recovery 成功证据 |
| `core-judge-protocol-v3-direct-json-probe-r2-20260918T051304Z-1dd65644` | 0.107 | v2.3 协议兼容性来源 |
| `core-judge-protocol-probe-20260917T141934Z-1a746872` | 0.137 | 4096 thinking 方案失败原始证据，解释为何改为 direct JSON |
| `paper1-core-fourclass-recovery-20260916-r13-a5a5936` | 0.246 | 旧失败恢复证据；当前 readiness builder 和 executor 仍显式引用其保护路径/文件 |

不从这些目录内抽删“旧标签”或“旧配置”：已有 hash manifest 覆盖它们，抽删会让历史验证失败。协议过时表示不再将结果混入正式统计，不表示原始证据无保留价值。

## 其他目录

- `.pytest_cache/`（约 5 KiB）与下列 Python `__pycache__/` 为可再生成缓存，确认当前没有本地测试或进程正在使用后可以清理：`paper1_broadening`、`scripts`、`scripts/stage1_phase_aware`、`scripts/stage3_production`、`tests`、`tests/paper1_broadening`、`tests/stage3`、`tests/stage3_model`、`activation_guard`、`stage3_pipeline`、`stage3_pipeline/statistics` 下的缓存。合计约 2.76 MiB，不触及源码或测试文件。
- `tmp/` 约 118.72 MiB，但包含 `pydeps` 依赖、写作参考 PDF、渲染页和图稿，不能仅凭名称整体删除；保留到相关写作/绘图流程确认不再使用。
- `results/phase_matrix/`、`results/stage1_phase_aware/`、`results/stage3_calibration-frame_sensitivity/` 属于已有论文证据，不因本轮 Judge 修订删除。没有逐项做这些目录的研究证据弃用审计。
- `configs/paper1_broadening/` 的旧 revision、`data/` 原始数据/ledger、`logs/` 运行日志以及旧设计文件保留；它们体积小，且可能被历史 source snapshot 或 hash 清单引用。
- 根目录 `nohup.out` 只有 43 字节，虽为旧错误记录，但两次失败报告引用它；暂时保留，不把它当作成功 run 的错误。

## 清单自审

没有把“设计更新”等同于“历史记录可直接删除”；区分可再生成缓存、可移除的已备份本地 prepare 副本、当前结果输入和协议历史证据。保留用户指定的 `.codex-temp`/report 范围；未执行删除、移动或改名。清单自审通过。
