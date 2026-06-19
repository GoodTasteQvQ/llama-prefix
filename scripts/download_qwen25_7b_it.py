#!/usr/bin/env python
"""Download Qwen2.5-7B-Instruct from ModelScope."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable


MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"


def _split_patterns(values: Iterable[str] | None) -> list[str] | None:
    if not values:
        return None

    patterns: list[str] = []
    for value in values:
        patterns.extend(part.strip() for part in value.split(",") if part.strip())
    return patterns or None


def _import_modelscope_download_tools():
    try:
        from modelscope import HubApi
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError as exc:
        raise SystemExit(
            "ModelScope SDK is not installed. Install it with:\n"
            "  python -m pip install -U modelscope"
        ) from exc

    return HubApi, snapshot_download


def build_parser() -> argparse.ArgumentParser:
    default_local_dir = Path("/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct")

    parser = argparse.ArgumentParser(
        description="Download Qwen2.5-7B-Instruct from ModelScope.",
    )
    parser.add_argument(
        "--model-id",
        default=MODEL_ID,
        help=f"ModelScope model id. Default: {MODEL_ID}",
    )
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=default_local_dir,
        help=f"Target directory. Default: {default_local_dir}",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional ModelScope branch, tag, or commit revision.",
    )
    parser.add_argument(
        "--allow-patterns",
        nargs="*",
        default=None,
        help="Optional glob patterns to include, separated by spaces or commas.",
    )
    parser.add_argument(
        "--ignore-patterns",
        nargs="*",
        default=None,
        help="Optional glob patterns to exclude, separated by spaces or commas.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("MODELSCOPE_API_TOKEN") or os.environ.get("MODELSCOPE_TOKEN"),
        help="Optional ModelScope token. Defaults to MODELSCOPE_API_TOKEN or MODELSCOPE_TOKEN.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    hub_api, snapshot_download = _import_modelscope_download_tools()

    local_dir = args.local_dir.expanduser().resolve()
    local_dir.mkdir(parents=True, exist_ok=True)

    kwargs = {
        "model_id": args.model_id,
        "local_dir": str(local_dir),
    }

    if args.revision:
        kwargs["revision"] = args.revision

    allow_patterns = _split_patterns(args.allow_patterns)
    if allow_patterns:
        kwargs["allow_patterns"] = allow_patterns

    ignore_patterns = _split_patterns(args.ignore_patterns)
    if ignore_patterns:
        kwargs["ignore_patterns"] = ignore_patterns

    print(f"Downloading {args.model_id} from ModelScope...")
    print(f"Target directory: {local_dir}")

    if args.token:
        hub_api().login(args.token)

    model_dir = snapshot_download(**kwargs)

    print("Download finished.")
    print(f"Model directory: {model_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
