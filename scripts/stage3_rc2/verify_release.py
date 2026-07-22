#!/usr/bin/env python3
"""Build and verify the v3.5-rc2 design-freeze release closure.

The verifier operates only on repository design files and synthetic fixtures. It
cannot run P1, support, generation, automated judging, or human validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc2.md"
OLD_HASHES = ROOT / "writing/stage3 design/v3_5_rc2_contracts/preexisting_files.sha256.json"
RELEASE_MANIFEST = ROOT / "writing/stage3 design/v3_5_rc2_contracts/v3_5_rc2_release_manifest.json"

ARTIFACT_PATHS = tuple(sorted({
    "scripts/judge_phase_outputs.py",
    "scripts/stage3_design/v3_5_rc2/human_quota.py",
    "scripts/stage3_design/v3_5_rc2/two_phase_correction.py",
    "scripts/stage3_rc2/freeze_contract.py",
    "scripts/stage3_rc2/verify_release.py",
    "writing/stage3 design/paper1_attention_sink_mu_design_freeze_audit_v3_5_rc2_disposition.md",
    "writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc2.md",
    "writing/stage3 design/revision/paper1_attention_sink_mu_experiment_design_v3_5_rc1_to_v3_5_rc2_semantic_diff.md",
    "writing/stage3 design/v3_5_rc2_closure/C/binding_manifest.json",
    "writing/stage3 design/v3_5_rc2_closure/C/human_correction_quota_resource_spec.md",
    "writing/stage3 design/v3_5_rc2_closure/C/human_quota_golden.json",
    "writing/stage3 design/v3_5_rc2_closure/C/two_phase_correction_golden.json",
    "writing/stage3 design/v3_5_rc2_contracts/README_B_freeze_execution.md",
    "writing/stage3 design/v3_5_rc2_contracts/freeze_execution_contract.json",
    "writing/stage3 design/v3_5_rc2_contracts/golden/freeze_execution_cases.json",
    "writing/stage3 design/v3_5_rc2_contracts/preexisting_files.sha256.json",
    "writing/stage3 design/v3_5_rc2_contracts/v3_5_rc2_hash_manifest.json",
    "writing/stage3 design/v3_5_rc2_statistics/README.md",
    "writing/stage3 design/v3_5_rc2_statistics/fixtures/failure_golden_expected.json",
    "writing/stage3 design/v3_5_rc2_statistics/fixtures/failure_golden_input.json",
    "writing/stage3 design/v3_5_rc2_statistics/fixtures/statistical_golden_expected.json",
    "writing/stage3 design/v3_5_rc2_statistics/fixtures/statistical_golden_input.json",
    "writing/stage3 design/v3_5_rc2_statistics/reference_statistics.py",
    "writing/stage3 design/v3_5_rc2_statistics/statistical_reference_manifest.json",
    "writing/stage3 design/v3_5_rc2_statistics/verify_golden.py",
}))

BANNED_PROTOCOL_PATTERNS = {
    "K2": r"\bK2\b",
    "V2": r"\bV2\b",
    "attention analysis": r"\battention(?:[_ -]confirm|[_ -]association)?\b",
    "teacher-forced": r"teacher-forced",
    "power simulation": r"power[_ -]simulation",
    "coverage simulation": r"coverage[_ -]simulation",
    "rendering 2x2": r"rendering_2x2",
    "sampled decoding": r"(?:sampled|stochastic)[_ -]decoding",
    "P=100 fallback": r"\bP\s*=\s*100\b",
    "V=30 fallback": r"\bV\s*=\s*30\b",
    "removed statistical branch": r"model-based|p2-model|population-integration|160,?000",
    "unregistered interval fallback": r"marginal intervals if available",
    "retired Freeze A filename": r"measurement_freeze\.json",
    "retired Freeze B filename": r"behavior_freeze\.json",
    "retired RNG identity": r"canonical_unit_id",
    "retired available-arm rate": r"p_judge_full",
    "unused benign alias": r"\bN_b\b",
}


class VerificationError(RuntimeError):
    """Raised for a reproducible design-freeze verification failure."""


def canonical_bytes(value: Any, exclude_self: bool = False) -> bytes:
    if exclude_self and isinstance(value, dict):
        value = {key: item for key, item in value.items() if key != "self_sha256"}
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_self_hash(document: dict[str, Any], label: str) -> None:
    expected = document.get("self_sha256")
    actual = hashlib.sha256(canonical_bytes(document, exclude_self=True)).hexdigest()
    if expected != actual:
        raise VerificationError(f"{label} self hash mismatch: expected {expected}, got {actual}")


def build_release_manifest() -> dict[str, Any]:
    artifacts = []
    for relative in ARTIFACT_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise VerificationError(f"release artifact missing: {relative}")
        artifacts.append({"path": relative, "sha256": file_sha256(path), "length": path.stat().st_size})
    document = {
        "schema_version": "v3.5-rc2-release-manifest-v1",
        "protocol_version": "v3.5-rc2",
        "created_date": "2026-07-22",
        "source": {
            "path": "writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc1.md",
            "sha256": "f557fb8a06329f92778e9e1eb7ddb2822b05e80bf83784ba1ec243b9343fb85a",
        },
        "fixed_scope": {
            "behavior_models": 1,
            "P": 50,
            "V": 20,
            "human_items": 720,
            "logical_generation": 5580,
            "scheduled_judge_identities": 5580,
            "new_experiment_blocks": 0,
        },
        "preexisting_file_count": 28,
        "artifacts": artifacts,
        "non_outputs": {
            "formal_P1": False,
            "formal_support": False,
            "formal_generation": False,
            "formal_judge": False,
            "formal_human_experiment": False,
            "formal_results": False,
        },
    }
    document["self_sha256"] = hashlib.sha256(canonical_bytes(document)).hexdigest()
    return document


def verify_release_manifest() -> int:
    document = load_json(RELEASE_MANIFEST)
    validate_self_hash(document, "release manifest")
    paths = tuple(entry["path"] for entry in document["artifacts"])
    if paths != ARTIFACT_PATHS:
        raise VerificationError("release artifact list differs from the hard-coded closure")
    for entry in document["artifacts"]:
        path = ROOT / entry["path"]
        if not path.is_file():
            raise VerificationError(f"release artifact missing: {entry['path']}")
        if path.stat().st_size != entry["length"]:
            raise VerificationError(f"release artifact length mismatch: {entry['path']}")
        actual = file_sha256(path)
        if actual != entry["sha256"]:
            raise VerificationError(f"release artifact hash mismatch: {entry['path']}")
    if document["fixed_scope"] != {
        "behavior_models": 1,
        "P": 50,
        "V": 20,
        "human_items": 720,
        "logical_generation": 5580,
        "scheduled_judge_identities": 5580,
        "new_experiment_blocks": 0,
    }:
        raise VerificationError("release fixed_scope changed")
    if any(document["non_outputs"].values()):
        raise VerificationError("release manifest claims a forbidden formal output")
    return len(document["artifacts"])


def verify_preexisting_files() -> int:
    baseline = load_json(OLD_HASHES)
    files = baseline["files"]
    if len(files) != 28 or not baseline.get("captured_before_rc2_edits"):
        raise VerificationError("preexisting-file baseline is incomplete")
    for entry in files:
        path = ROOT / entry["path"]
        if not path.is_file():
            raise VerificationError(f"preexisting file missing: {entry['path']}")
        if path.stat().st_size != entry["length"] or file_sha256(path) != entry["sha256"]:
            raise VerificationError(f"preexisting file changed: {entry['path']}")
    return len(files)


def verify_nested_bindings() -> int:
    count = 0
    stats_dir = ROOT / "writing/stage3 design/v3_5_rc2_statistics"
    stats = load_json(stats_dir / "statistical_reference_manifest.json")
    if stats["runtime"]["python"] != platform.python_version():
        raise VerificationError("statistical reference Python runtime mismatch")
    for relative, expected in stats["sha256"].items():
        if file_sha256(stats_dir / relative) != expected:
            raise VerificationError(f"statistical binding mismatch: {relative}")
        count += 1

    b_dir = ROOT / "writing/stage3 design/v3_5_rc2_contracts"
    b_contract = load_json(b_dir / "freeze_execution_contract.json")
    b_manifest = load_json(b_dir / "v3_5_rc2_hash_manifest.json")
    validate_self_hash(b_contract, "freeze execution contract")
    validate_self_hash(b_manifest, "freeze binding manifest")
    for entry in b_manifest["files"]:
        if file_sha256(ROOT / entry["path"]) != entry["sha256"]:
            raise VerificationError(f"freeze binding mismatch: {entry['path']}")
        count += 1

    c_manifest = load_json(ROOT / "writing/stage3 design/v3_5_rc2_closure/C/binding_manifest.json")
    for entry in c_manifest["artifacts"]:
        if file_sha256(ROOT / entry["path"]) != entry["sha256"]:
            raise VerificationError(f"human/quota binding mismatch: {entry['path']}")
        count += 1
    return count


def verify_scope(protocol: str) -> int:
    failures = []
    for label, pattern in BANNED_PROTOCOL_PATTERNS.items():
        if re.search(pattern, protocol, flags=re.IGNORECASE):
            failures.append(label)
    if failures:
        raise VerificationError("scope residue: " + ", ".join(failures))
    return len(BANNED_PROTOCOL_PATTERNS)


def verify_cross_references(protocol: str) -> int:
    headings = set(re.findall(
        r"^#{2,4}\s+(\d+(?:\.\d+)*)(?:\.|\s)", protocol, flags=re.MULTILINE
    ))
    references = re.findall(r"\bsection\s+(\d+(?:\.\d+)*)\b", protocol, flags=re.IGNORECASE)
    missing = sorted(set(references) - headings)
    if missing:
        raise VerificationError("undefined section references: " + ", ".join(missing))
    return len(references)


def verify_budget_and_symbols(protocol: str) -> dict[str, int]:
    required_literals = (
        "P = 50",
        "V = 20",
        "N_human_items = 720",
        "N_benign_prompt = 30",
        "900+4000+50+600+30",
        "**5,580**",
        "human response items = 720",
        "primary annotation assignments = 2*720 = 1,440",
        "scheduled assignment upper bound = 2,160",
        "member_id` is metadata and is forbidden",
        "theta_hat_j = RD_two_phase_M",
        "theta_(j,b)_star = RD_two_phase_M",
        "define `M_k`",
        "mu_g_tw_s =",
        "n_j=|M_k|",
        "base_w_hi=N_h/n_h",
        "mu_all_tw_Qwen",
        "median_content_norm_Qwen",
        "E_generation_unattempted",
        "E_prejudge_terminal",
    )
    missing = [item for item in required_literals if item not in protocol]
    if missing:
        raise VerificationError("undefined/missing contracted symbol or budget literal: " + repr(missing))
    if 900 + 4000 + 50 + 600 + 30 != 5580:
        raise VerificationError("internal logical budget arithmetic failed")
    if 2 * 720 != 1440 or 1440 + 720 != 2160:
        raise VerificationError("internal human budget arithmetic failed")
    if protocol.count("active_execution_profile = compact_single_gpu") != 1:
        raise VerificationError("active profile is absent or duplicated")
    if protocol.count("model = Qwen only for behavior confirmation") != 1:
        raise VerificationError("behavior model profile is absent or duplicated")
    return {"logical_generation": 5580, "human_items": 720, "required_literals": len(required_literals)}


def run_golden_verifiers() -> int:
    commands = (
        ([sys.executable, "writing/stage3 design/v3_5_rc2_statistics/verify_golden.py"],
         "STATISTICAL_GOLDEN_PASS"),
        ([sys.executable, "scripts/stage3_rc2/freeze_contract.py", "--self-test"],
         '"status": "PASS"'),
        ([sys.executable, "scripts/stage3_design/v3_5_rc2/human_quota.py", "--verify-golden",
          "writing/stage3 design/v3_5_rc2_closure/C/human_quota_golden.json"], "PASS"),
        ([sys.executable, "scripts/stage3_design/v3_5_rc2/two_phase_correction.py", "--verify-golden",
          "writing/stage3 design/v3_5_rc2_closure/C/two_phase_correction_golden.json"], "PASS"),
    )
    for command, expected in commands:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        if completed.returncode != 0 or expected not in completed.stdout:
            raise VerificationError(
                f"golden verifier failed: {command!r}; stdout={completed.stdout!r}; "
                f"stderr={completed.stderr!r}"
            )
    return len(commands)


def verify_all() -> dict[str, Any]:
    protocol = PROTOCOL.read_text(encoding="utf-8")
    return {
        "status": "PASS",
        "verdict": "DESIGN-FREEZE-PASS",
        "release_artifacts": verify_release_manifest(),
        "preexisting_files_unchanged": verify_preexisting_files(),
        "nested_hash_bindings": verify_nested_bindings(),
        "scope_residue_patterns_checked": verify_scope(protocol),
        "section_references_resolved": verify_cross_references(protocol),
        "budget_and_symbols": verify_budget_and_symbols(protocol),
        "golden_verifier_groups": run_golden_verifiers(),
        "formal_experiments_executed": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()
    try:
        if args.write_manifest:
            manifest = build_release_manifest()
            RELEASE_MANIFEST.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        report = verify_all()
        rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.write_report:
            target = args.write_report if args.write_report.is_absolute() else ROOT / args.write_report
            target.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 0
    except (OSError, KeyError, TypeError, ValueError, VerificationError) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
