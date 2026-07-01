#!/usr/bin/env bash
set -euo pipefail

cd /data/goodtaste_workspace/prefix

ROOT=results/stage1_phase_aware/formal/qwen25
SUBSET_DIR="$ROOT/judge_subsets"
JUDGED_DIR="$ROOT/judged_qwen3_v2"
SUMMARY_DIR="$ROOT/judge_summaries"
BAD_CASE_DIR="$SUMMARY_DIR/qwen25_stage1_remaining_phase_qwen3_v2_bad_cases"
LOG_DIR=logs/stage1_formal/qwen25/judge_remaining_phase
SUBSET_INDEX="$SUBSET_DIR/index_remaining_phase.json"
JUDGED_LIST="$LOG_DIR/judged_remaining_phase_files.txt"

JUDGE_MODEL="${JUDGE_MODEL:-/data/goodtaste_workspace/models/Qwen3-8B}"
TORCH_DTYPE="${TORCH_DTYPE:-bfloat16}"
GROUPS="trackA:no_cache,trackA:first_k,trackA:decay,trackB:no_cache,trackB:first_k,trackB:decay"
STRENGTHS="0.0,0.25,0.5,0.75,1.0,1.25,1.5,1.75,2.0"
SAMPLES_PER_STRENGTH=100
SEED=42

mkdir -p "$SUBSET_DIR" "$JUDGED_DIR" "$SUMMARY_DIR" "$BAD_CASE_DIR" "$LOG_DIR"

echo "[$(date "+%F %T")] BUILD_SUBSETS" | tee -a "$LOG_DIR/queue.log"
python -u scripts/stage1_phase_aware/build_judge_subsets.py \
  --formal-dir "$ROOT" \
  --individual-dir results/stage1_phase_aware \
  --output-dir "$SUBSET_DIR" \
  --groups "$GROUPS" \
  --strengths "$STRENGTHS" \
  --samples-per-strength "$SAMPLES_PER_STRENGTH" \
  --seed "$SEED" \
  --index-name index_remaining_phase.json \
  --overwrite \
  2>&1 | tee "$LOG_DIR/build_subsets.log"

echo "[$(date "+%F %T")] JUDGE_BEGIN" | tee -a "$LOG_DIR/queue.log"
rm -f "$JUDGED_LIST"
while IFS= read -r subset_path; do
  subset_name="$(basename "$subset_path")"
  judged_path="$JUDGED_DIR/${subset_name%.json}.judged.json"
  log_path="$LOG_DIR/${subset_name%.json}.log"

  echo "[$(date "+%F %T")] START $subset_name" | tee -a "$LOG_DIR/queue.log"
  python -u scripts/judge_phase_outputs.py \
    --input "$subset_path" \
    --output "$judged_path" \
    --judge-model "$JUDGE_MODEL" \
    --mode harmful \
    --torch-dtype "$TORCH_DTYPE" \
    2>&1 | tee "$log_path"
  echo "$judged_path" >> "$JUDGED_LIST"
  echo "[$(date "+%F %T")] END   $subset_name" | tee -a "$LOG_DIR/queue.log"
done < <(python - "$SUBSET_INDEX" <<'PY'
import json
import sys
from pathlib import Path

rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for row in rows:
    print(row["path"])
PY
)

echo "[$(date "+%F %T")] SUMMARIZE" | tee -a "$LOG_DIR/queue.log"
mapfile -t JUDGED_FILES < "$JUDGED_LIST"
python -u scripts/summarize_phase_results.py \
  --input "${JUDGED_FILES[@]}" \
  --dataset-type harmful \
  --output "$SUMMARY_DIR/qwen25_stage1_remaining_phase_qwen3_v2_judge_summary.json" \
  --bad-case-dir "$BAD_CASE_DIR" \
  2>&1 | tee "$LOG_DIR/summarize.log"

echo "[$(date "+%F %T")] ALL DONE" | tee -a "$LOG_DIR/queue.log"
