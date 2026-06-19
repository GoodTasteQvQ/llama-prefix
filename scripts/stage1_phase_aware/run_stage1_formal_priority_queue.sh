#!/usr/bin/env bash
set -euo pipefail

cd /data/goodtaste_workspace/prefix

LOG_ROOT=logs/stage1_formal/qwen25
OUT_ROOT=results/stage1_phase_aware/formal/qwen25
MU_JSON=results/stage1_phase_aware/validation/qwen25_mu_trackB_rogue_v1.json
PROMPT_LIMIT=100

mkdir -p "$LOG_ROOT/trackA" "$LOG_ROOT/trackB" "$OUT_ROOT/trackA" "$OUT_ROOT/trackB" "$OUT_ROOT/summaries"

run_step() {
  local name="$1"
  shift
  local log_path="$1"
  shift
  echo "[$(date "+%F %T")] START $name" | tee -a "$LOG_ROOT/priority_queue.log"
  "$@" 2>&1 | tee "$log_path"
  echo "[$(date "+%F %T")] END   $name" | tee -a "$LOG_ROOT/priority_queue.log"
}

run_group_shards() {
  local track="$1"
  local group="$2"
  local config_path="$3"

  local shard_start
  for shard_start in 100 200 300 400 500 600 700 800 900; do
    local shard_end=$((shard_start + 99))
    local shard_tag
    shard_tag=$(printf "v%04d_%04d" "$shard_start" "$shard_end")
    local out_path="$OUT_ROOT/${track}/stage1_${track}_qwen25_${group}_formal_${shard_tag}.json"
    local log_path="$LOG_ROOT/${track}/${track}_${group}_${shard_tag}.log"
    if [[ "$track" == "trackA" ]]; then
      run_step "${track}_${group}_${shard_tag}" "$log_path" \
        bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
          "$track" "$group" "$config_path" "$out_path" "$shard_start" "$shard_end" "$PROMPT_LIMIT"
    else
      run_step "${track}_${group}_${shard_tag}" "$log_path" \
        bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
          "$track" "$group" "$config_path" "$out_path" "$shard_start" "$shard_end" "$PROMPT_LIMIT" "$MU_JSON"
    fi
  done
}

run_group_summary() {
  local track="$1"
  local group="$2"
  python -u scripts/stage1_phase_aware/summarize_stage1_results.py \
    --input "$OUT_ROOT/${track}/stage1_${track}_qwen25_${group}_formal_v*.json" \
    --output "$OUT_ROOT/summaries/stage1_${track}_qwen25_${group}_formal_summary.json"
}

# Priority groups only. The v0000_0099 smoke shard is assumed to have been run already.
run_group_shards trackA rogue_v1 configs/local/stage1_trackA_qwen25_rogue_v1.json
run_group_summary trackA rogue_v1

run_group_shards trackA decode_only configs/local/stage1_trackA_qwen25_decode_only.json
run_group_summary trackA decode_only

run_group_shards trackA full configs/local/stage1_trackA_qwen25_full.json
run_group_summary trackA full

run_group_shards trackB rogue_v1 configs/local/stage1_trackB_qwen25_rogue_v1.json
run_group_summary trackB rogue_v1

run_group_shards trackB decode_only configs/local/stage1_trackB_qwen25_decode_only.json
run_group_summary trackB decode_only

run_group_shards trackB full configs/local/stage1_trackB_qwen25_full.json
run_group_summary trackB full

echo "[$(date "+%F %T")] ALL DONE" | tee -a "$LOG_ROOT/priority_queue.log"
