#!/usr/bin/env bash
set -euo pipefail

cd /data/goodtaste_workspace/prefix

LOG_ROOT=logs/stage1_formal/qwen25
OUT_ROOT=results/stage1_phase_aware/formal/qwen25
MU_JSON=results/stage1_phase_aware/validation/qwen25_mu_trackB_rogue_v1.json
DATASET_PATH=./data/single_prompt_bomb.json
RUN_CONFIG_ROOT="$OUT_ROOT/generated_single_prompt_configs"

# Match the existing v0000_0999 formal vector scans in trackA/trackB:
# 1000 vectors x 9 strengths on the single_prompt_bomb dataset.
# The 100-sample judge should be done later by subsampling these attack outputs.
PROMPT_LIMIT=1

mkdir -p "$LOG_ROOT/trackA" "$LOG_ROOT/trackB" "$OUT_ROOT/trackA" "$OUT_ROOT/trackB" "$OUT_ROOT/summaries" "$RUN_CONFIG_ROOT"

run_step() {
  local name="$1"
  shift
  local log_path="$1"
  shift
  echo "[$(date "+%F %T")] START $name" | tee -a "$LOG_ROOT/remaining_phase_queue.log"
  "$@" 2>&1 | tee "$log_path"
  echo "[$(date "+%F %T")] END   $name" | tee -a "$LOG_ROOT/remaining_phase_queue.log"
}

build_single_prompt_config() {
  local src_config="$1"
  local dst_config="$2"
  python - "$src_config" "$dst_config" "$DATASET_PATH" <<'PY'
import json
import sys
from pathlib import Path

src, dst, dataset_path = sys.argv[1:4]
payload = json.loads(Path(src).read_text(encoding="utf-8"))
dataset = payload.setdefault("dataset", {})
dataset["dataset_path"] = dataset_path
dataset["dataset_format"] = "json"
dataset["limit"] = 1
dataset["offset"] = 0
Path(dst).parent.mkdir(parents=True, exist_ok=True)
Path(dst).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

run_group() {
  local track="$1"
  local group="$2"
  local base_config_path="configs/local/stage1_${track}_qwen25_${group}.json"
  local config_path="$RUN_CONFIG_ROOT/stage1_${track}_qwen25_${group}_single_prompt_bomb.json"
  local out_path="$OUT_ROOT/${track}/stage1_${track}_qwen25_${group}_formal_v0000_0999.json"
  local log_path="$LOG_ROOT/${track}/${track}_${group}_v0000_0999.log"

  build_single_prompt_config "$base_config_path" "$config_path"

  if [[ -s "$out_path" ]]; then
    if python -m json.tool "$out_path" >/dev/null 2>&1; then
      echo "[$(date "+%F %T")] SKIP valid existing $out_path" | tee -a "$LOG_ROOT/remaining_phase_queue.log"
      return
    fi
    local corrupt_path="${out_path}.corrupt.$(date +%Y%m%d_%H%M%S)"
    echo "[$(date "+%F %T")] MOVE corrupt $out_path -> $corrupt_path" | tee -a "$LOG_ROOT/remaining_phase_queue.log"
    mv "$out_path" "$corrupt_path"
  fi

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
