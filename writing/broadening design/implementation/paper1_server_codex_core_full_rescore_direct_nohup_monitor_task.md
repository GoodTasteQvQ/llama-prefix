# Core full rescore、screen gate 与 A/S：直接 nohup 监控任务书

版本：`core-full-rescore-direct-nohup-monitor-v1`

本任务替代 `paper1_server_codex_core_full_rescore_supervised_launch_task.md` 的 CPU probe 流程。继续使用原服务器 Codex 会话；不要启动执行代理或并行 GPU 会话。

## 当前判断

两次旧提交都没有创建 run、`.exit` 或 Python/Judge 记录。现有 readiness/preflight 已通过，CPU probe 不是科学 gate，之前也没有产生可验证的 probe receipt。本任务取消 CPU probe，直接提交一次 live full rescore，并由同一会话监控真实进程。不能因为监控窗口中断就重新提交；先检查原 PID、run 和日志。

本任务允许一次新的 live 提交，因为之前两次都在 run 创建前失败。完成后仍需负责人审查，才能进入正式评估。

## 不可修改的边界

- 只处理既有 F2 的 1,200 条 generation，20 cells、每 cell 60 条；不重新生成行为输出，不使用旧 Judge 标签。
- Judge 固定为 `enable_thinking=false`、`max_new_tokens=1296`、`strict_direct_json_v1`、greedy、float32、离线、GPU 0。
- 每条最多一次相同设置 retry；four-class 总上限 2,400；binary=0，generation retry=0；每 cell missing 最多 1 条（2%）。
- executor 成功后才运行现有 CPU-only `scripts/core_full_rescore_dose_adapter.py`；adapter 只读取本次 run。
- 不修改 Python 源码、测试、设计、config、manifest、F2、old recovery 或历史报告事实；不重跑 fixture、pytest 或 smoke。
- 不运行 Core formal evaluation、E1/E2/E3、人工审核或正式分析。

## 启动前只读检查

在 `/data/goodtaste_workspace/llama-prefix` 执行并记录到 `.codex-temp/core_full_rescore_direct_live/launch_precheck.txt`：

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 3
mkdir -p .codex-temp/core_full_rescore_direct_live logs/paper1_broadening results/paper1_broadening || exit 3
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR" TEMP="$TMPDIR" NX_DAEMON=false
export PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 MBD_GPU=0
PY=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$PY" || exit 3
test ! -e "$PWD/results/paper1_broadening/core-full-rescore-screen-as-20260919T031100Z-2436493" || exit 3
test ! -e "$PWD/results/paper1_broadening/core-full-rescore-screen-as-retry-20260919T035450Z-2443666" || exit 3
pgrep -af 'core_judge_full_rescore_run.py.*--live|core_full_rescore_dose_adapter.py' || true
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
df -h /data /tmp
printf 'python='; "$PY" --version
```

如果发现本任务的真实 worker、run 或旧 PID 仍在运行，停止并报告；不要杀其他用户进程。若 readiness 的 1,200/20×60、`FULL_RESCORE_BOUNDARY_AUDIT_PASS` 或 `CORE_RECOVERY_V3_PASS` 不再匹配，停止，不重建 manifest。

## 唯一 live nohup 提交

先生成唯一 tag；所有路径必须是普通文件路径。不要把 `.codex-temp` 或目录写在 `nohup` 的命令位置，不使用 `nohup.out` 作为成功判断。

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 3
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR" TEMP="$TMPDIR" NX_DAEMON=false
export PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 MBD_GPU=0
PY=/data/goodtaste_workspace/envs/llama-prefix/bin/python
TAG="core-full-rescore-direct-$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN="$PWD/results/paper1_broadening/$TAG"
LOG="$PWD/logs/paper1_broadening/$TAG.log"
PIDFILE="$PWD/logs/paper1_broadening/$TAG.pid"
EXITFILE="$PWD/logs/paper1_broadening/$TAG.exit"
MONITOR="$PWD/logs/paper1_broadening/$TAG.monitor.log"
test ! -e "$RUN" && test ! -e "$LOG" && test ! -e "$PIDFILE" && test ! -e "$EXITFILE" || exit 3

nohup env FULL_RESCORE_APPROVED=1 \
  "$PY" -u scripts/core_judge_full_rescore_run.py \
  --run-dir "$RUN" --live >"$LOG" 2>&1 < /dev/null &
PID=$!
printf '%s\n' "$PID" > "$PIDFILE"
printf 'tag=%s\nrun=%s\nlog=%s\npid=%s\n' "$TAG" "$RUN" "$LOG" "$PID" > "$MONITOR"
```

提交后立即记录外层命令和返回码。外层命令返回 0 只表示 nohup 已提交，不表示实验成功。

## 监控规则

同一服务器会话每 30–60 秒轮询一次，直到 PID 消失。轮询只读下列内容并追加到 `$MONITOR`：

```bash
date -u +%FT%TZ >> "$MONITOR"
if kill -0 "$PID" 2>/dev/null; then echo "PID_ALIVE" >> "$MONITOR"; else echo "PID_EXITED" >> "$MONITOR"; fi
tail -20 "$LOG" >> "$MONITOR"
test -f "$RUN/terminal_accounting.json" && cat "$RUN/terminal_accounting.json" >> "$MONITOR" || true
```

不要向 live 进程发送信号，不要因为暂时没有日志就重启。若 Codex 会话失去连接，重新连接后先用 PID、`ps`、run 目录和日志判断原任务状态；在状态不明时禁止新提交。

PID 消失后执行：

```bash
wait "$PID" 2>/dev/null; INNER_RC=$?
printf '%s\n' "$INNER_RC" > "$EXITFILE"
```

如果原 shell 已无法 `wait`，以进程退出状态、run 内 `terminal_accounting.json` 和日志为准，并明确记录无法取得 wait 返回码；不得填造 0。

仅当 executor 的退出状态为 0、`terminal_accounting.json` 为 `CORE_SCREEN_V3_PASS`、1,200 条记录和 20 cells 完整时，前台运行：

```bash
"$PY" -u scripts/core_full_rescore_dose_adapter.py --run-dir "$RUN" >"$RUN/adapter.log" 2>&1
ADAPTER_RC=$?
printf '%s\n' "$ADAPTER_RC" > "$RUN/adapter.exit"
```

executor 非零、run 未生成、进程异常退出、missing gate 失败或 adapter 非零时：保留所有已有证据并停止，不重跑，不补请求，不修改结果。

## 交付和报告

更新 `writing/broadening design/report/paper1_core_full_rescore_screen_as_report.md`，保留两次历史启动失败，新增本次实际状态。报告必须区分 nohup 外层返回码、PID、log、`.exit`、monitor、run 路径和进程轮询记录；1,200/20×60、每 cell parsed/missing、four-class/retry/binary 计数和 gate；四组 A/S 的 `dose_decisions.json`、rho、alpha、ordering 状态；Judge identity、raw/diagnostics、runtime/boundary 和 artifact hash。当前 runtime/release 占位字段不得写成 release PASS。

必须逐项同步：更新报告；`.codex-temp/core_full_rescore_direct_live/launch_precheck.txt`；本次 monitor、`.pid`、`.log`、`.exit`；完整新 run（manifest、request/attempt/event、terminal/runtime/boundary、Judge identity、dose/view/index、raw/diagnostics、hash）；以及任何实际修改的文件。不存在的文件如实标注。任务结束后停止，不 commit/push。保留 `FORMAL_EVALUATION_NOT_RUN`、`E1/E2/E3_NOT_RUN`、`HUMAN_REVIEW_NOT_RUN`。
