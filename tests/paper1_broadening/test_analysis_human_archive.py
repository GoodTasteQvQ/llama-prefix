from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper1_broadening.analysis import (
    _bootstrap,
    _coordinate_table,
    analyze_records,
    descriptive_comparisons,
    nearest_rank,
    paired_endpoints,
    write_analysis_artifacts,
)
from paper1_broadening.archive import archive_run
from paper1_broadening.common import BroadeningError, canonical_json, file_sha256
from paper1_broadening.human import (
    allocate_core_human,
    allocate_extension_human,
    analyze_human_labels,
    blinded_packets,
)


BOOTSTRAP = {"replicates": 30, "minimum_successes": 25, "lower": 0.10, "upper": 0.90}


def _complete_records(prompt_count: int = 25) -> list[dict[str, object]]:
    records = []
    for category in ("cat-a", "cat-b"):
        for direction in ("d0", "d1"):
            for index in range(prompt_count):
                common = {
                    "block": "core_harmful_steered",
                    "model_id": "qwen25",
                    "family": "rogue",
                    "layer": 9,
                    "condition": "decode_only",
                    "category": category,
                    "prompt_id": f"{category}:p{index}",
                    "direction_id": direction,
                }
                records.append({**common, "dose_label": "A", "label": "unsafe"})
                records.append({**common, "dose_label": "S", "label": "safe"})
    return records


def test_equal_weight_endpoints_bounds_and_bootstrap() -> None:
    records = _complete_records()
    result = paired_endpoints(
        records,
        block="core_harmful_steered",
        model_id="qwen25",
        family="rogue",
        layer=9,
        bootstrap=BOOTSTRAP,
    )
    assert result["status"] == "ESTIMABLE"
    assert result["point_estimate"] == {"Delta_unsafe": 1.0, "Delta_broken": 0.0}
    assert result["denominator"]["scheduled_pairs"] == 100
    assert result["denominator"]["paired_retained"] == 100
    assert result["bootstrap"]["replicates_successful"] == 30
    assert result["bootstrap"]["ci"] is not None
    assert nearest_rank([3, 1, 2], 0.5) == 2.0

    records[1]["label"] = None
    with_one_missing = paired_endpoints(
        records,
        block="core_harmful_steered",
        model_id="qwen25",
        family="rogue",
        layer=9,
        bootstrap=BOOTSTRAP,
    )
    assert with_one_missing["status"] == "ESTIMABLE"
    assert with_one_missing["missing_worst_case_bounds"] is not None
    assert with_one_missing["denominator"]["missing_fraction"] == pytest.approx(0.005)

    for index, row in enumerate(records):
        if row["label"] is not None:
            row["label"] = None
        if index >= 10:
            break
    too_many_missing = paired_endpoints(
        records,
        block="core_harmful_steered",
        model_id="qwen25",
        family="rogue",
        layer=9,
        bootstrap=BOOTSTRAP,
    )
    assert too_many_missing["status"] == "ACCOUNTING_ONLY"
    assert too_many_missing["bootstrap"]["ci"] is None
    assert too_many_missing["missing_worst_case_bounds"] is None


def test_bootstrap_incomplete_direction_fails_replicates_without_keyerror() -> None:
    records = _complete_records(prompt_count=3)
    records = [
        row for row in records
        if not (row["category"] == "cat-b" and row["direction_id"] == "d1" and row["prompt_id"].endswith("p2"))
    ]
    table, _ = _coordinate_table(records)
    result = _bootstrap(
        table,
        seed="MBD-NM-v2.1|fixture",
        replicates=100,
        minimum_successes=1,
        lower=0.1,
        upper=0.9,
    )
    assert result["replicates_failed"] > 0
    assert result["replicates_successful"] + result["replicates_failed"] == 100


def test_analysis_rejects_unknown_labels_and_keeps_descriptive_comparisons_separate() -> None:
    bad = _complete_records(prompt_count=1)
    bad[0]["label"] = "not-a-class"
    with pytest.raises(BroadeningError):
        paired_endpoints(bad, block="b", model_id="m", family="f", layer=1, bootstrap=BOOTSTRAP)

    records: list[dict[str, object]] = []
    for direction in ("d0", "d1"):
        for prompt_index in range(2):
            prompt_id = f"cat-a:p{prompt_index}"
            common = {
                "block": "core_harmful_steered", "model_id": "qwen25", "family": "rogue", "layer": 9,
                "category": "cat-a", "prompt_id": prompt_id, "direction_id": direction, "dose_label": "A",
            }
            records.append({**common, "condition": "public_v1", "label": "unsafe"})
            records.append({**common, "condition": "decode_only", "label": "broken"})
            records.append({
                "block": "core_harmful_clean", "model_id": "qwen25", "family": None, "layer": None,
                "category": "cat-a", "prompt_id": prompt_id, "direction_id": None,
                "condition": "clean", "dose_label": "clean", "label": "safe",
            })
    comparisons = descriptive_comparisons(records)
    phase = next(row for row in comparisons if row["comparison"] == "public_v1_vs_decode_only")
    clean = next(row for row in comparisons if row["comparison"] == "A_decode_only_vs_clean")
    assert phase["point_estimate"] == {"unsafe": 1.0, "broken": -1.0}
    assert clean["point_estimate"] == {"unsafe": 0.0}
    assert clean["clean_is_single_prompt_record"] is True


def _human_row(index: int, cell: str, label: str = "safe") -> dict[str, object]:
    return {
        "response_id": f"response-{index}",
        "cell": cell,
        "request": f"request {index}",
        "response": f"response {index}",
        "auto_label": label,
        "model_id": "qwen25",
        "family": "rogue",
        "layer": 9,
        "condition": "decode_only",
        "dose_label": "A",
    }


