#!/usr/bin/env bash
set -euo pipefail

cd /data/goodtaste_workspace/prefix

LOG_ROOT=logs/stage1_formal/qwen25
OUT_ROOT=results/stage1_phase_aware/formal/qwen25
MU_JSON=results/stage1_phase_aware/validation/qwen25_mu_trackB_rogue_v1.json

# Match the existing v0000_0999 formal vector scans in trackA/trackB.
# The 100-sample judge should be done later by subsampling these attack outputs.
PROMPT_LIMIT=1

mkdir -p "$LOG_ROOT/trackA" "$LOG_ROOT/trackB" "$OUT_ROOT/trackA" "$OUT_ROOT/trackB" "$OUT_ROOT/summaries"

run_step() {
  local name="$1"
  shift
  local log_path="$1"
  shift
  echo "[$(date "+%F %T")] START $name" | tee -a "$LOG_ROOT/remaining_phase_queue.log"
  "$@" 2>&1 | tee "$log_path"
  echo "[$(date "+%F %T")] END   $name" | tee -a "$LOG_ROOT/remaining_phase_queue.log"
}

run_group() {
  local track="$1"
  local group="$2"
  local config_path="configs/local/stage1_${track}_qwen25_${group}.json"
  local out_path="$OUT_ROOT/${track}/stage1_${track}_qwen25_${group}_formal_v0000_0999.json"
  local log_path="$LOG_ROOT/${track}/${track}_${group}_v0000_0999.log"

  if [[ "$track" == "trackA" ]]; then
    run_step "${track}_${group}_v0000_0999" "$log_path" \
      bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
        "$track" "$group" "$config_path" "$out_path" 0 999 "$PROMPT_LIMIT"
  else
    run_step "${track}_${group}_v0000_0999" "$log_path" \
      bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
        "$track" "$group" "$config_path" "$out_path" 0 999 "$PROMPT_LIMIT" "$MU_JSON"
  fi

  python -u scripts/stage1_phase_aware/summarize_stage1_results.py \
    --input "$out_path" \
    --output "$OUT_ROOT/summaries/stage1_${track}_${group}_formal_summary.json"
}

run_group trackA no_cache
run_group trackA first_k
run_group trackA decay

run_group trackB no_cache
run_group trackB first_k
run_group trackB decay

echo "[$(date "+%F %T")] ALL DONE" | tee -a "$LOG_ROOT/remaining_phase_queue.log"
