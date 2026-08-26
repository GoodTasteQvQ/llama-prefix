from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stage3_pipeline import fixed720_runner as runner
from stage3_pipeline.statistics import human_quota


class Fixed720RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records, cls.source = runner.build_eligible_records()
        cls.trace = human_quota.allocate_human_sample(
            cls.records,
            active_cell_order=runner.ACTIVE_CELL_ORDER,
            member_mapping=runner.ACTIVE_MEMBER_MAPPING,
        )

    def test_old_allocator_golden_and_active_mapping(self) -> None:
        golden = Path(__file__).parent / "fixtures/fixed720/human_quota_golden.json"
        human_quota.verify_golden(golden)
        self.assertEqual(runner.ACTIVE_CELL_ORDER, ("P2_T_all", "P2_T_content", "P2_H_all", "P2_H_content"))
        self.assertEqual(runner.ACTIVE_MEMBER_MAPPING["P2_T_all"], "P2-U(T)")
        self.assertEqual(runner.ACTIVE_MEMBER_MAPPING["P2_H_all"], "P2-B(H)")
        self.assertNotIn("P2_A_all", runner.ACTIVE_CELL_ORDER)

    def test_fixed_accounting_and_deterministic_trace(self) -> None:
        self.assertEqual(len(self.records), 4621)
        self.assertEqual(self.trace["eligible_n"], 4621)
        self.assertEqual(self.trace["selected_n"], 720)
        self.assertEqual(self.trace["fixed720_status"], "complete")
        self.assertEqual(self.trace["selected_ids_sha256"], "1305a68c339602a5c5aacf4dd82bda57776babf4fcc9ea327811901d1b6966f2")
        self.assertEqual(self.trace["trace_sha256"], "e760e0abd6801a35666417f3bd7575715f69c2409c5792ed623f99ce841cf099")
        again = human_quota.allocate_human_sample(
            self.records,
            active_cell_order=runner.ACTIVE_CELL_ORDER,
            member_mapping=runner.ACTIVE_MEMBER_MAPPING,
        )
        self.assertEqual(self.trace, again)

    def test_p2_membership_and_non_p2_block_mapping(self) -> None:
        p2 = [row for row in self.records if row["block"] == "P2"]
        self.assertEqual(sum(row["matched"] for row in p2 if row["logical_cell"].startswith("P2_T")), 1952)
        self.assertEqual(sum(row["matched"] for row in p2 if row["logical_cell"].startswith("P2_H")), 1932)
        self.assertEqual(sum(not row["matched"] for row in p2), 58)
        self.assertEqual(len([row for row in self.records if row["block"] == "harmful_clean"]), 50)
        self.assertEqual(len([row for row in self.records if row["block"] == "benign_clean"]), 30)
        self.assertEqual(len([row for row in self.records if row["block"] == "benign_steered"]), 599)
        self.assertTrue(all(row["matched"] is False for row in self.records if row["block"] != "P2"))

    def test_terminal_missing_and_invalid_frame_fail_closed(self) -> None:
        failed = {
            "logical_id": "failed",
            "terminal_status": "TERMINAL_JUDGE_FAILURE",
            "label": None,
            "retained": False,
        }
        disposition = {"logical_id": "failed", "terminal_disposition": "TERMINAL_JUDGE_FAILURE"}
        self.assertEqual(
            runner._completed_records([failed], [disposition], block="benign_clean", labels=runner.benign_results.BENIGN_LABELS, cells={"benign_clean"}),
            [],
        )
        valid = {"response_id": "x", "block": "P2", "predicted_class": "safe", "matched": True, "logical_cell": "P2_A_all"}
        with self.assertRaises(human_quota.AllocationError):
            human_quota.allocate_human_sample([valid], active_cell_order=runner.ACTIVE_CELL_ORDER, member_mapping=runner.ACTIVE_MEMBER_MAPPING)
        duplicate = dict(self.records[0])
        with self.assertRaises(human_quota.AllocationError):
            human_quota.allocate_human_sample([self.records[0], duplicate], active_cell_order=runner.ACTIVE_CELL_ORDER, member_mapping=runner.ACTIVE_MEMBER_MAPPING)
        bad_label = dict(self.records[0], predicted_class="not-a-label")
        with self.assertRaises(human_quota.AllocationError):
            human_quota.allocate_human_sample([bad_label], active_cell_order=runner.ACTIVE_CELL_ORDER, member_mapping=runner.ACTIVE_MEMBER_MAPPING)

    def test_validate_only_does_not_write_selection(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".codex-temp") as directory:
            output = Path(directory) / "would-be-output"
            with mock.patch.object(runner, "build_eligible_records", return_value=(self.records, self.source)):
                summary = runner.validate_only(runner.DEFAULT_CONFIG)
            self.assertFalse(output.exists())
            self.assertFalse(summary["output_written"])
            self.assertFalse(summary["human_annotation_run"])
            self.assertFalse(summary["two_phase_run"])


if __name__ == "__main__":
    unittest.main()
