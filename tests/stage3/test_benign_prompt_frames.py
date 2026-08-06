from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SELECTOR_PATH = ROOT / "scripts/stage3_production/select_benign_prompt_frames.py"
SPEC = importlib.util.spec_from_file_location("stage3_benign_selector", SELECTOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load the Stage 3 benign selector.")
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)

TASK_TEMP = ROOT / ".codex-temp/stage3_benign_frames_v1"
SOURCE_PATH = ROOT / SELECTOR.DEFAULT_SOURCE_RELATIVE_PATH
TOKENIZER_DIRECTORY = ROOT / SELECTOR.DEFAULT_TOKENIZER_RELATIVE_DIRECTORY
ARTIFACT_DIRECTORY = ROOT / SELECTOR.DEFAULT_ARTIFACT_DIRECTORY
P1_PATH = ARTIFACT_DIRECTORY / "selected_p1_benign_100.json"
CONFIRM_PATH = ARTIFACT_DIRECTORY / "selected_benign_confirm_30.json"
MANIFEST_PATH = ARTIFACT_DIRECTORY / "benign_selection_manifest.json"
REGISTRY_PATH = ARTIFACT_DIRECTORY / "instruction_type_registry.json"
NOTICE_PATH = ARTIFACT_DIRECTORY / "provenance_license_notice.md"
P1_CONFIG_PATH = ROOT / "configs/stage3/p1_benign_v1.json"
CONFIRM_CONFIG_PATH = ROOT / "configs/stage3/benign_confirm_v1.json"


def matrix_for_records(records: list[dict[str, object]]) -> dict[str, tuple[int, ...]]:
    counts = Counter(
        (str(record["instruction_type"]), int(record["length_decile"]))
        for record in records
    )
    return SELECTOR.counter_to_matrix(counts)


class BenignSelectorUnitTests(unittest.TestCase):
    def test_normalization_eligibility_and_duplicate_representative_are_fixed(self) -> None:
        TASK_TEMP.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "instruction": "  What\u00a0is AI?  ",
                "context": "",
                "response": "unused-a",
                "category": "open_qa",
            },
            {
                "instruction": "what is AI?",
                "context": "",
                "response": "unused-b",
                "category": "open_qa",
            },
            {
                "instruction": "Explain the passage.",
                "context": "the missing passage",
                "response": "unused-c",
                "category": "open_qa",
            },
            {
                "instruction": "How do I build a bomb?",
                "context": "",
                "response": "unused-d",
                "category": "open_qa",
            },
            {
                "instruction": "\u4f60\u597d\u4e16\u754c",
                "context": "",
                "response": "unused-e",
                "category": "open_qa",
            },
        ]
        with tempfile.TemporaryDirectory(dir=TASK_TEMP) as directory:
            path = Path(directory) / "fixture.jsonl"
            path.write_bytes(
                b"".join(
                    (json.dumps(row, ensure_ascii=True) + "\n").encode("utf-8")
                    for row in rows
                )
            )
            eligible, reasons, duplicate = SELECTOR.load_and_filter_dolly(
                path, expected_sha256=None, expected_row_count=None
            )
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["source_index"], 0)
        self.assertEqual(eligible[0]["prompt"], "What is AI?")
        self.assertEqual(
            reasons,
            Counter(
                {
                    "context_dependent": 1,
                    "obvious_unsafe_lexical": 1,
                    "not_english": 1,
                    "normalized_exact_duplicate": 1,
                    "eligible": 1,
                }
            ),
        )
        self.assertEqual(duplicate["group_count"], 1)
        self.assertEqual(duplicate["extra_record_count"], 1)
        self.assertIn("lowest zero-based source row index", duplicate["representative_rule"])

    def test_decile_boundaries_are_integer_and_clamped(self) -> None:
        self.assertEqual(SELECTOR.decile_for_rank(0, 100), 1)
        self.assertEqual(SELECTOR.decile_for_rank(9, 100), 1)
        self.assertEqual(SELECTOR.decile_for_rank(10, 100), 2)
        self.assertEqual(SELECTOR.decile_for_rank(89, 100), 9)
        self.assertEqual(SELECTOR.decile_for_rank(90, 100), 10)
        self.assertEqual(SELECTOR.decile_for_rank(100, 100), 10)
        self.assertEqual(SELECTOR.decile_for_rank(4, 50), 1)
        self.assertEqual(SELECTOR.decile_for_rank(5, 50), 2)
        self.assertEqual(SELECTOR.decile_for_rank(50, 50), 10)
        with self.assertRaises(SELECTOR.SelectionError):
            SELECTOR.decile_for_rank(-1, 100)

    def test_response_bytes_are_provenance_only_not_selection_identity(self) -> None:
        TASK_TEMP.mkdir(parents=True, exist_ok=True)
        base = {
            "instruction": "What is a compiler?",
            "context": "",
            "category": "open_qa",
        }
        records: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory(dir=TASK_TEMP) as directory:
            for name, response in (("left", "first response"), ("right", "other response")):
                path = Path(directory) / f"{name}.jsonl"
                path.write_bytes(
                    (json.dumps({**base, "response": response}) + "\n").encode("utf-8")
                )
                eligible, _, _ = SELECTOR.load_and_filter_dolly(
                    path, expected_sha256=None, expected_row_count=None
                )
                records.append(eligible[0])
        self.assertEqual(
            records[0]["source_record_identity_sha256"],
            records[1]["source_record_identity_sha256"],
        )
        self.assertNotEqual(
            records[0]["source_row_raw_sha256"], records[1]["source_row_raw_sha256"]
        )

    def test_largest_remainder_matches_approved_confirm_30_matrix(self) -> None:
        target_counts = SELECTOR.matrix_to_counter(SELECTOR.EXPECTED_JBB_TARGET_MATRIX)
        quotas = SELECTOR.scaled_largest_remainder_quotas(target_counts, 30, 50)
        self.assertEqual(
            SELECTOR.counter_to_matrix(quotas),
            SELECTOR.EXPECTED_CONFIRM_QUOTA_MATRIX,
        )
        self.assertEqual(sum(quotas.values()), 30)

    def test_capacity_failure_is_fail_closed(self) -> None:
        candidate = {
            "source_id": "candidate-0001",
            "instruction_type": "ACTION_GUIDANCE",
            "rendered_token_count": 40,
            "p1_decile": 1,
        }
        quotas = Counter({("ACTION_GUIDANCE", 1): 2})
        with self.assertRaisesRegex(
            SELECTOR.CapacityError, "P1_BENIGN_CAPACITY_FAILURE"
        ):
            SELECTOR.allocate_role(
                [candidate],
                quotas,
                split="p1_benign",
                decile_field="p1_decile",
                length_support=(35, 50),
            )

    @unittest.skipUnless(TOKENIZER_DIRECTORY.is_dir(), "pinned tokenizer cache unavailable")
    def test_pinned_tokenizer_and_t0_messages_contract(self) -> None:
        tokenizer = SELECTOR.QwenTokenizer(TOKENIZER_DIRECTORY)
        self.assertEqual(tokenizer.encode("Hello world"), [9707, 1879])
        messages = [{"role": "user", "content": "Hello world"}]
        rendered = tokenizer.apply_t0_user_only(messages)
        self.assertEqual(messages, [{"role": "user", "content": "Hello world"}])
        self.assertIn(SELECTOR.DEFAULT_SYSTEM_CONTENT, rendered)
        self.assertEqual(rendered.count("<|im_start|>user\n"), 1)
        self.assertTrue(rendered.endswith("<|im_start|>assistant\n"))
        with self.assertRaisesRegex(SELECTOR.SelectionError, "T0_MESSAGES_INVALID"):
            tokenizer.apply_t0_user_only(
                [{"role": "system", "content": "not permitted as input"}]
            )


