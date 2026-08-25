from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from stage3_pipeline import p2_v2_k1_results as v2
from stage3_pipeline.core import canonical_sha256
from stage3_pipeline.statistics import retained_bootstrap


def _raw_coordinates() -> dict[str, object]:
    frame = [(f"p{prompt:02d}", f"v{vector:02d}") for prompt in range(50) for vector in range(20)]
    mt = frame[:976]
    mh = frame[:946] + frame[976:996]
    return {
        "members": [
            {"matched_set": "M_T", "matched_pair_count": len(mt), "records": [{"prompt_id": p, "vector_id": v} for p, v in mt]},
            {"matched_set": "M_H", "matched_pair_count": len(mh), "records": [{"prompt_id": p, "vector_id": v} for p, v in mh]},
        ],
    }


class _Registry:
    def __init__(self, identities: dict[str, dict[str, object]]) -> None:
        self.identities = identities

    def require(self, logical_id: str) -> dict[str, object]:
        return self.identities[logical_id]


def _validated_fixture(coordinates: list[tuple[str, str]] | None = None, *, failed: tuple[str, str, str] | None = None, bad_lineage: bool = False):
    coordinates = coordinates or [("p00", "v00"), ("p01", "v01")]
    rows: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    generations: list[dict[str, object]] = []
    judges: list[dict[str, object]] = []
    identities: dict[str, dict[str, object]] = {}
    for cell in v2.CELL_ORDER:
        anchor = "T" if cell.startswith("P2_T") else "H"
        arm = "all-token" if cell.endswith("_all") else "content-token"
        for index, (prompt_id, vector_id) in enumerate(coordinates):
            logical_id = f"{cell}:{prompt_id}:{vector_id}"
            identity = {"block": cell, "anchor": anchor, "estimator": "mu_all_tw", "prompt_id": prompt_id, "vector_id": vector_id}
            identities[logical_id] = identity
            rows.append({"logical_id": logical_id, "identity": identity})
            generation_sha = f"g-{logical_id}"
            judge_sha = f"j-{logical_id}"
            generation = {"logical_id": logical_id, "record_sha256": generation_sha}
            judge = {"logical_id": logical_id, "record_sha256": judge_sha}
            terminal = "TERMINAL_JUDGE_FAILURE" if failed == (cell, prompt_id, vector_id) else "COMPLETED_PARSED"
            response = {
                "logical_id": logical_id, "record_sha256": f"r-{logical_id}", "identity_sha256": f"i-{logical_id}",
                "generation_record_sha256": generation_sha,
                "judge_record_sha256": judge_sha if terminal == "COMPLETED_PARSED" else None,
                "cell": cell, "anchor": anchor, "estimator": "mu_all_tw", "arm": arm,
                "prompt_id": prompt_id, "vector_id": vector_id, "pair_id": f"{anchor}|{prompt_id}|{vector_id}",
                "terminal_status": terminal, "retained": terminal == "COMPLETED_PARSED",
                "label": ("unsafe" if index % 2 == 0 else "safe") if terminal == "COMPLETED_PARSED" else None,
            }
            if bad_lineage and logical_id == f"{v2.CELL_ORDER[0]}:{coordinates[0][0]}:{coordinates[0][1]}":
                response["generation_record_sha256"] = "wrong"
            responses.append(response)
            generations.append(generation)
            judges.append(judge)
    prepared = SimpleNamespace(rows=tuple(rows), registry=_Registry(identities))
    loaded = SimpleNamespace(responses=tuple(responses), generations=tuple(generations), judges=tuple(judges))
    return SimpleNamespace(prepared=prepared, loaded=loaded)


