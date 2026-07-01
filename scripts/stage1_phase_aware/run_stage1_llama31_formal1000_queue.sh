#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${STAGE1_REPO_ROOT:-/data/goodtaste_workspace/llama-prefix}"
cd "$REPO_ROOT"

MODEL_KEY=llama31
LOG_ROOT="logs/stage1_formal/${MODEL_KEY}"
OUT_ROOT="results/stage1_phase_aware/formal/${MODEL_KEY}"
VALIDATION_DIR="results/stage1_phase_aware/validation"
MU_JSON="${VALIDATION_DIR}/${MODEL_KEY}_mu_trackB_rogue_v1.json"
DATASET_PATH="./data/single_prompt_bomb.json"
RUN_CONFIG_ROOT="${OUT_ROOT}/generated_single_prompt_configs"
VECTOR_POOL="./results/stage1_phase_aware/random_vector_pools/${MODEL_KEY}_stage1_vectors.pt"
PROMPT_LIMIT=1

export STAGE1_REPO_ROOT="$REPO_ROOT"
export STAGE1_VECTOR_POOL="$VECTOR_POOL"

mkdir -p \
  "$LOG_ROOT/trackA" \
  "$LOG_ROOT/trackB" \
  "$OUT_ROOT/trackA" \
  "$OUT_ROOT/trackB" \
  "$OUT_ROOT/summaries" \
  "$RUN_CONFIG_ROOT" \
  "$VALIDATION_DIR"

run_step() {
  local name="$1"
  shift
  local log_path="$1"
  shift
  echo "[$(date "+%F %T")] START $name" | tee -a "$LOG_ROOT/formal1000_queue.log"
  "$@" 2>&1 | tee "$log_path"
  echo "[$(date "+%F %T")] END   $name" | tee -a "$LOG_ROOT/formal1000_queue.log"
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

ensure_configs() {
  python scripts/stage1_phase_aware/build_stage1_configs.py --models "$MODEL_KEY"
}

measure_mu() {
  local config_path="configs/local/stage1_trackB_${MODEL_KEY}_rogue_v1.json"
  if [[ -s "$MU_JSON" ]]; then
    if python -m json.tool "$MU_JSON" >/dev/null 2>&1; then
      echo "[$(date "+%F %T")] SKIP valid existing $MU_JSON" | tee -a "$LOG_ROOT/formal1000_queue.log"
      return
    fi
    local corrupt_path="${MU_JSON}.corrupt.$(date +%Y%m%d_%H%M%S)"
    echo "[$(date "+%F %T")] MOVE corrupt $MU_JSON -> $corrupt_path" | tee -a "$LOG_ROOT/formal1000_queue.log"
    mv "$MU_JSON" "$corrupt_path"
  fi

  run_step "measure_mu_${MODEL_KEY}" "$LOG_ROOT/measure_mu.log" \
    python -u scripts/stage1_phase_aware/measure_activation_norm.py \
      --config "$config_path" \
      --output "$MU_JSON"
}

run_group() {
  local track="$1"
  local group="$2"
  local base_config_path="configs/local/stage1_${track}_${MODEL_KEY}_${group}.json"
  local config_path="$RUN_CONFIG_ROOT/stage1_${track}_${MODEL_KEY}_${group}_single_prompt_bomb.json"
  local out_path="$OUT_ROOT/${track}/stage1_${track}_${MODEL_KEY}_${group}_formal_v0000_0999.json"
  local log_path="$LOG_ROOT/${track}/${track}_${group}_v0000_0999.log"

  build_single_prompt_config "$base_config_path" "$config_path"

  if [[ -s "$out_path" ]]; then
    if python -m json.tool "$out_path" >/dev/null 2>&1; then
      echo "[$(date "+%F %T")] SKIP valid existing $out_path" | tee -a "$LOG_ROOT/formal1000_queue.log"
      return
    fi
    local corrupt_path="${out_path}.corrupt.$(date +%Y%m%d_%H%M%S)"
    echo "[$(date "+%F %T")] MOVE corrupt $out_path -> $corrupt_path" | tee -a "$LOG_ROOT/formal1000_queue.log"
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
    --output "$OUT_ROOT/summaries/stage1_${track}_${MODEL_KEY}_${group}_formal_summary.json"
}

ensure_configs
measure_mu

for group in rogue_v1 no_cache decode_only full first_k decay; do
  run_group trackA "$group"
done

for group in rogue_v1 no_cache decode_only full first_k decay; do
  run_group trackB "$group"
done

echo "[$(date "+%F %T")] ALL DONE" | tee -a "$LOG_ROOT/formal1000_queue.log"
