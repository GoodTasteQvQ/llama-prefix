#!/usr/bin/env bash
set -euo pipefail
cd /data/goodtaste_workspace/prefix

LOG_ROOT=logs/stage1_formal/qwen25
MU_JSON=results/stage1_phase_aware/validation/qwen25_mu_trackB_rogue_v1.json
PROMPT_LIMIT=1

mkdir -p "$LOG_ROOT/trackA" "$LOG_ROOT/trackB"

run_step() {
  local name="$1"
  shift
  echo "[$(date "+%F %T")] START $name" | tee -a "$LOG_ROOT/first_shards_queue.log"
  "$@" 2>&1 | tee "$LOG_ROOT/${name}.log"
  echo "[$(date "+%F %T")] END   $name" | tee -a "$LOG_ROOT/first_shards_queue.log"
}

echo "[$(date "+%F %T")] QUEUE_ALL_BEGIN" | tee -a "$LOG_ROOT/first_shards_queue.log"

run_step trackA_rogue_v1_v0000_0999 \
  bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
    trackA \
    rogue_v1 \
    configs/local/stage1_trackA_qwen25_rogue_v1.json \
    results/stage1_phase_aware/formal/qwen25/trackA/stage1_trackA_qwen25_rogue_v1_formal_v0000_0999.json \
    0 999 "$PROMPT_LIMIT"

run_step trackA_decode_only_v0000_0999 \
  bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
    trackA \
    decode_only \
    configs/local/stage1_trackA_qwen25_decode_only.json \
    results/stage1_phase_aware/formal/qwen25/trackA/stage1_trackA_qwen25_decode_only_formal_v0000_0999.json \
    0 999 "$PROMPT_LIMIT"

run_step trackA_full_v0000_0999 \
  bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
    trackA \
    full \
    configs/local/stage1_trackA_qwen25_full.json \
    results/stage1_phase_aware/formal/qwen25/trackA/stage1_trackA_qwen25_full_formal_v0000_0999.json \
    0 999 "$PROMPT_LIMIT"

run_step trackB_rogue_v1_v0000_0999 \
  bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
    trackB \
    rogue_v1 \
    configs/local/stage1_trackB_qwen25_rogue_v1.json \
    results/stage1_phase_aware/formal/qwen25/trackB/stage1_trackB_qwen25_rogue_v1_formal_v0000_0999.json \
    0 999 "$PROMPT_LIMIT" \
    "$MU_JSON"

run_step trackB_decode_only_v0000_0999 \
  bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
    trackB \
    decode_only \
    configs/local/stage1_trackB_qwen25_decode_only.json \
    results/stage1_phase_aware/formal/qwen25/trackB/stage1_trackB_qwen25_decode_only_formal_v0000_0999.json \
    0 999 "$PROMPT_LIMIT" \
    "$MU_JSON"

run_step trackB_full_v0000_0999 \
  bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
    trackB \
    full \
    configs/local/stage1_trackB_qwen25_full.json \
    results/stage1_phase_aware/formal/qwen25/trackB/stage1_trackB_qwen25_full_formal_v0000_0999.json \
    0 999 "$PROMPT_LIMIT" \
    "$MU_JSON"

echo "[$(date "+%F %T")] ALL DONE" | tee -a "$LOG_ROOT/first_shards_queue.log"
