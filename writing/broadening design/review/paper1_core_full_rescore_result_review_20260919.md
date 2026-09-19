# Core full rescore 结果复核与同步补齐验收

日期：2026-09-19

审查对象：`results/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251/`、更新后的 `report/paper1_core_full_rescore_screen_as_report.md`、full-rescore executor/launcher、CPU dose adapter 和现有正式评估入口。首次结果审查的 Git HEAD 为 `ae3ac19`，本次补验起点为 `23eaa6b`；本地这些实现文件无未提交修改。

当前状态：`CORE_FULL_RESCORE_SCREEN_AS_REVIEW_PASS`（2026-09-19 补齐后）。下文首次审查的缺项记录保留为历史；五份文件现已收到并核验，当前无影响下一任务判断的同步缺项。

首次审查时仅确认结果文件通过复核，曾按作者要求等待启动证据。本次补充验收通过，下一步执行独立 Core 正式 generation；不重跑已完成的 full rescore、screen 或 A/S。

## 已实际复核的证据

- 完整 run 共 16 个文件，`artifact_hashes.sha256` 覆盖其余 15 个文件；15/15 SHA256 逐字节匹配，不是依靠换行归一化匹配。
- manifest、request records、attempt records 均为 1,200 条，events 为 4,800 条。logical identity 和 response identity 均唯一。
- 对全部 1,200 条逐项核对 F2 schedule/attempt/ledger 行号、identity、终止状态，以及 prompt/completion/request hash；旧 F2 四份 source 文件的 hash 也匹配。
- 四分类 raw 为完整 JSON，键及值与解析记录一致；raw、diagnostics hash 与独立 attempt、嵌套 attempt 和事件中的 identity/label 一致。没有读取旧 F2 Judge label 来补结果。
- 20 cells 每格 60 parsed / 0 missing；实际 four-class=1,200，binary=0，retry=0；terminal accounting 与逐条计数一致。
- 从新标签独立重算候选 unsafe/broken 比例和 A/S，四组的 rho、alpha、状态及 ordering 与输出一致。view/index 也与原始 records 一致。
- `adapter.exit=0`、adapter 输出和 Judge identity 已同步。Judge 为 direct JSON、1296、thinking disabled、float32、cuda:0，模型 revision 保留 UNKNOWN。

| Group | A rho | S rho | A alpha | S alpha |
|---|---:|---:|---:|---:|
| Qwen / contrastive | 0.50 | 1.00 | 28.4348698313 | 56.8697396627 |
| Qwen / Rogue | 0.75 | 1.50 | 42.6523047470 | 85.3046094940 |
| Llama / contrastive | 1.00 | 1.25 | 7.6152477558 | 9.5190596947 |
| Llama / Rogue | 1.00 | 1.50 | 7.6152477558 | 11.4228716337 |

四组 `ordering_not_established=false` 是 development screen 中的操作性排序结果。它不证明正式 JBB-100 效果、相对 clean 的攻击有效性或人工 Judge 质量已经通过。

本地只读核查脚本与详细结果保存在 `.codex-temp/review_core_full_rescore_20260919.py`、`.codex-temp/local_core_full_rescore_review_20260919.json`。未加载模型或发出请求，未重跑全套测试，未改写实验结果。

## 首次审查要求补齐的五个既有文件（现已全部补齐）

首次审查时本地缺少以下文件。它们用于核对实际进程、退出和启动环境；run 内的 runtime/boundary 仍是 DEFERRED/null 占位，不能替代这些证据。

```text
.codex-temp/core_full_rescore_direct_live/launch_precheck.txt
logs/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251.log
logs/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251.pid
logs/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251.exit
logs/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251.monitor.log
```

此前同步指示已完成，不再要求服务器重新同步或生成这五份文件。仍保留不重跑、不事后填造退出码或历史记录的约束。

## 后续接口与规模核对

现有 `paper1_broadening/pipeline.py::_dose_rhos` 读取 `decisions[model_id][family]`；本次 `dose_decisions.json` 使用 `groups[model_id|family]`。它不能直接作为既有正式评估入口的剂量文件。本次 rescore run 也没有正式 generation 所需的完整 run header、frames、directions 和 source snapshot。

下一步在独立正式评估 run 中按既有接口衔接新 A/S、F2 frames 与方向资产，保留输入来源；无需重算方向或重新选剂量，更不能改写旧 F2 的 dose 文件。Core 尚余正式 generation 为 11,440 条：harmful steered 10,400 + harmful clean 200 + benign steered 780 + benign clean 60。1,200 条 development generation 已完成，Judge full rescore 不能再次计入 generation 预算。

本次使用真实 frames、新 A/S 与 v2.3 config，经现有 `_dose_rhos` 和 `build_core_schedule(include_development=False)` 在本地内存中核对：11,440 rows、11,440 unique response IDs，Qwen/Llama 各 5,720；四组剂量、层、benign decode-only S、JBB 100 条/10 类均匹配。这是接口与日程核对，不冒充服务器完整 config/模型环境验证。未创建正式 run，模型加载及 Judge 请求为 0。摘要为 `.codex-temp/local_core_formal_schedule_review_20260919.json`。

## 补充证据验收（2026-09-19）

- precheck 为服务器路径 `/data/goodtaste_workspace/llama-prefix`、HEAD `ae3ac19`、Python 3.10.20；2026-09-19T09:47:02Z 完成，原两次失败 run 均未生成。进程匹配中的检查命令本身不计为重复 worker。
- `.pid=2523254`，与 monitor 中本次唯一 run 的记录一致。monitor 记录 09:48:47Z 启动、存活到退出、`inner_rc=0`，最终时间 10:23:17Z；`.exit=0`。
- executor log 为 736 bytes，完成五个模型分片加载，只有 greedy 下部分 sampling 参数被忽略的提示；无 traceback。monitor 共 38,421 bytes，终态与 run 内 1,200/20×60、零 missing/retry 的 accounting 一致。
- 五份补充文件的路径、大小、SHA256 已写入上述本地摘要。15/15 run artifact 的既有逐字节核验继续有效，无需重复全部审核。
- runtime/release 中的 `DEFERRED`/null 仍是原实现占位；本次只确认进程正常结束，不将其写成实际 `runtime.release()` 已序列化通过，不改写历史文件。下一正式 run 使用既有 generation runner 的真实 `behavior_release.json`。

决策：接受 `CORE_SCREEN_V3_PASS` / `CORE_DOSE_SCREEN_READY` / `CORE_A_S_READY_FOR_FORMAL_EVALUATION`。执行 [Core 正式生成任务书](../implementation/paper1_server_codex_core_formal_generation_task_nohup.md)，在同一任务完成最小格式衔接与 11,440 条 generation；本轮不发 Judge 请求，不进入 E1/E2/E3。无需新的 approval 文件或额外 CPU 启动 probe。

## 首次审查的有边界自审

本次仅复核已落地结果与现有接口，未扩展科学设计、模型、数据、剂量或审核流程。将结果文件通过与启动证据待补分开，不凭报告冒充已见原始日志；同步任务只取现有文件，不产生额外请求。结论边界和同步指示自审通过。

补齐后的任务与验收自审见 [Core 正式生成任务有边界自审](paper1_core_formal_generation_task_review_20260919.md)。本文件的首次缺项结论不再构成当前阻断。
