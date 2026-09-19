#!/usr/bin/env python3
"""Read-only boundary audit for full-rescore readiness."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path("/data/goodtaste_workspace/llama-prefix")
EVIDENCE = ROOT / ".codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def main() -> int:
    executor = ROOT / "scripts/core_judge_full_rescore_executor.py"
    launcher = ROOT / "scripts/core_judge_full_rescore_run.py"
    binding = json.loads((EVIDENCE / "input_binding.json").read_text(encoding="utf-8"))
    handoff = json.loads((EVIDENCE / "recovery_handoff_manifest.json").read_text(encoding="utf-8"))
    evidence_hashes = handoff.get("canonical_evidence_sha256", {})
    evidence_paths = handoff.get("recovery_evidence", {})
    evidence_hashes_pass = all(Path(evidence_paths.get(name, "")).is_file() and __import__("hashlib").sha256(Path(evidence_paths[name]).read_bytes()).hexdigest() == digest for name, digest in evidence_hashes.items())
    report = {"status": "FULL_RESCORE_BOUNDARY_AUDIT_PASS", "models_loaded": 0, "judge_requests": 0, "full_rescore_started": False, "core_screen_started": False, "formal_evaluation_started": False, "executor_model_imports": sorted(imports(executor) & {"torch", "transformers"}), "launcher_model_imports": sorted(imports(launcher) & {"torch", "transformers"}), "input_binding_pass": binding["status"] == "FULL_RESCORE_BINDING_PASS" and binding["logical_identity_count"] == 1200 and binding["all_cells_exactly_60"], "old_judge_labels_consumed": binding["old_judge_labels_consumed"], "recovery_handoff_pass": handoff["status"] == "CORE_RECOVERY_V3_PASS" and handoff["run_artifact_verification"] == 0 and evidence_hashes_pass, "recovery_canonical_evidence_hashes_pass": evidence_hashes_pass, "historical_stale_preserved": all(Path(p).is_file() for p in handoff["historical_stale"])}
    if report["executor_model_imports"] or report["launcher_model_imports"] or not report["input_binding_pass"] or not report["recovery_handoff_pass"] or not report["historical_stale_preserved"]:
        report["status"] = "FULL_RESCORE_READINESS_BLOCKED"
    (EVIDENCE / "final_boundary_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["status"] == "FULL_RESCORE_BOUNDARY_AUDIT_PASS" else 4


if __name__ == "__main__":
    raise SystemExit(main())