def test_human_allocators_blind_aliases_weights_and_support_status() -> None:
    cells = [
        f"{model}|{family}|{condition}|{dose}"
        for model in ("qwen25", "llama31")
        for family in ("rogue", "contrastive")
        for condition in ("public_v1", "decode_only")
        for dose in ("A", "S")
    ]
    rows = [_human_row(index, cells[index // 10], "unsafe" if index % 3 == 0 else "safe") for index in range(160)]
    allocation = allocate_core_human(rows)
    assert allocation["probability_sample_actual"] == 160
    assert len([row for row in allocation["records"] if not row["diagnostic_only"]]) == 160
    assert all(row["N"] == 10 and row["n"] == 10 and row["selection_probability"] == 1.0 for row in allocation["records"])
    packets = blinded_packets(allocation, "rubric")
    assert len(packets) == 160
    assert set(packets[0]) == {"blind_id", "request", "response", "rubric"}
    assert "model_id" not in packets[0]

    extension_rows = [_human_row(index, f"cell-{index % 4}") for index in range(48)]
    extension = allocate_extension_human(extension_rows, block="E1")
    assert extension["actual"] == 40
    assert sum(extension["cell_quotas"].values()) == 40
    assert all(row["selection_probability"] == pytest.approx(row["n"] / row["N"]) for row in extension["records"])

    aliases = [_human_row(1, "cell-a", "unsafe"), {**_human_row(1, "cell-b", "unsafe"), "response": "response 1"}]
    aliased = allocate_extension_human(aliases, block="E2")
    assert aliased["actual"] == 1
    assert len(aliased["records"][0]["alias_cells"]) == 2

    one = allocate_extension_human([_human_row(1, "cell-a", "unsafe")], block="E3")
    label = {"blind_id": one["records"][0]["blind_id"], "adjudicated_label": "safe"}
    human = analyze_human_labels(one, [label])
    assert human["metrics"]["unsafe"]["recall"] is None
    assert human["metrics"]["unsafe"]["status"] == "INSUFFICIENT_HUMAN_SUPPORT"


def _write_terminal_run(run_dir: Path) -> dict[str, object]:
    run_dir.mkdir(parents=True)
    header = {
        "run_id": "archive-fixture", "design_id": "MBD-NM", "design_revision": "v2.1-ccf-a-target",
        "implementation_revision": "linux-single-gpu-v1", "code_commit": "fixture", "dirty": True,
        "started_at": "2026-09-05T00:00:00Z", "model_revision": "UNKNOWN", "tokenizer_revision": "UNKNOWN",
        "judge_revision": "UNKNOWN", "template": {}, "decoder": {},
        "fixture": True,
    }
    (run_dir / "run_header.json").write_text(json.dumps(header), encoding="utf-8")
    (run_dir / "frames.json").write_text(json.dumps({"frame_digest": "fixture"}), encoding="utf-8")
    (run_dir / "resolved_config.json").write_text(json.dumps({"fixture": True}), encoding="utf-8")
    (run_dir / "analysis.json").write_text(json.dumps({"status": "ACCOUNTING_ONLY"}), encoding="utf-8")
    (run_dir / "generation_attempts.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "generation_ledger.jsonl").write_text(json.dumps({"response_id": "r", "terminal_status": "COMPLETED", "attempt_count": 1}) + "\n", encoding="utf-8")
    (run_dir / "judge_records.jsonl").write_text(json.dumps({"response_id": "r", "four_class_status": "PARSED"}) + "\n", encoding="utf-8")
    return header


def test_analysis_revisions_and_archive_are_immutable_and_non_self_hashed(tmp_path: Path) -> None:
    analysis = analyze_records(_complete_records(prompt_count=1), BOOTSTRAP)
    first = write_analysis_artifacts(analysis, tmp_path)
    first_hash = file_sha256(tmp_path / "analysis.json")
    second = write_analysis_artifacts(analysis, tmp_path)
    assert first["analysis_revision"] == "v1"
    assert second["analysis_revision"] == "v2"
    assert (tmp_path / "analysis.json").is_file()
    assert (tmp_path / "analysis.v2.json").is_file()
    assert file_sha256(tmp_path / "analysis.json") == first_hash

    header = _write_terminal_run(tmp_path / "run")
    run_dir = tmp_path / "run"
    manifest = archive_run(
        run_dir=run_dir,
        repo_root=Path(__file__).resolve().parents[2],
        run_header=header,
        source_ids={"fixture": True},
    )
    assert manifest["manifest_is_self_hashed"] is False
    assert all(not record["path"].startswith("provenance_manifest") for record in manifest["files"])
    first_manifest_hash = file_sha256(run_dir / "provenance_manifest.json")
    second_manifest = archive_run(
        run_dir=run_dir,
        repo_root=Path(__file__).resolve().parents[2],
        run_header=header,
        source_ids={"fixture": True, "revision": 2},
    )
    assert second_manifest["archive_revision"] == 2
    assert file_sha256(run_dir / "provenance_manifest.json") == first_manifest_hash
    assert (run_dir / "provenance_manifest.v2.json").is_file()

    (run_dir / "generation_ledger.jsonl").write_text(json.dumps({"response_id": "r", "terminal_status": "UNEXECUTED"}) + "\n", encoding="utf-8")
    with pytest.raises(BroadeningError):
        archive_run(
            run_dir=run_dir,
            repo_root=Path(__file__).resolve().parents[2],
            run_header=header,
            source_ids={"fixture": True},
        )
