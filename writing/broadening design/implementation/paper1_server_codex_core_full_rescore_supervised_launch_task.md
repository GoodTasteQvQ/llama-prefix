# Core 启动验证与 full rescore 连续执行任务

版本：`core-full-rescore-supervised-launch-v1`

执行会话：继续原 Core full-rescore 会话；只有该会话执行本任务，不开并行 GPU 任务。本文件替代旧 launch-repair-v2 的启动步骤，旧记录保留。

## 负责人判断与授权

两次提交均未产生 live run。第二次外层 `launcher_script_rc=0` 只表示后台提交命令返回；0-byte log、无 `.exit`、无 run 和事后无任务进程不能定位具体退出原因。新同步的 `nohup.out` 仍只有 `.codex-temp/: .codex-temp/: Is a directory`，缺少与第二次启动关联的服务器原始时间证据，不得把它直接当作第二次的报错。`bash -n` 只验证语法，不证明后台链路能运行。

本任务授权顺序完成：只读检查 → CPU 启动验证与既有 preflight → 一次新的 live full rescore → screen gate → CPU A/S → 一份报告。CPU 验证通过即继续，不再提交 proposal 或申请 approval。验证失败则在 shell 层做一次有依据的最小修正并最多再验证一次；仍失败时停止。live 最多一次，不得自动恢复、重复提交或重新请求以验证结果。

不修改实验 Python 源码、测试、设计、config、manifest、旧 F2/recovery 或既有 raw。只允许新增本任务的两个临时 shell 文件、启动证据、一个独立 live run，以及追加报告。无需重跑已通过的 1,200-row fixture、全套 pytest 或模型 smoke。

## 1. 只读检查

在 `/data/goodtaste_workspace/llama-prefix` 工作，先确认两次旧 run 均不存在，没有实际的本任务 worker/Python 进程。不要把包含脚本名的检查命令本身当成 worker，不终止其他用户进程。

保存一份简短 `diagnostic.txt`，仅包含：

- 当前 UTC、git HEAD、旧 log/PID/`.exit`/run 的存在性与大小；服务器 `stat nohup.out` 和其现有内容。缺失也如实记录。
- `nohup`、`bash` 的命令解析类型及路径，`/usr/bin/nohup`、`/bin/bash`、`/usr/bin/env` 是否可执行；`BASH_ENV`/`ENV` 是否设置及其路径。不导出完整环境、令牌或无关用户的全量进程列表。
- GPU 0 当前进程和显存、磁盘可用空间、正式 Python 是否存在。GPU 0 忙时等待，不改用双卡。
- readiness 的 `FULL_RESCORE_BINDING_PASS`、1,200/20×60、`FULL_RESCORE_BOUNDARY_AUDIT_PASS`、recovery handoff 的 `CORE_RECOVERY_V3_PASS`。当前源码须与已审查版本一致；不重建 manifest 或修写 hash。

旧 run 名：

```text
core-full-rescore-screen-as-20260919T031100Z-2436493
core-full-rescore-screen-as-retry-20260919T035450Z-2443666
```

若发现实际 run 或活跃实验进程，停止并交付证据，不启动下一步。上述系统程序缺失或不是预期程序时，在 shell 修复范围内查清，不盲目换工具。

## 2. 保存两个明确的 shell 文件

使用 Linux LF，保存在 `.codex-temp/core_full_rescore_launch_v3/`。文件若已存在，先确认是否已有本任务 live 提交；不得覆盖证据或通过换名字绕过一次 live 上限。脚本不依赖 shell profile、环境中的 Bash 初始化文件或多行 `bash -c`。

`worker.sh`：

```bash
#!/bin/bash
set -u
task_mode=${1:?mode required}
task_run=${2:?output path required}
task_exit=${3:?exit path required}
finish() {
  task_rc=$?
  trap - EXIT
  printf '%s\n' "$task_rc" > "$task_exit"
  exit "$task_rc"
}
trap finish EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
printf 'WORKER_STARTED mode=%s pid=%s utc=%s\n' "$task_mode" "$$" "$(date -u +%FT%TZ)"
cd /data/goodtaste_workspace/llama-prefix || exit 3
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR" TEMP="$TMPDIR" NX_DAEMON=false
export PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 MBD_GPU=0
task_python=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$task_python" || exit 3
case "$task_mode" in
  probe)
    unset FULL_RESCORE_APPROVED
    "$task_python" -u -c 'import os,time; print("CPU_PROBE_STARTED",os.getpid(),flush=True); time.sleep(15); print("CPU_PROBE_FINISHED",flush=True)' || exit $?
    "$task_python" scripts/core_judge_full_rescore_run.py --run-dir "$task_run" --preflight || exit $?
    ;;
  live)
    export FULL_RESCORE_APPROVED=1
    "$task_python" scripts/core_judge_full_rescore_run.py --run-dir "$task_run" --live || exit $?
    "$task_python" scripts/core_full_rescore_dose_adapter.py --run-dir "$task_run" || exit $?
    ;;
  *) exit 3 ;;
esac
printf 'WORKER_FINISHED mode=%s utc=%s\n' "$task_mode" "$(date -u +%FT%TZ)"
```