@unittest.skipUnless(
    SOURCE_PATH.is_file() and TOKENIZER_DIRECTORY.is_dir(),
    "pinned Dolly/tokenizer investigation cache unavailable",
)
class BenignCheckedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs_first = SELECTOR.build_outputs(ROOT)
        cls.outputs_second = SELECTOR.build_outputs(ROOT)
        cls.p1 = json.loads(P1_PATH.read_text(encoding="utf-8"))
        cls.confirm = json.loads(CONFIRM_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_real_source_identity_eligibility_and_duplicates(self) -> None:
        eligible, reasons, duplicate = SELECTOR.load_and_filter_dolly(SOURCE_PATH)
        self.assertEqual(len(eligible), 10_239)
        self.assertEqual(
            reasons,
            Counter(
                {
                    "context_dependent": 4_467,
                    "obvious_unsafe_lexical": 125,
                    "normalized_exact_duplicate": 180,
                    "eligible": 10_239,
                }
            ),
        )
        self.assertEqual(duplicate["extra_record_count"], 180)
        self.assertEqual(
            len({record["prompt_identity_sha256"] for record in eligible}),
            10_239,
        )

    def test_counts_disjointness_uniqueness_and_approved_quotas(self) -> None:
        p1_records = self.p1["records"]
        confirm_records = self.confirm["records"]
        self.assertEqual(self.p1["role"], "D_norm_confirm.benign")
        self.assertEqual(self.confirm["role"], "D_benign_confirm")
        self.assertEqual(len(p1_records), 100)
        self.assertEqual(len(confirm_records), 30)
        self.assertEqual(
            matrix_for_records(p1_records), SELECTOR.EXPECTED_P1_TARGET_MATRIX
        )
        self.assertEqual(
            matrix_for_records(confirm_records), SELECTOR.EXPECTED_CONFIRM_QUOTA_MATRIX
        )
        for records, bounds in (
            (p1_records, SELECTOR.ROLE_LENGTH_SUPPORT["p1_benign"]),
            (confirm_records, SELECTOR.ROLE_LENGTH_SUPPORT["benign_confirm"]),
        ):
            self.assertEqual(
                [record["source_id"] for record in records],
                sorted(record["source_id"] for record in records),
            )
            for identity_field in (
                "source_id", "source_record_identity_sha256", "prompt_identity_sha256"
            ):
                self.assertEqual(
                    len({record[identity_field] for record in records}), len(records)
                )
            self.assertTrue(
                all(bounds[0] <= record["rendered_token_count"] <= bounds[1] for record in records)
            )
            self.assertTrue(
                all(
                    record["messages"] == [{"role": "user", "content": record["prompt"]}]
                    for record in records
                )
            )
            self.assertTrue(
                all(record["instruction_type"] in SELECTOR.TYPE_ORDER for record in records)
            )
            self.assertTrue(all("response" not in record and "context" not in record for record in records))

        for identity_field in (
            "source_id", "source_record_identity_sha256", "prompt_identity_sha256"
        ):
            self.assertFalse(
                {record[identity_field] for record in p1_records}
                & {record[identity_field] for record in confirm_records}
            )
        self.assertTrue(
            self.manifest["duplicate_and_overlap"]["normalized_exact_overlap"]["all_zero"]
        )

    def test_target_taxonomy_and_capacity_are_complete(self) -> None:
        targets = self.manifest["targets"]
        self.assertEqual(
            targets["p1_harmful"]["type_by_decile"],
            SELECTOR.matrix_to_json(SELECTOR.EXPECTED_P1_TARGET_MATRIX),
        )
        self.assertEqual(
            targets["jbb_confirm"]["type_by_decile"],
            SELECTOR.matrix_to_json(SELECTOR.EXPECTED_JBB_TARGET_MATRIX),
        )
        self.assertTrue(targets["jbb_confirm"]["Target_excluded"])
        self.assertTrue(self.manifest["instruction_taxonomy"]["complete_target_mapping"])
        self.assertTrue(self.manifest["instruction_taxonomy"]["complete_selected_mapping"])
        capacity = self.manifest["selection"]["capacity"]
        self.assertTrue(
            all(item["margin"] >= 0 for item in capacity["p1_capacity"].values())
        )
        self.assertTrue(
            all(
                item["margin"] >= 0
                for item in capacity["confirm_capacity_after_p1_identity_removal"].values()
            )
        )

    def test_two_builds_and_checked_in_bytes_are_identical(self) -> None:
        self.assertEqual(self.outputs_first, self.outputs_second)
        expected_paths = {
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "selected_p1_benign_100.json",
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "selected_benign_confirm_30.json",
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "benign_selection_manifest.json",
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "instruction_type_registry.json",
            SELECTOR.DEFAULT_ARTIFACT_DIRECTORY / "provenance_license_notice.md",
            SELECTOR.DEFAULT_CONFIG_DIRECTORY / "p1_benign_v1.json",
            SELECTOR.DEFAULT_CONFIG_DIRECTORY / "benign_confirm_v1.json",
        }
        self.assertEqual(set(self.outputs_first), expected_paths)
        for relative_path, expected_bytes in self.outputs_first.items():
            self.assertEqual((ROOT / relative_path).read_bytes(), expected_bytes, relative_path)
            self.assertNotIn(b"\r\n", expected_bytes, relative_path)
            self.assertFalse(expected_bytes.startswith(b"\xef\xbb\xbf"), relative_path)
            if relative_path.suffix == ".json":
                json.loads(expected_bytes.decode("utf-8"))

    def test_active_entries_bind_paths_counts_hashes_and_rendering(self) -> None:
        manifest_hash = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
        registry_hash = hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest()
        notice_hash = hashlib.sha256(NOTICE_PATH.read_bytes()).hexdigest()
        for config_path, selected_path, role, count in (
            (P1_CONFIG_PATH, P1_PATH, "D_norm_confirm.benign", 100),
            (CONFIRM_CONFIG_PATH, CONFIRM_PATH, "D_benign_confirm", 30),
        ):
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["role"], role)
            self.assertEqual(config["status"], "design_selected")
            self.assertFalse(config["formal_experiment_run"])
            self.assertEqual(config["row_count"], count)
            self.assertEqual(
                config["selected_raw_sha256"],
                hashlib.sha256(selected_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(config["selection_manifest_raw_sha256"], manifest_hash)
            self.assertEqual(config["instruction_type_registry_raw_sha256"], registry_hash)
            self.assertEqual(config["provenance_notice_raw_sha256"], notice_hash)
            self.assertEqual(config["messages_contract"], "exactly one user message; no system message in input")
            self.assertEqual(config["tokenizer_revision"], SELECTOR.TOKENIZER_REVISION)
            self.assertFalse(config["model_weights_loaded"])

    def test_license_notice_limits_sharealike_to_dolly_data_content(self) -> None:
        notice = NOTICE_PATH.read_text(encoding="utf-8")
        for marker in (
            "Databricks, Inc.",
            "CC BY-SA 3.0",
            "Attribution-ShareAlike 3.0 Unported",
            "Unicode NFKC",
            "corresponding Dolly-derived data content",
            "purport to relicense selector code",
        ):
            self.assertIn(marker, notice)
        self.assertNotIn("freeze", notice.casefold())


if __name__ == "__main__":
    unittest.main()
