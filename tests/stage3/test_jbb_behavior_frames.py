from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SELECTOR_PATH = ROOT / "scripts/stage3_production/select_jbb_behavior_frames.py"
SPEC = importlib.util.spec_from_file_location("stage3_jbb_selector", SELECTOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load the Stage 3 JBB selector.")
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)

ARTIFACT_DIRECTORY = ROOT / "data/stage3/jbb_behavior_frames_v1"
SCREEN_PATH = ARTIFACT_DIRECTORY / "selected_jbb_screen_30.json"
CONFIRM_PATH = ARTIFACT_DIRECTORY / "selected_jbb_confirm_50.json"
MANIFEST_PATH = ARTIFACT_DIRECTORY / "jbb_behavior_split_manifest.json"
NOTICE_PATH = ARTIFACT_DIRECTORY / "provenance_license_notice.md"
SCREEN_CONFIG_PATH = ROOT / "configs/stage3/jbb_behavior_screen_v1.json"
CONFIRM_CONFIG_PATH = ROOT / "configs/stage3/jbb_behavior_confirm_v1.json"


class JBBBehaviorFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = SELECTOR.load_and_validate_source(ROOT)
        cls.memberships, cls.ranks, cls.category_ids = SELECTOR.assign_memberships(cls.rows)

    def test_source_schema_identity_and_category_counts(self) -> None:
        self.assertEqual(len(self.rows), 100)
        self.assertEqual([row["Index"] for row in self.rows], list(range(100)))
        self.assertEqual(len({row["Goal"] for row in self.rows}), 100)
        self.assertEqual(len({SELECTOR.canonical_sha256(row) for row in self.rows}), 100)
        self.assertEqual(
            Counter(row["Category"] for row in self.rows),
            Counter({category: 10 for category in SELECTOR.EXPECTED_CATEGORIES}),
        )
        self.assertEqual(
            hashlib.sha256((ROOT / SELECTOR.SOURCE_RELATIVE_PATH).read_bytes()).hexdigest(),
            SELECTOR.LOCAL_SOURCE_SHA256,
        )

    def test_rank_uses_only_fixed_membership_inputs(self) -> None:
        row = dict(self.rows[0])
        expected = SELECTOR.canonical_sha256(
            {
                "category": row["Category"],
                "index": row["Index"],
                "master_seed": 42,
                "namespace": "paper1-stage3-jbb-split-v1",
            }
        )
        self.assertEqual(SELECTOR.selection_rank(row), expected)
        changed_goal = {**row, "Goal": "not a selection input"}
        changed_target = {**row, "Target": "not a selection input"}
        self.assertEqual(SELECTOR.selection_rank(changed_goal), expected)
        self.assertEqual(SELECTOR.selection_rank(changed_target), expected)
        self.assertEqual(len(set(self.ranks.values())), 100)

    def test_quota_disjointness_coverage_and_expected_ids(self) -> None:
        actual = {
            membership: sorted(
                index for index, assigned in self.memberships.items() if assigned == membership
            )
            for membership in ("confirm", "screen", "unused")
        }
        self.assertEqual(actual, SELECTOR.EXPECTED_MEMBERSHIP_IDS)
        self.assertEqual({key: len(value) for key, value in actual.items()}, {
            "confirm": 50,
            "screen": 30,
            "unused": 20,
        })
        self.assertFalse(set(actual["confirm"]) & set(actual["screen"]))
        self.assertFalse(set(actual["confirm"]) & set(actual["unused"]))
        self.assertFalse(set(actual["screen"]) & set(actual["unused"]))
        self.assertEqual(set().union(*map(set, actual.values())), set(range(100)))
        for category in SELECTOR.EXPECTED_CATEGORIES:
            self.assertEqual(
                {key: len(value) for key, value in self.category_ids[category].items()},
                {"confirm": 5, "screen": 3, "unused": 2},
            )

    def test_checked_in_artifacts_are_exact_selector_outputs(self) -> None:
        first = SELECTOR.build_outputs(ROOT)
        second = SELECTOR.build_outputs(ROOT)
        self.assertEqual(first, second)
        expected_paths = {
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "selected_jbb_screen_30.json",
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "selected_jbb_confirm_50.json",
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "jbb_behavior_split_manifest.json",
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "provenance_license_notice.md",
            SELECTOR.DEFAULT_CONFIG_DIRECTORY / "jbb_behavior_screen_v1.json",
            SELECTOR.DEFAULT_CONFIG_DIRECTORY / "jbb_behavior_confirm_v1.json",
        }
        self.assertEqual(set(first), expected_paths)
        for relative_path, expected_bytes in first.items():
            self.assertEqual((ROOT / relative_path).read_bytes(), expected_bytes, relative_path)
            self.assertNotIn(b"\r\n", expected_bytes, relative_path)
            self.assertFalse(expected_bytes.startswith(b"\xef\xbb\xbf"), relative_path)

    def test_selected_runtime_frames_exclude_source_response_prefix(self) -> None:
        for path, role, count, quota in (
            (SCREEN_PATH, "D_behavior_screen", 30, 3),
            (CONFIRM_PATH, "D_behavior_confirm", 50, 5),
        ):
            raw = path.read_bytes()
            selected = json.loads(raw.decode("utf-8"))
            self.assertNotIn(b'"Target"', raw)
            self.assertEqual(selected["role"], role)
            self.assertEqual(selected["status"], "design_selected")
            self.assertFalse(selected["formal_experiment_run"])
            self.assertEqual(selected["record_count"], count)
            records = selected["records"]
            indices = [record["source_index"] for record in records]
            self.assertEqual(indices, sorted(indices))
            self.assertEqual(Counter(record["category"] for record in records), Counter({
                category: quota for category in SELECTOR.EXPECTED_CATEGORIES
            }))
            self.assertTrue(all(record["prompt"] for record in records))
            self.assertTrue(all(record["split_membership"] == role.removeprefix("D_behavior_") for record in records))

    def test_manifest_duplicate_overlap_and_provenance_contract(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["final_membership_ids_in_source_index_order"],
            SELECTOR.EXPECTED_MEMBERSHIP_IDS,
        )
        self.assertEqual(manifest["counts"], {
            "confirm": 50,
            "screen": 30,
            "unused": 20,
            "union": 100,
        })
        self.assertTrue(manifest["pairwise_disjoint"])
        self.assertTrue(manifest["complete_source_coverage"])
        duplicate = manifest["duplicate_leakage"]
        self.assertEqual(duplicate["jbb_internal_normalized_exact_duplicate_count"], 0)
        self.assertEqual(duplicate["p1_harmful_to_jbb_normalized_exact_overlap_count"], 0)
        self.assertEqual(duplicate["p1_to_jbb_lexical_candidates"], [])
        self.assertEqual(
            [item["source_indices"] for item in duplicate["jbb_internal_lexical_candidates"]],
            [[10, 13], [25, 29], [51, 53]],
        )
        provenance = manifest["source_provenance"]
        self.assertEqual(provenance["dataset_revision"], SELECTOR.OFFICIAL_DATASET_REVISION)
        self.assertEqual(provenance["source_csv_raw_sha256"], SELECTOR.OFFICIAL_CSV_SHA256)
        self.assertEqual(provenance["local_json_raw_sha256"], SELECTOR.LOCAL_SOURCE_SHA256)
        self.assertEqual(provenance["license"], "MIT")
        self.assertIn("zero field mismatches", provenance["local_to_official_relation"])

    def test_active_entries_bind_selected_bytes(self) -> None:
        for config_path, selected_path, role, count, quota in (
            (SCREEN_CONFIG_PATH, SCREEN_PATH, "D_behavior_screen", 30, 3),
            (CONFIRM_CONFIG_PATH, CONFIRM_PATH, "D_behavior_confirm", 50, 5),
        ):
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["role"], role)
            self.assertEqual(config["status"], "design_selected")
            self.assertFalse(config["formal_experiment_run"])
            self.assertEqual(config["row_count"], count)
            self.assertEqual(config["category_quota"], quota)
            self.assertEqual(config["source_revision"], SELECTOR.OFFICIAL_DATASET_REVISION)
            self.assertEqual(
                config["selected_raw_sha256"],
                hashlib.sha256(selected_path.read_bytes()).hexdigest(),
            )

    def test_notice_carries_mit_redistribution_condition_and_status_boundary(self) -> None:
        notice = NOTICE_PATH.read_text(encoding="utf-8")
        for marker in (
            "MIT License",
            "Copyright (c) 2023 JailbreakBench Team",
            "included in all copies or substantial portions",
            "formal_experiment_run=false",
            "not a freeze",
            "RUN-READY",
            "PAPER-RUN-READY",
        ):
            self.assertIn(marker, notice)


if __name__ == "__main__":
    unittest.main()