`submit.sh`：

```bash
#!/bin/bash
set -u
task_mode=${1:?probe or live required}
case "$task_mode" in probe|live) ;; *) exit 3 ;; esac
cd /data/goodtaste_workspace/llama-prefix || exit 3
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR" TEMP="$TMPDIR" NX_DAEMON=false
task_base="$PWD/.codex-temp/core_full_rescore_launch_v3"
task_worker="$task_base/worker.sh"
test -f "$task_worker" || exit 3
task_tag="core-full-rescore-supervised-${task_mode}-$(date -u +%Y%m%dT%H%M%SZ)-$$"
task_receipt="$task_base/$task_tag"
mkdir "$task_receipt" || exit 3
if [ "$task_mode" = probe ]; then
  task_run="$task_receipt/preflight"
else
  task_run="$PWD/results/paper1_broadening/$task_tag"
fi
test ! -e "$task_run" || exit 3
printf 'mode=%s\nrun=%s\nreceipt=%s\n' "$task_mode" "$task_run" "$task_receipt" > "$task_receipt/launch.txt"
cat "$task_receipt/launch.txt"
/usr/bin/env -u BASH_ENV -u ENV /usr/bin/nohup /bin/bash --noprofile --norc "$task_worker" "$task_mode" "$task_run" "$task_receipt/worker.exit" > "$task_receipt/worker.log" 2>&1 < /dev/null &
task_pid=$!
printf '%s\n' "$task_pid" > "$task_receipt/worker.pid"
printf 'worker_pid=%s\n' "$task_pid"
wait "$task_pid"
task_rc=$?
printf '%s\n' "$task_rc" > "$task_receipt/supervisor.exit"
printf 'SUPERVISOR_FINISHED rc=%s receipt=%s\n' "$task_rc" "$task_receipt"
exit "$task_rc"
```

`wait` 是关键：外层 shell 必须等待实际 `nohup` 子进程，不能提交后台后立即结束。不要给 `submit.sh` 再加 `&`、`timeout` 或自动重试。本方案仍使用 nohup，但不依赖提交 shell 提前退出后后台进程必然存活的假设。无需改系统设置、安装服务或引入新调度框架。

## 3. CPU 验证通过后自动继续一次 live

