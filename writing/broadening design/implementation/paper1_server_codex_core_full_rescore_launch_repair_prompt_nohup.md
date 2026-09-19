# Core full rescore 启动修复与唯一重试任务书

版本：`core-full-rescore-launch-repair-v2`
前置报告：`writing/broadening design/report/paper1_core_full_rescore_screen_as_report.md`
前置状态：`LIVE_LAUNCH_BLOCKED_NO_RERUN`

## 判断

前一次 live 提交在 shell 启动层失败，报告记录错误为 `.codex-temp/: Is a directory`。run 目录和 `.exit` 均未生成、log 为 0 bytes、PID 已退出，符合 Python executor 尚未启动的情况。现有材料不足以确定外层工具如何把目录拼接进命令，不能把某个环境变量错误当作已证实的根因。下一步采用明确的 Bash 命令和重定向，先验证 shell，再进行一次唯一的新 live 提交；不得把它当作恢复旧 run。

本任务已获负责人授权，不需要另建 approval 文件。沿用原合并任务的科学边界，以本文件替代其启动命令。继续使用当前服务器会话即可；无需并行 GPU 会话或重新做已通过的 fixture 测试，也不得改 Python 源码、测试、设计、config、manifest、旧 F2/recovery。允许保存本任务的临时 shell、日志和运行结果。

范围为 1,200 条现有 generation、20 cells 各 60；Judge 为 `enable_thinking=false / max_new_tokens=1296 / strict_direct_json_v1 / greedy / float32`。每条至多一次原设置 retry，four-class 总上限 2,400，binary 和 generation 均为 0。每 cell 的原 2% missing gate 保持不变。通过后才调用现有 CPU adapter，按原规则产生四组 A/S；`A_NOT_ESTABLISHED`、`S_NOT_ATTAINED` 或 ordering 不成立是合法结果。

## 启动前检查

只读确认服务器当前输入仍匹配已通过的 readiness/handoff（`FULL_RESCORE_BINDING_PASS`、`FULL_RESCORE_BOUNDARY_AUDIT_PASS`、`CORE_RECOVERY_V3_PASS`）；live executor 自带的 preflight 继续保留。若有变化，停止并报告，不重建输入。

将下面两段 Bash 按顺序原样保存到项目内 `.codex-temp/` 的一个新 `.sh` 文件，用 Linux LF。先 `bash -n <实际脚本路径>`，通过后只执行该脚本一次；不要把多行脚本再拼接为另一层含复杂引号的命令。语法检查不执行 Python，不消耗 live 次数。

先在 `/data/goodtaste_workspace/llama-prefix` 执行以下环境检查；通过后再提交：

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p "$PWD/.codex-temp" "$PWD/logs/paper1_broadening" "$PWD/results/paper1_broadening" || exit 1
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR" TEMP="$TMPDIR" NX_DAEMON=false
export PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 MBD_GPU=0
export MBD_MODEL_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_MODEL_PYTHON" || exit 1
test ! -e "$PWD/results/paper1_broadening/core-full-rescore-screen-as-20260919T031100Z-2436493" || exit 1
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
```

提交前用进程列表和 GPU 状态确认没有本任务正在执行的 Python/worker 或旧 PID 仍属本任务的进程。检查命令本身及其父 shell 中的命令文本不能当作正在运行的实验；不得仅以 `pgrep -af` 匹配到脚本名就判断重复运行。不终止其他用户进程。GPU 0 正忙时等待可用，不改用双卡。

保留前一次 `nohup.out` 及启动失败报告，不删除、覆盖或重命名为成功证据。若发现实际 run 已创建或任务仍活跃，立即停止并报告，不重跑。

## 唯一修正提交

使用新的唯一 tag。不要把 `.codex-temp`、`TMPDIR` 或任何目录路径放在 `nohup` 要执行的命令位置。所有变量在 inner shell 中再次显式设置，stdout/stderr 必须在 `nohup` 命令外重定向，避免生成默认 `nohup.out`：

```bash
TAG="core-full-rescore-screen-as-retry-$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN="$PWD/results/paper1_broadening/$TAG"
LOG="$PWD/logs/paper1_broadening/$TAG.log"
EXIT="$PWD/logs/paper1_broadening/$TAG.exit"
PID="$PWD/logs/paper1_broadening/$TAG.pid"
mkdir -p "$PWD/logs/paper1_broadening" "$PWD/results/paper1_broadening"
for path in "$RUN" "$LOG" "$EXIT" "$PID"; do
  test ! -e "$path" || exit 1
