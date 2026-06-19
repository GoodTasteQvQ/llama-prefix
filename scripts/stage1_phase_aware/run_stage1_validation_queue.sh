#!/usr/bin/env bash
set -euo pipefail

cd /data/goodtaste_workspace/prefix

LOG_DIR=logs/stage1_validation
OUT_DIR=results/stage1_phase_aware/validation
SUMMARY_DIR=results/stage1_phase_aware/summaries
mkdir -p "$LOG_DIR" "$OUT_DIR" "$SUMMARY_DIR"

run_step() {
  local name="$1"
  shift
  echo "[$(date "+%F %T")] START $name" | tee -a "$LOG_DIR/queue.log"
  "$@" 2>&1 | tee "$LOG_DIR/${name}.log"
  echo "[$(date "+%F %T")] END   $name" | tee -a "$LOG_DIR/queue.log"
}

run_step mu_qwen \
  python -u scripts/stage1_phase_aware/measure_activation_norm.py \
    --config configs/local/stage1_trackB_qwen25_rogue_v1.json \
    --output "$OUT_DIR/qwen25_mu_trackB_rogue_v1.json"

run_step trackA_A_rogue_v1 \
  python -u scripts/stage1_phase_aware/run_phase_semantic_matrix.py \
    --config configs/local/stage1_trackA_qwen25_rogue_v1.json \
    --output "$OUT_DIR/stage1_trackA_qwen25_rogue_v1_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-alpha 1.25

run_step trackA_B_no_cache \
  python -u scripts/stage1_phase_aware/run_phase_semantic_matrix.py \
    --config configs/local/stage1_trackA_qwen25_no_cache.json \
    --output "$OUT_DIR/stage1_trackA_qwen25_no_cache_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-alpha 1.00

run_step trackA_C_decode_only \
  python -u scripts/stage1_phase_aware/run_phase_semantic_matrix.py \
    --config configs/local/stage1_trackA_qwen25_decode_only.json \
    --output "$OUT_DIR/stage1_trackA_qwen25_decode_only_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-alpha 1.00

run_step trackA_D_full \
  python -u scripts/stage1_phase_aware/run_phase_semantic_matrix.py \
    --config configs/local/stage1_trackA_qwen25_full.json \
    --output "$OUT_DIR/stage1_trackA_qwen25_full_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-alpha 1.00

run_step trackA_E_first_k \
  python -u scripts/stage1_phase_aware/run_phase_semantic_matrix.py \
    --config configs/local/stage1_trackA_qwen25_first_k.json \
    --output "$OUT_DIR/stage1_trackA_qwen25_first_k_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-alpha 1.00

run_step trackA_F_decay \
  python -u scripts/stage1_phase_aware/run_phase_semantic_matrix.py \
    --config configs/local/stage1_trackA_qwen25_decay.json \
    --output "$OUT_DIR/stage1_trackA_qwen25_decay_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-alpha 1.00

run_step trackB_A_rogue_v1 \
  python -u scripts/stage1_phase_aware/run_rogue_calibrated_matrix.py \
    --config configs/local/stage1_trackB_qwen25_rogue_v1.json \
    --mu-json "$OUT_DIR/qwen25_mu_trackB_rogue_v1.json" \
    --output "$OUT_DIR/stage1_trackB_qwen25_rogue_v1_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-c 1.00

run_step trackB_B_no_cache \
  python -u scripts/stage1_phase_aware/run_rogue_calibrated_matrix.py \
    --config configs/local/stage1_trackB_qwen25_no_cache.json \
    --mu-json "$OUT_DIR/qwen25_mu_trackB_rogue_v1.json" \
    --output "$OUT_DIR/stage1_trackB_qwen25_no_cache_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-c 1.00

run_step trackB_C_decode_only \
  python -u scripts/stage1_phase_aware/run_rogue_calibrated_matrix.py \
    --config configs/local/stage1_trackB_qwen25_decode_only.json \
    --mu-json "$OUT_DIR/qwen25_mu_trackB_rogue_v1.json" \
    --output "$OUT_DIR/stage1_trackB_qwen25_decode_only_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-c 1.00

run_step trackB_D_full \
  python -u scripts/stage1_phase_aware/run_rogue_calibrated_matrix.py \
    --config configs/local/stage1_trackB_qwen25_full.json \
    --mu-json "$OUT_DIR/qwen25_mu_trackB_rogue_v1.json" \
    --output "$OUT_DIR/stage1_trackB_qwen25_full_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-c 1.00

run_step trackB_E_first_k \
  python -u scripts/stage1_phase_aware/run_rogue_calibrated_matrix.py \
    --config configs/local/stage1_trackB_qwen25_first_k.json \
    --mu-json "$OUT_DIR/qwen25_mu_trackB_rogue_v1.json" \
    --output "$OUT_DIR/stage1_trackB_qwen25_first_k_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-c 1.00

run_step trackB_F_decay \
  python -u scripts/stage1_phase_aware/run_rogue_calibrated_matrix.py \
    --config configs/local/stage1_trackB_qwen25_decay.json \
    --mu-json "$OUT_DIR/qwen25_mu_trackB_rogue_v1.json" \
    --output "$OUT_DIR/stage1_trackB_qwen25_decay_debug.json" \
    --mode debug \
    --single-vector-index 0 \
    --single-c 1.00

run_step summarize_stage1 \
  python -u scripts/stage1_phase_aware/summarize_stage1_results.py \
    --input \
      "$OUT_DIR/stage1_trackA_qwen25_rogue_v1_debug.json" \
      "$OUT_DIR/stage1_trackA_qwen25_no_cache_debug.json" \
      "$OUT_DIR/stage1_trackA_qwen25_decode_only_debug.json" \
      "$OUT_DIR/stage1_trackA_qwen25_full_debug.json" \
      "$OUT_DIR/stage1_trackA_qwen25_first_k_debug.json" \
      "$OUT_DIR/stage1_trackA_qwen25_decay_debug.json" \
      "$OUT_DIR/stage1_trackB_qwen25_rogue_v1_debug.json" \
      "$OUT_DIR/stage1_trackB_qwen25_no_cache_debug.json" \
      "$OUT_DIR/stage1_trackB_qwen25_decode_only_debug.json" \
      "$OUT_DIR/stage1_trackB_qwen25_full_debug.json" \
      "$OUT_DIR/stage1_trackB_qwen25_first_k_debug.json" \
      "$OUT_DIR/stage1_trackB_qwen25_decay_debug.json" \
    --output "$SUMMARY_DIR/qwen25_stage1_validation_summary.json"

echo "[$(date "+%F %T")] ALL DONE" | tee -a "$LOG_DIR/queue.log"
