#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 7 ]]; then
  echo "Usage: $0 <trackA|trackB> <group-name> <config-path> <output-path> <vector-start> <vector-end> <prompt-limit> [mu-json]"
  exit 1
fi

TRACK="$1"
GROUP_NAME="$2"
CONFIG_PATH="$3"
OUTPUT_PATH="$4"
VECTOR_START="$5"
VECTOR_END="$6"
PROMPT_LIMIT="$7"
MU_JSON="${8:-}"

REPO_ROOT="${STAGE1_REPO_ROOT:-/data/goodtaste_workspace/llama-prefix}"
VECTOR_POOL_ARG=()
if [[ -n "${STAGE1_VECTOR_POOL:-}" ]]; then
  VECTOR_POOL_ARG=(--vector-pool "$STAGE1_VECTOR_POOL")
fi

cd "$REPO_ROOT"

mkdir -p "$(dirname "$OUTPUT_PATH")"

if [[ "$TRACK" == "trackA" ]]; then
  python -u scripts/stage1_phase_aware/run_phase_semantic_matrix.py \
    --config "$CONFIG_PATH" \
    --output "$OUTPUT_PATH" \
    --mode formal \
    --vector-start "$VECTOR_START" \
    --vector-end "$VECTOR_END" \
    "${VECTOR_POOL_ARG[@]}" \
    --prompt-limit "$PROMPT_LIMIT" \
    --prompt-offset 0
elif [[ "$TRACK" == "trackB" ]]; then
  if [[ -z "$MU_JSON" ]]; then
    echo "trackB requires mu-json"
    exit 1
  fi
  python -u scripts/stage1_phase_aware/run_rogue_calibrated_matrix.py \
    --config "$CONFIG_PATH" \
    --mu-json "$MU_JSON" \
    --output "$OUTPUT_PATH" \
    --mode formal \
    --vector-start "$VECTOR_START" \
    --vector-end "$VECTOR_END" \
    "${VECTOR_POOL_ARG[@]}" \
    --prompt-limit "$PROMPT_LIMIT" \
    --prompt-offset 0
else
  echo "Unsupported track: $TRACK"
  exit 1
fi