done

nohup bash -c '
  set -o pipefail
  rc=0
  cd /data/goodtaste_workspace/llama-prefix || { printf "%s\n" 3 > "$2"; exit 3; }
  export TMPDIR="/data/goodtaste_workspace/llama-prefix/.codex-temp"
  export TMP="$TMPDIR" TEMP="$TMPDIR" NX_DAEMON=false
  export PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
  export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 MBD_GPU=0
  export MBD_MODEL_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
  test -x "$MBD_MODEL_PYTHON" || { printf "%s\n" 3 > "$2"; exit 3; }
  export FULL_RESCORE_APPROVED=1
  "$MBD_MODEL_PYTHON" /data/goodtaste_workspace/llama-prefix/scripts/core_judge_full_rescore_run.py --run-dir "$1" --live || rc=$?
  if [ "$rc" -eq 0 ]; then
    "$MBD_MODEL_PYTHON" /data/goodtaste_workspace/llama-prefix/scripts/core_full_rescore_dose_adapter.py --run-dir "$1" || rc=$?
  fi
  printf "%s\n" "$rc" > "$2"
  exit "$rc"
' core-full-rescore-screen-as-retry "$RUN" "$EXIT" >"$LOG" 2>&1 < /dev/null &
printf "%s\n" "$!" > "$PID"
```

这里 inner shell 的 `$0` 是 `core-full-rescore-screen-as-retry`，`$1` 是 run 路径，`$2` 是 exit 路径。提交后只允许这一条后台任务；不要再次提交，不要用 `nohup.out` 判断成功。等待 PID 完成后再读取 `.exit` 和日志。外层提交命令退出 0 仅表示已提交，不能当作实验完成。

## 停止与交付

- executor 非零退出、run 内 contract failure、retry 耗尽、missing gate 或 adapter 阻断时，保留已有证据并停止，不删除、不修写结果、不重跑。
- executor 成功且 adapter 成功时，报告四组 20-cell accounting、A/S、实际 calls/retry、Judge release 和所有 hash。adapter 必须只消费本次 run 的 `request_records.jsonl`，不得读取旧 F2 Judge records。
- 当前 executor 的 live `runtime_status.json` / `boundary_status.json` 有 `DEFERRED`、`models_loaded=null` 及 `full_rescore_started=false` 的占位字段，launcher 未显式调用 `runtime.release()`。这些字段不能当成真实运行或 release PASS 证据。保留原文件，在报告中明确区分占位信息与本次实际的 Judge identity、request/event 计数、Python 进程退出及 GPU PID 消失的证据。进程退出只证明进程层资源回收，不能声称验证了 `runtime.release()` 内部步骤。本任务不为此重构实现或补发请求；正式评估仍等负责人审查。
- 仍禁止 generation、binary Judge、formal evaluation、E1/E2/E3、人工审核和分析。
- 报告路径保持 `writing/broadening design/report/paper1_core_full_rescore_screen_as_report.md`，追加本次修正提交的实际命令、PID、log、exit、run、结果和边界自审；不得覆盖前一次失败事实。
- 交付完整新 run（包括 `request_manifest.jsonl`、`request_records.jsonl`、`attempt_records.jsonl`、`events.jsonl`、`terminal_accounting.json`、`runtime_status.json`、`boundary_status.json`、`judge_identity.json`、`dose_decision.json`、`dose_decisions.json`、`judge_records_view.jsonl`、`judge_records_index.json`、`artifact_hashes.sha256`；失败时如实列出尚未生成的文件）。一并交付本次实际 `.sh`、语法检查结果、`.pid/.log/.exit`、运行前后进程/GPU 记录和更新报告，按实际路径逐项列出，方便 SFTP 同步。raw 若嵌在 JSONL 内则同步整个 JSONL，不另造文件。adapter 源码和测试已在提交 `8f3b14a` 中，本任务不重复实现；若出现任何意外源码差异必须报告路径和原因。任务结束后停止，不 commit/push。
