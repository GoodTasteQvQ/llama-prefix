#!/usr/bin/env python3
"""Build a non-overwriting local asset inventory without rewriting source data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.local_temp import require_project_local_temp  # noqa: E402
from stage3_pipeline.offline_assets import load_p1_harmful_active_entry  # noqa: E402


def main() -> int:
    require_project_local_temp(ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--active-entry", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to overwrite output: {output}")
    loaded = load_p1_harmful_active_entry(args.asset_root, args.active_entry)
    inventory = {key: value for key, value in loaded.items() if key != "records"}
    inventory["schema_version"] = "paper1-stage3-offline-active-inventory-v1"
    inventory["network_fallback"] = False
    inventory["hf_cache_fallback"] = False
    inventory["alternate_file_fallback"] = False
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(inventory, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
    print(json.dumps({"marker": "STAGE3_OFFLINE_INVENTORY_BUILT", "asset_count": 1}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