class P2V2K1Tests(unittest.TestCase):
    def test_common_intersection_is_identity_paired_and_counts_are_fixed(self) -> None:
        raw = _raw_coordinates()
        prompts = [f"p{index:02d}" for index in range(50)]
        vectors = [f"v{index:02d}" for index in range(20)]
        result = v2.derive_common_coordinates(raw, prompt_ids=prompts, vector_ids=vectors)
        self.assertEqual((result["M_T_count"], result["M_H_count"], result["intersection_count"]), (976, 966, 946))
        self.assertEqual(result["intersection_coordinates"][0], ("p00", "v00"))

    def test_reuse_accounting_and_v2_order(self) -> None:
        coordinates = [(f"p{index // 20:02d}", f"v{index % 20:02d}") for index in range(946)]
        fixture = _validated_fixture(coordinates)
        profile = v2.build_k1_profile(fixture, coordinates, prompt_ids=[f"p{index:02d}" for index in range(50)], vector_ids=[f"v{index:02d}" for index in range(20)])
        self.assertEqual(profile["cell_order"], list(v2.CELL_ORDER))
        self.assertEqual(len(profile["k1_reuse_records"]), 3_784)
        self.assertTrue(all(item["generation_calls_added"] == 0 and item["judge_calls_added"] == 0 for item in profile["k1_reuse_records"]))

    def test_terminal_failure_is_rejected_and_never_relabelled(self) -> None:
        fixture = _validated_fixture(failed=("P2_T_content", "p01", "v01"))
        with self.assertRaisesRegex(v2.P2V2K1ResultInputInvalid, "TERMINAL_OR_UNPARSED_SOURCE"):
            v2.build_k1_profile(fixture, [("p00", "v00"), ("p01", "v01")], prompt_ids=[f"p{index:02d}" for index in range(50)], vector_ids=[f"v{index:02d}" for index in range(20)])

    def test_lineage_mismatch_fails_closed(self) -> None:
        fixture = _validated_fixture(bad_lineage=True)
        with self.assertRaisesRegex(v2.P2V2K1ResultInputInvalid, "LINEAGE_MISMATCH"):
            v2.build_k1_profile(fixture, [("p00", "v00"), ("p01", "v01")], prompt_ids=[f"p{index:02d}" for index in range(50)], vector_ids=[f"v{index:02d}" for index in range(20)])

    def test_explicit_v2_order_is_forwarded_and_invalid_orders_fail_closed(self) -> None:
        payload = {"schema_version": retained_bootstrap.SCHEMA_VERSION, "synthetic_data": True, "block_type": "k1", "prompt_frame": [{"position": 0, "prompt_id": "p"}, {"position": 1, "prompt_id": "q"}], "vector_frame": [{"position": 0, "vector_id": "v"}, {"position": 1, "vector_id": "w"}], "cells": []}
        with self.assertRaisesRegex(retained_bootstrap.RetainedBootstrapError, "cell order"):
            retained_bootstrap.analyze_k1(payload, fixture_mode=True, cell_order=["P2_H_all", "P2_T_content", "P2_T_all", "P2_H_content"])
        with self.assertRaisesRegex(retained_bootstrap.RetainedBootstrapError, "cell order"):
            retained_bootstrap.analyze_k1(payload, fixture_mode=True, cell_order=["P2_T_all", "P2_T_all", "P2_H_all", "P2_H_content"])

    def test_validate_only_summary_and_existing_output_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            with self.assertRaisesRegex(v2.P2V2K1ResultInputInvalid, "OUTPUT_DIRECTORY_EXISTS"):
                v2.validate_p2_v2_k1_inputs(Path("/unused"), Path("/unused/raw.json"), Path("/unused/formal.json"), output)

    def test_assembly_does_not_duplicate_algorithm_and_uses_injected_statistic(self) -> None:
        fixture = _validated_fixture()
        profile = v2.build_k1_profile(fixture, [("p00", "v00"), ("p01", "v01")], prompt_ids=[f"p{index:02d}" for index in range(50)], vector_ids=[f"v{index:02d}" for index in range(20)])
        profile["matched_counts"] = {"M_T_count": 2, "M_H_count": 2, "intersection_count": 2}
        validated = SimpleNamespace(p2_run_directory=Path("/run"), p2_raw_result_path=Path("/raw"), p2_formal_result_path=Path("/formal"), p2_raw_result_sha256="a" * 64, p2_formal_result_sha256="b" * 64, raw_result={"schema_version": "raw", "status": "RAW_MEMBERS_READY", "terminal_partition": {}}, formal_result={"schema_version": "formal", "status": "ESTIMABLE", "formal_status": "FORMAL AMENDED T/H P2 RESULT"}, profile=profile)
        calls: list[object] = []
        def fake_statistic(payload: object, *, fixture_mode: bool, cell_order: list[str]) -> dict[str, object]:
            calls.append((payload, fixture_mode, cell_order))
            return {"status": "ESTIMABLE"}
        with mock.patch.object(v2, "file_sha256", return_value="a" * 64):
            result = v2.assemble_p2_v2_k1_result(validated, statistics_function=fake_statistic)
        self.assertEqual(calls[0][1:], (False, list(v2.CELL_ORDER)))
        self.assertEqual(result["k1_reuse_record_count"], 8)
        self.assertEqual(result["generation_calls_added"], 0)


if __name__ == "__main__":
    unittest.main()
