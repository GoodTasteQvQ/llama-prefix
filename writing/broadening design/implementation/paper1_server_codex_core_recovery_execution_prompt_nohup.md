# Core recovery execution：负责人批准后最多恢复 13 条 Judge 解析失败

版本：`core-judge-recovery-execution-v1`；会话：`A-recovery-run`。

这是一个**批准门控**任务。未看到负责人书面批准前，只能检查批准文件是否存在，不能发送任何 Judge 请求。

## 前置输入

先阅读：

- `writing/broadening design/report/paper1_core_recovery_proposal_report.md`
- `writing/broadening design/report/paper1_judge_observability_patch_report.md`
- `writing/broadening design/report/paper1_core_screen_parse_forensic_report.md`
- `writing/broadening design/implementation/paper1_server_codex_post_audit_task_index.md`
- 三份原实验设计文件

执行前记录 `git status`、目标文件已有 diff，并核对 F2 原件 hash。不得 reset、checkout 或覆盖其他修改。

## 必须先验证的批准内容

批准必须是项目内可审计的文本文件或 run header 记录，且同时明确：

1. 新 recovery run 的完整 `run_id` 和目录路径；
2. 最多 13 次、每条输入最多 1 次的 four-class Judge 请求；
3. 使用原 F2 prompt/frame、generation completion、rubric、parser、decoder 和 endpoint；
4. binary Judge=0、generation retry=0、额外 retry=0；
5. 原 2% missing gate 保持不变；
6. 旧 F2 全部文件只读，不覆盖、不合并、不回写。

批准缺任何一项时，写入 `APPROVAL_INCOMPLETE` 报告并停止，不发送请求。

## 执行边界

- 只消费 proposal 中列出的 13 条 generation completion。
- 不重新生成，不加载 behavior model，不运行 screen 或正式 evaluation。
- 新 run 必须独立保存：request manifest、Judge records、runtime/status、provenance/hash manifest。
- 每条最多一次 four-class Judge 请求；失败、超时、无 raw 或解析失败都写成 `PARSE_FAILURE`/missing。
- 使用 F4 observability 字段保存 raw、diagnostics、错误和 request identity。
- 不手工补标签，不从 generation completion 推断标签，不复制其他分组的标签或 A/S。
- 不运行 binary Judge，不改变模型、层、方向、rho、seed、模板、rubric、parser、decoder、预算或 2% gate。

## Gate 与停止条件

所有请求结束后，只能在新 recovery ledger 上做只读 gate 计算：按原 F2 的模型/家庭/rho 分组检查 2% missing。不得修改旧 `dose_decisions.json`。

- 任一原始分组仍超过 2% missing：写 `CORE_RECOVERY_BLOCKED`，不得选择 A/S，不得开始 evaluation。
- 全部分组满足原门槛：只写 `CORE_RECOVERY_GATE_PASS_PENDING_AS_REVIEW`；A/S 选择和正式 evaluation 仍需另一个独立任务和批准。

## Linux/nohup

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export NX_DAEMON=false
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export PYTHONUNBUFFERED=1
export PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export CUDA_VISIBLE_DEVICES=0
```

所有检查、预检、请求和汇总均须保存 PID、日志和 `.exit`。请求应串行执行，防止共享 GPU 和 ledger 竞争；启动前确认 GPU 0 空闲且显存足够。

## 输出

报告：`writing/broadening design/report/paper1_core_recovery_execution_report.md`。

必须列出批准文件/hash、run id/path、13 条输入 identity/hash、实际请求数、每条状态、旧 F2 不变 hash、gate 结果和所有 PID/log/exit，并写入：

- `CORE_RECOVERY_EXECUTION_COMPLETE` 或 `CORE_RECOVERY_BLOCKED`
- `OLD_F2_UNMODIFIED`
- `FORMAL_EVALUATION_NOT_RUN`

不得 commit/push。完成边界自审后停止。若发现需要超过 13 次请求、任何重试、改变科学规则或修改旧 F2，立即写 `DESIGN_CHANGE_REQUIRED` 并停止。
