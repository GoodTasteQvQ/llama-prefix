#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MBD_PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$MBD_PROJECT_ROOT" || exit 1
mkdir -p "$MBD_PROJECT_ROOT/.codex-temp"
export MBD_PROJECT_ROOT
export TMPDIR="$MBD_PROJECT_ROOT/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export NX_DAEMON=false
export PYTHONUNBUFFERED=1
export MBD_MODEL_PYTHON="${MBD_MODEL_PYTHON:-/data/goodtaste_workspace/envs/llama-prefix/bin/python}"
export MBD_STATS_PYTHON="${MBD_STATS_PYTHON:-/data/goodtaste_workspace/envs/stage3-stats-py31210/bin/python}"
export MBD_GPU="${MBD_GPU:-0}"
case "$MBD_GPU" in
  0|1) ;;
  *) printf '%s\n' 'MBD_GPU must name exactly one physical GPU: 0 or 1.' >&2; exit 2 ;;
esac
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES="$MBD_GPU"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export HF_HOME="$MBD_PROJECT_ROOT/.hf_cache"
export MBD_OUTPUT_ROOT="$MBD_PROJECT_ROOT/results/paper1_broadening"
export MBD_LOG_ROOT="$MBD_PROJECT_ROOT/logs/paper1_broadening"
mkdir -p "$MBD_OUTPUT_ROOT" "$MBD_LOG_ROOT"
test -x "$MBD_MODEL_PYTHON"

if [[ $# -eq 0 ]]; then
  exec "$MBD_MODEL_PYTHON" "$MBD_PROJECT_ROOT/scripts/paper1_broadening.py" --help
fi

exec "$MBD_MODEL_PYTHON" "$MBD_PROJECT_ROOT/scripts/paper1_broadening.py" "$@"
