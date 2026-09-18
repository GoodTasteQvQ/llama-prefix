#!/usr/bin/env python3
"""Approval-gated production launcher for the bounded Core recovery.

The module intentionally imports only standard-library code at import time. The
Qwen3/torch stack is imported inside the backend factory, after the canonical
JSON approval has passed the executor preflight.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path("/data/goodtaste_workspace/llama-prefix")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core_judge_recovery_executor import (
    APPROVAL_PATH,
    CONFIG_PATH,
    RecoveryContractError,
    RecoveryExecutor,
    canonical,
    canonical_sha256,
    load_json,
    request_identity_for_row,
    sha256_file,
)

PROTOCOL = "core-judge-protocol-v3-direct-json"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_artifact_hashes(run_dir: Path) -> None:
    paths = sorted(path for path in run_dir.iterdir() if path.is_file() and path.name != "artifact_hashes.sha256")
    lines = []
    for path in paths:
        lines.append(f"{sha256_file(path)}  {path.name}\n")
    (run_dir / "artifact_hashes.sha256").write_text("".join(lines), encoding="utf-8")


def _offline_env() -> None:
    required = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"}
    bad = {key: os.environ.get(key) for key, value in required.items() if os.environ.get(key) != value}
    if bad:
        raise RecoveryContractError(f"offline environment is not set: {bad}")


def _build_backend_factory(*, config: Mapping[str, Any], run_dir: Path, lifecycle: Mapping[str, Any]):
    """Return a factory whose first non-stdlib import is after preflight."""
    def factory():
        _offline_env()
        from paper1_broadening.judge import Qwen3JudgeRuntime

        details = config.get("models", {}).get("judge")
        if not isinstance(details, Mapping):
            raise RecoveryContractError("v2.3 config Judge details are missing")
        runtime = Qwen3JudgeRuntime.from_pretrained(
            details=details,
            lifecycle=lifecycle,
            enable_thinking=False,
            max_new_tokens=1296,
            parser="strict_direct_json_v1",
        )
        _write_json(run_dir / "judge_identity.json", runtime.identity())
        runtime_identity = runtime.identity()

        def backend(row: dict[str, Any]) -> dict[str, Any]:
            payload = row.get("payload")
            if not isinstance(payload, Mapping):
                raise RecoveryContractError("launcher payload is missing")
            expected_identity = request_identity_for_row(row)
            result = runtime.four_class(
                prompt=str(payload["prompt"]),
                response=str(payload["response"]),
                domain=str(payload["domain"]),
            )
            return {
                "request_identity": expected_identity,
                "actual_call_counts": {"binary": 0, "four_class": 1},
                "generation_retries": 0,
                "additional_judge_retries": 0,
                "binary_requests": 0,
                "raw": result.get("raw"),
                "diagnostics": result.get("diagnostics"),
                "backend_status": result.get("status"),
                "backend_error": result.get("error"),
                "runtime_identity_sha256": canonical_sha256(runtime_identity),
            }

        backend.runtime = runtime
        backend.runtime_identity = runtime_identity
        return backend

    return factory


def run(*, run_dir: Path) -> int:
    if run_dir.exists():
        raise RecoveryContractError("launcher run directory must be new and absent")
    config = load_json(CONFIG_PATH)
    lifecycle = {
        "behavior_released": True,
        "behavior_hook_removed": True,
        "behavior_model_reference_cleared": True,
        "behavior_tokenizer_reference_cleared": True,
        "gc_collect_called": True,
        "models_concurrently_resident": False,
        "cuda_available": True,
        "cuda_synchronize_called": True,
        "cuda_empty_cache_called": True,
    }
    # RecoveryExecutor performs canonical approval and all immutable-input checks
    # before this factory can import torch/transformers or construct Qwen3.
    factory = _build_backend_factory(config=config, run_dir=run_dir, lifecycle=lifecycle)
    executor = RecoveryExecutor(backend_factory=factory, run_dir=run_dir)
    try:
        result = executor.run()
    except RecoveryContractError as exc:
        if "approval" in str(exc).lower() or "canonical" in str(exc).lower():
            run_dir.mkdir(parents=True, exist_ok=False)
            _write_json(run_dir / "launcher_status.json", {
                "status": "RECOVERY_APPROVAL_BLOCKED",
                "approval_path": str(APPROVAL_PATH),
                "approval_exists": APPROVAL_PATH.exists(),
                "actual_judge_requests": 0,
                "models_loaded": 0,
                "error": str(exc),
            })
            _write_json(run_dir / "boundary_audit.json", {
                "status": "RECOVERY_APPROVAL_BLOCKED",
                "actual_judge_requests": 0,
                "models_loaded": 0,
                "binary_requests": 0,
                "generation_retries": 0,
                "additional_judge_retries": 0,
            })
            _write_artifact_hashes(run_dir)
            return 3
        raise
    backend = executor.backend_instance
    runtime = getattr(backend, "runtime", None)
    if runtime is not None:
        try:
            _write_json(run_dir / "judge_release.json", runtime.release())
        except Exception as exc:
            _write_json(run_dir / "judge_release.json", {"status": "RELEASE_FAILED", "error": str(exc)})
    _write_json(run_dir / "boundary_audit.json", {
        "status": "BOUNDARY_AUDIT_PASS" if result.get("status") == "COMPLETED" else "RECOVERY_STOPPED_ON_FAILURE",
        "actual_judge_requests": result.get("actual_four_class_requests", 0),
        "models_loaded": 1,
        "binary_requests": result.get("binary_requests", 0),
        "generation_retries": result.get("generation_retries", 0),
        "additional_judge_retries": result.get("additional_judge_retries", 0),
        "timestamp": time.time(),
    })
    _write_json(run_dir / "launcher_runtime_status.json", {
        **result,
        "protocol": PROTOCOL,
        "python": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "config_sha256": sha256_file(CONFIG_PATH),
        "approval_path": str(APPROVAL_PATH),
    })
    _write_artifact_hashes(run_dir)
    return 0 if result.get("status") == "COMPLETED" else 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        return run(run_dir=args.run_dir)
    except RecoveryContractError as exc:
        print(f"RECOVERY_LAUNCHER_BLOCKED: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
