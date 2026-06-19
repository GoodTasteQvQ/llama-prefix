#!/usr/bin/env python
"""Generate local-path config copies for offline or ModelScope-based server runs."""

from __future__ import annotations

import argparse
from pathlib import Path
import json


HF_TO_LOCAL_KEY = {
    "Qwen/Qwen2.5-7B-Instruct": "qwen",
    "meta-llama/Llama-3.1-8B-Instruct": "llama31",
    "mistralai/Mistral-7B-Instruct-v0.3": "mistral",
}


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Clone JSON configs and rewrite model names to local model paths.",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=repo_root / "configs",
        help="Directory containing source JSON configs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "configs" / "server_local",
        help="Directory for rewritten configs.",
    )
    parser.add_argument(
        "--qwen-path",
        default="/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct",
        help="Local path for Qwen2.5-7B-Instruct.",
    )
    parser.add_argument(
        "--llama31-path",
        default="/data/goodtaste_workspace/models/Meta-Llama-3.1-8B-Instruct",
        help="Local path for Llama-3.1-8B-Instruct.",
    )
    parser.add_argument(
        "--mistral-path",
        default="/data/goodtaste_workspace/models/Mistral-7B-Instruct-v0.3",
        help="Local path for Mistral-7B-Instruct-v0.3.",
    )
    return parser


def local_path_map(args: argparse.Namespace) -> dict[str, str]:
    return {
        "qwen": args.qwen_path,
        "llama31": args.llama31_path,
        "mistral": args.mistral_path,
    }


def rewrite_payload(payload: dict, replacements: dict[str, str]) -> tuple[dict, bool]:
    changed = False

    model_block = payload.get("model")
    if isinstance(model_block, dict):
        original = model_block.get("model_name")
        key = HF_TO_LOCAL_KEY.get(original)
        if key:
            model_block["model_name"] = replacements[key]
            changed = True

    top_level_model_name = payload.get("model_name")
    key = HF_TO_LOCAL_KEY.get(top_level_model_name)
    if key:
        payload["model_name"] = replacements[key]
        changed = True

    return payload, changed


def main() -> int:
    args = build_parser().parse_args()
    source_dir = args.config_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    replacements = local_path_map(args)
    processed = 0
    changed = 0

    for path in sorted(source_dir.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rewritten, was_changed = rewrite_payload(payload, replacements)
        target = output_dir / path.relative_to(source_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(rewritten, ensure_ascii=False, indent=2), encoding="utf-8")
        processed += 1
        if was_changed:
            changed += 1

    print(f"Processed {processed} config files into {output_dir}")
    print(f"Rewrote local model paths in {changed} config files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