运行 shell 检查前把临时目录设在本项目 `.codex-temp`。先对两个文件执行 `bash -n` 并记录结果。然后通过执行工具直接运行下面命令，工作目录为本项目；若工具支持，关闭 login shell：

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash --noprofile --norc .codex-temp/core_full_rescore_launch_v3/submit.sh probe
```

执行工具初次等待时间设为约 1 秒；若返回 session ID，继续轮询该 session，不另开一个 probe。15 秒的标准库等待用于验证工具返回后进程仍能走到结束，不加载 torch、模型或 Judge。之后现有 launcher 的 `--preflight` 仅做 CPU 输入核验；它的输出放在 receipt 目录，不能冒充 live run。

CPU gate 通过条件：`WORKER_STARTED`、`CPU_PROBE_STARTED`、`CPU_PROBE_FINISHED`、`WORKER_FINISHED` 都存在，`worker.exit=0`、`supervisor.exit=0`、执行工具最终退出 0，且 `preflight/launcher_status.json` 为 `PRECHECK_PASS`、1,200 输入、model/Judge=0、绑定及保护 hash 通过。

失败时优先用真实 stderr、`worker.exit`/`supervisor.exit` 和启动标记判断退出层次。不要把猜测（例如父进程清理、BASH_ENV 或 nohup wrapper）写成已证实根因。只有 shell 层问题允许做一次最小修正，再用新 receipt 验证一次；若是 Python/config/输入不符，或两次 probe 都失败，停止交付。禁止为探测 shell 故障调用 `--live`，禁止扩大诊断到系统配置修改。

CPU gate 通过，且 GPU 0 可用、当前未产生任何本任务 live run 后，直接执行一次：

```bash
/usr/bin/env -u BASH_ENV -u ENV /bin/bash --noprofile --norc .codex-temp/core_full_rescore_launch_v3/submit.sh live
```

保持同一个工具 session 持续监测，允许分次轮询，不能因工具返回 session ID 就结束会话或宣称任务完成。只读观察相应 receipt 日志和新 run 的进度。若 live 失败，保留部分输出并停止，不做第二次 live。若工具连接失去跟踪，先检查原 worker/Python/run 的真实状态；不能凭没有 session 就重新提交。

## 4. 科学边界与结果判定

- 仅对既有 F2 的 1,200 条 generation 重评分，20 cells 各 60；不使用旧 Judge 标签，不重新生成行为输出。
- Qwen3 Judge：`enable_thinking=false`、`max_new_tokens=1296`、`strict_direct_json_v1`、greedy、float32、GPU 0、离线。每条最多一次原设置 retry，总 four-class 上限 2,400；binary、generation retry 均为 0。
- 原 2% missing gate 保持不变，每 cell 最多 1/60 missing；按现有 executor 的失败即停规则执行，不改 retry/missing 行为。
- executor 成功才执行已有 `core_full_rescore_dose_adapter.py`，读取本次 run，为 Qwen/Llama × rogue/contrastive 四组按原五个 rho 和 `choose_doses` 规则选择 A/S。不扩大剂量网格。
- `A_NOT_ESTABLISHED`、`S_NOT_ATTAINED`、A=S、ordering 不成立均可是真实结果，不据此调参或重跑。`dose_decision.json` 只有 screen gate 信息；四组实际 A/S 必须查 `dose_decisions.json`，不能混淆。
- 现有 runtime/boundary 文件包含 `DEFERRED`/null/占位字段，不能据此证明模型未加载或 release PASS。保留原文件，报告用本次 Judge identity、request/event、实际进程结束及 GPU 进程记录说明事实；进程退出不等于已验证 `runtime.release()` 内部步骤。本任务不为此重构实现。
- Core 正式评估、E1/E2/E3、human packet 和正式分析均不在本任务范围。

## 5. 一次收尾审查、报告与同步

追加更新 `writing/broadening design/report/paper1_core_full_rescore_screen_as_report.md`，保留两次历史失败事实。在报告顶部增加当前最新状态，旧段落标为历史记录，避免成功后标题仍误写 blocked。

一次边界自查只涵盖：shell/probe 证据、唯一 live、1,200/20×60、调用/retry、2% gate、四组 A/S、旧输入保护、进程结束与已知 release 局限、输出 hash。不要另增审核框架、再跑 fixture 或发送验证请求。没有真实证据时不得填 PASS。

报告写清本次实际外层工具命令及工具返回、session ID（若有）、脚本/PID/log/exit/run 路径、各 cell 的四类结果和 missing、四组 A/S rho/alpha/状态、实际 calls、停止原因、边界结论，以及 `FORMAL_EVALUATION_NOT_RUN`。无法追溯旧失败根因时如实写“历史根因未能确定，本次启动链路已通过/仍未通过”，不补写历史日志。

必须在最终回执逐项列出需要同步的实际文件：

1. 更新报告。
2. 完整 `.codex-temp/core_full_rescore_launch_v3/`：`diagnostic.txt`、两个实际 shell、语法检查、每次 probe 和唯一 live 的 receipt（`launch.txt`、`worker.pid`、`worker.log`、`worker.exit`、`supervisor.exit`、probe preflight 输出）、工具返回记录、相关进程/GPU 前后记录。没有产生的文件明确标注。
3. 若 live 已开始，完整 `results/paper1_broadening/<本次真实 run>/`：manifest、request/attempt/event、raw/diagnostics、terminal/runtime/boundary、Judge identity、两种 dose 文件、view/index 和 `artifact_hashes.sha256`。嵌在 JSONL 的 raw 同步整份 JSONL。运行结束后验证已有 hash 清单，不覆盖旧 run。
4. 若有允许范围内的 shell 修正，列明文件和理由；没有实验源码修改则写明。不得省略实际改动文件。

报告和以上证据通过 SFTP 同步；本任务不 commit/push、不打包模型权重。完成或阻断后停止，等待负责人审查后才进入正式评估。
