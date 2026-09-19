#!/usr/bin/env python3
"""Launcher for the independent full-rescore executor.

Default operation is preflight-only. Real model construction is intentionally
disabled in this readiness session; ``--fixture`` is the only execution mode.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path("/data/goodtaste_workspace/llama-prefix")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core_judge_full_rescore_executor import FullRescoreContractError, FullRescoreExecutor


def _fixture_backend(row: dict, retry_no: int) -> dict:
    # Deterministic fixture; the first attempt for one identity exercises retry.
    if row["ordinal"] == 1 and retry_no == 0:
        return {"request_identity": {"ordinal": row["ordinal"], "response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "parser": "strict_direct_json_v1", "enable_thinking": False, "max_new_tokens": 1296}, "raw": "not-json", "diagnostics": {"fixture": True}}
    domain = row["domain"]
    label = "safe" if domain == "harmful" else "helpful"
    return {"request_identity": {"ordinal": row["ordinal"], "response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "parser": "strict_direct_json_v1", "enable_thinking": False, "max_new_tokens": 1296}, "raw": json.dumps({"label": label, "rationale": "offline fixture"}), "diagnostics": {"fixture": True, "retry_no": retry_no}}


def _build_live_backend(*, run_dir: Path):
    """Construct the model only after FullRescoreExecutor.preflight succeeds."""
    if os.environ.get("FULL_RESCORE_APPROVED") != "1":
        raise FullRescoreContractError("FULL_RESCORE_APPROVED=1 is required for live execution")
    from paper1_broadening.judge import Qwen3JudgeRuntime

    config = json.loads((Path("/data/goodtaste_workspace/llama-prefix") / "configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json").read_text(encoding="utf-8"))
    details = config["models"]["judge"]
    lifecycle = {"behavior_released": True, "behavior_hook_removed": True, "behavior_model_reference_cleared": True, "behavior_tokenizer_reference_cleared": True, "gc_collect_called": True, "models_concurrently_resident": False, "cuda_available": True, "cuda_synchronize_called": True, "cuda_empty_cache_called": True}
    runtime = Qwen3JudgeRuntime.from_pretrained(details=details, lifecycle=lifecycle, enable_thinking=False, max_new_tokens=1296, parser="strict_direct_json_v1")
    (run_dir / "judge_identity.json").write_text(json.dumps(runtime.identity(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def backend(row: dict, retry_no: int) -> dict:
        payload = row["payload"]
        result = runtime.four_class(prompt=payload["prompt"], response=payload["response"], domain=payload["domain"])
        return {"request_identity": {"ordinal": row["ordinal"], "response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "parser": "strict_direct_json_v1", "enable_thinking": False, "max_new_tokens": 1296}, "actual_call_counts": {"four_class": 1, "binary": 0}, "raw": result.get("raw"), "diagnostics": result.get("diagnostics"), "backend_status": result.get("status"), "backend_error": result.get("error")}

    backend.runtime = runtime
    return backend


def run(*, run_dir: Path, fixture: bool = False, preflight_only: bool = False, live: bool = False) -> int:
    if sum(bool(value) for value in (fixture, preflight_only, live)) > 1:
        raise FullRescoreContractError("choose only one of --preflight, --fixture, or --live")
    if not fixture and not preflight_only and not live:
        raise FullRescoreContractError("real full rescore is disabled by default; use --preflight or --fixture")
    if preflight_only:
        details = FullRescoreExecutor(run_dir=run_dir, backend=_fixture_backend).preflight()
        details.update({"models_loaded": 0, "actual_judge_requests": 0})
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "launcher_status.json").write_text(json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    executor = FullRescoreExecutor(run_dir=run_dir, backend=_fixture_backend if fixture else None, backend_factory=None if fixture else lambda: _build_live_backend(run_dir=run_dir))
    result = executor.run()
    return 0 if result["status"] == "CORE_SCREEN_V3_PASS" else 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--live", action="store_true", help="approval-gated real execution; never used in readiness")
    args = parser.parse_args(argv)
    try:
        return run(run_dir=args.run_dir, fixture=args.fixture, preflight_only=args.preflight, live=args.live)
    except (FullRescoreContractError, OSError) as exc:
        print(f"FULL_RESCORE_LAUNCHER_BLOCKED: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
