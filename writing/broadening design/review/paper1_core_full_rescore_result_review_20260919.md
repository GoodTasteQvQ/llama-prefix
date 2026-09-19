# Core full rescore 结果复核与同步缺项

日期：2026-09-19

审查对象：`results/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251/`、更新后的 `report/paper1_core_full_rescore_screen_as_report.md`、full-rescore executor/launcher、CPU dose adapter 和现有正式评估入口。当前 Git HEAD 为 `ae3ac19`；本地这些实现文件无未提交修改。

状态：`RESULT_ARTIFACT_REVIEW_PASS_LAUNCH_EVIDENCE_PENDING`。

本次可确认结果文件通过复核。按照作者“发现影响下一步判断的同步缺项时先提出，补齐后再下判断”的要求，暂不下发正式评估运行任务，也不要求重新执行实验。

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

## 必须补齐的五个既有文件

本地缺少以下报告声称已存在的文件。它们用于核对实际进程、退出和启动环境；run 内的 runtime/boundary 仍是 DEFERRED/null 占位，不能替代这些证据。

```text
.codex-temp/core_full_rescore_direct_live/launch_precheck.txt
logs/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251.log
logs/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251.pid
logs/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251.exit
logs/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251.monitor.log
```

给服务器会话的当前指示：只读找到上述五个原文件，按原目录通过 SFTP 同步。不要重跑 full rescore、screen、adapter、CPU probe 或模型，不重新生成退出码或历史监控记录。如果文件实际不存在，直接报告缺失和现有替代原始证据，不填造文件。若 `.exit` 来自不同 shell 中的 `wait` 或后补推断，需要如实说明来源；不要修改原文件。同步完成后由本机继续审查。

## 后续接口已发现的事项（尚非运行授权）

现有 `paper1_broadening/pipeline.py::_dose_rhos` 读取 `decisions[model_id][family]`；本次 `dose_decisions.json` 使用 `groups[model_id|family]`。它不能直接作为既有正式评估入口的剂量文件。本次 rescore run 也没有正式 generation 所需的完整 run header、frames、directions 和 source snapshot。

补齐启动证据后，下一步应在独立正式评估 run 中按既有接口衔接新 A/S、F2 frames 与方向资产，保留输入来源；无需重算方向或重新选剂量，更不能改写旧 F2 的 dose 文件。Core 尚余正式 generation 为 11,440 条：harmful steered 10,400 + harmful clean 200 + benign steered 780 + benign clean 60。1,200 条 development generation 已完成，Judge full rescore 不能再次计入 generation 预算。具体任务和授权在同步缺项核验后再给出。

## 有边界自审

本次仅复核已落地结果与现有接口，未扩展科学设计、模型、数据、剂量或审核流程。将结果文件通过与启动证据待补分开，不凭报告冒充已见原始日志；同步任务只取现有文件，不产生额外请求。结论边界和同步指示自审通过。
