#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${STAGE1_REPO_ROOT:-/data/goodtaste_workspace/llama-prefix}"
cd "$REPO_ROOT"

MODEL_KEY=llama31
JUDGE_MODEL="${JUDGE_MODEL:-/data/goodtaste_workspace/models/Qwen3-8B}"
FORMAL_DIR="results/stage1_phase_aware/formal/${MODEL_KEY}"
INDIVIDUAL_DIR="results/stage1_phase_aware"
SUBSET_DIR="${FORMAL_DIR}/judge_subsets"
JUDGED_DIR="${FORMAL_DIR}/judged_qwen3_v2_100sample"
SUMMARY_DIR="${FORMAL_DIR}/judge_summaries"
SUMMARY_JSON="${SUMMARY_DIR}/${MODEL_KEY}_stage1_qwen3_v2_100sample_judge_summary.json"
BAD_CASE_DIR="${SUMMARY_DIR}/${MODEL_KEY}_stage1_qwen3_v2_100sample_bad_cases"
PLOT_DIR="${SUMMARY_DIR}/${MODEL_KEY}_stage1_qwen3_v2_100sample_plots"
LOG_ROOT="logs/stage1_formal/${MODEL_KEY}"
STRENGTHS="0.0,0.25,0.5,0.75,1.0,1.25,1.5,1.75,2.0"
GROUPS="trackA:rogue_v1,trackA:no_cache,trackA:decode_only,trackA:full,trackA:first_k,trackA:decay,trackB:rogue_v1,trackB:no_cache,trackB:decode_only,trackB:full,trackB:first_k,trackB:decay"

mkdir -p "$SUBSET_DIR" "$JUDGED_DIR" "$SUMMARY_DIR" "$LOG_ROOT/judge"

run_step() {
  local name="$1"
  shift
  local log_path="$1"
  shift
  echo "[$(date "+%F %T")] START $name" | tee -a "$LOG_ROOT/judge100_queue.log"
  "$@" 2>&1 | tee "$log_path"
  echo "[$(date "+%F %T")] END   $name" | tee -a "$LOG_ROOT/judge100_queue.log"
}

run_step "build_judge_subsets_${MODEL_KEY}" "$LOG_ROOT/judge/build_subsets.log" \
  python -u scripts/stage1_phase_aware/build_judge_subsets.py \
    --formal-dir "$FORMAL_DIR" \
    --individual-dir "$INDIVIDUAL_DIR" \
    --output-dir "$SUBSET_DIR" \
    --model-key "$MODEL_KEY" \
    --groups "$GROUPS" \
    --strengths "$STRENGTHS" \
    --samples-per-strength 100 \
    --seed 42 \
    --overwrite

while IFS= read -r subset_path; do
  subset_name="$(basename "$subset_path" .json)"
  out_path="$JUDGED_DIR/${subset_name}.judged.json"
  log_path="$LOG_ROOT/judge/${subset_name}.log"
  if [[ -s "$out_path" ]] && python -m json.tool "$out_path" >/dev/null 2>&1; then
    echo "[$(date "+%F %T")] SKIP valid existing $out_path" | tee -a "$LOG_ROOT/judge100_queue.log"
    continue
  fi
  run_step "judge_${subset_name}" "$log_path" \
    python -u scripts/judge_phase_outputs.py \
      --mode harmful \
      --input "$subset_path" \
      --output "$out_path" \
      --judge-model "$JUDGE_MODEL" \
      --torch-dtype bfloat16 \
      --max-new-tokens 256 \
      --rogue-max-new-tokens 128
done < <(python - "$SUBSET_DIR/index.json" <<'PY'
import json
import sys
from pathlib import Path

for row in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")):
    print(row["path"])
PY
)

run_step "summarize_judged_${MODEL_KEY}" "$LOG_ROOT/judge/summarize.log" \
  python -u scripts/summarize_phase_results.py \
    --dataset-type harmful \
    --input "$JUDGED_DIR"/*.judged.json \
    --output "$SUMMARY_JSON" \
    --bad-case-dir "$BAD_CASE_DIR"

run_step "plot_judged_${MODEL_KEY}" "$LOG_ROOT/judge/plot.log" \
  python -u scripts/stage1_phase_aware/plot_judge_v2_results.py \
    --summary "$SUMMARY_JSON" \
    --output-dir "$PLOT_DIR"

echo "[$(date "+%F %T")] ALL DONE" | tee -a "$LOG_ROOT/judge100_queue.log"
