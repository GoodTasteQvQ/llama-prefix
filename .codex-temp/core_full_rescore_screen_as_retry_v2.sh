#!/usr/bin/env bash
set -e
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
