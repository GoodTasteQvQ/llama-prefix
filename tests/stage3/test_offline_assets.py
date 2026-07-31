from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from stage3_pipeline.core import canonical_sha256
from stage3_pipeline.offline_assets import (
    AssetError,
    JsonInputSpec,
    OfflineJsonLoader,
    load_p1_harmful_active_entry,
)
from tests.stage3.helpers import ACTIVE_ENTRY, P1_DIRECTORY, ROOT


class OfflineAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.update({
            "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "TEMP": str(ROOT / ".codex-temp"), "TMP": str(ROOT / ".codex-temp"),
        })

    def test_generic_loader_validates_raw_schema_identity_frame_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            root = Path(temporary)
            rows = [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]
            raw = (json.dumps(rows, separators=(",", ":")) + "\n").encode("utf-8")
            (root / "asset.json").write_bytes(raw)
            identities = [canonical_sha256([["id", row["id"]]]) for row in rows]
            spec = JsonInputSpec(
                "asset.json", "array", row_count=2,
                ordered_fields=("id", "text"), identity_fields=("id",),
                field_types=(("id", "string"), ("text", "string")),
                expected_sha256=hashlib.sha256(raw).hexdigest(),
                expected_byte_length=len(raw), expected_frame_sha256=canonical_sha256(identities),
                source_repository="test/repository", source_revision="test-revision-1",
                source_path_or_config_split="fixtures/asset.json", license="CC0-1.0",
                provenance="synthetic unit-test fixture",
            )
            loader = OfflineJsonLoader(root, [spec])
            self.assertEqual(loader.load("asset.json"), rows)
            inventory = loader.inventory()[0]
            self.assertEqual(inventory["duplicate_identity_count"], 0)
            self.assertEqual(inventory["canonical_ordered_frame_sha256"], canonical_sha256(identities))

    def test_generic_loader_negative_matrix_and_no_fallback(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            root = Path(temporary)
            documents = {
                "wrong-top.json": {"id": "a", "text": "x"},
                "wrong-order.json": [{"text": "x", "id": "a"}],
                "wrong-type.json": [{"id": 1, "text": "x"}],
                "duplicate.json": [{"id": "a", "text": "x"}, {"id": "a", "text": "y"}],
                "valid.json": [{"id": "a", "text": "x"}],
            }
            for name, value in documents.items():
                (root / name).write_text(json.dumps(value) + "\n", encoding="utf-8", newline="\n")
            def complete_spec(name: str, *, top_level_type: str = "array") -> JsonInputSpec:
                raw = (root / name).read_bytes()
                payload = json.loads(raw.decode("utf-8"))
                rows = payload if isinstance(payload, list) else [payload]
                identities = [canonical_sha256([["id", row["id"]]]) for row in rows]
                return JsonInputSpec(
                    name, top_level_type, row_count=len(rows),
                    ordered_fields=("id", "text"), identity_fields=("id",),
                    field_types=(("id", "string"), ("text", "string")),
                    expected_sha256=hashlib.sha256(raw).hexdigest(),
                    expected_byte_length=len(raw),
                    expected_frame_sha256=canonical_sha256(identities),
                    source_repository="test/repository", source_revision="test-revision-1",
                    source_path_or_config_split=f"fixtures/{name}", license="CC0-1.0",
                    provenance="synthetic negative-test fixture",
                )
            valid_spec = complete_spec("valid.json")
            specs = [
                replace(valid_spec, relative_path="missing.json"),
                replace(valid_spec, expected_sha256="0" * 64),
                replace(valid_spec, expected_byte_length=1),
                complete_spec("wrong-top.json"),
                complete_spec("wrong-order.json"),
                complete_spec("wrong-type.json"),
                complete_spec("duplicate.json"),
                replace(valid_spec, expected_frame_sha256="f" * 64),
            ]
            for index, spec in enumerate(specs):
                with self.subTest(case=index):
                    with self.assertRaises(AssetError):
                        OfflineJsonLoader(root, [spec]).load(spec.relative_path)
            with self.assertRaises(AssetError):
                replace(valid_spec, provenance=None).validate()
            with self.assertRaises(AssetError):
                JsonInputSpec("valid.json", "array").validate()
            with self.assertRaises(AssetError):
                JsonInputSpec("https://example.invalid/data.json", "array").validate()
            loader = OfflineJsonLoader(root, [valid_spec])
            with self.assertRaises(AssetError):
                loader.load("alternate.json")
            self.assertNotIn("HF_HOME", loader.specs)

    def _p1_fixture_root(self, destination: Path) -> dict[str, object]:
        entry = json.loads(ACTIVE_ENTRY.read_text(encoding="utf-8"))
        config_path = destination / "configs/stage3/p1_harmful_do_not_answer_v1.json"
        config_path.parent.mkdir(parents=True)
        package = destination / "data/stage3/p1_harmful_do_not_answer_v1"
        package.mkdir(parents=True)
        for name in (
            "selected_p1_harmful_100.json", "p1_harmful_selection_manifest.json",
            "category_registry.json", "data_license_notice.md",
        ):
            shutil.copyfile(P1_DIRECTORY / name, package / name)
        config_path.write_text(
            json.dumps(entry, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        return entry

    @staticmethod
    def _write_entry(root: Path, entry: dict[str, object]) -> None:
        path = root / "configs/stage3/p1_harmful_do_not_answer_v1.json"
        path.write_text(
            json.dumps(entry, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def test_p1_active_entry_positive_three_way_integration(self) -> None:
        loaded = load_p1_harmful_active_entry(
            ROOT, "configs/stage3/p1_harmful_do_not_answer_v1.json"
        )
        self.assertEqual(loaded["row_count"], 100)
        self.assertEqual(
            loaded["canonical_ordered_frame_sha256"],
            "afcb3bcfe3042bf37189fc9718b53389ce0145e43b75efc3364e250e86552410",
        )
        self.assertEqual(loaded["ordered_source_ids"][0], loaded["records"][0]["source_id"])
        self.assertEqual(
            loaded["license_notice_raw_sha256"],
            "cf90c23995486ac9bdb26b6145bec0fee906201bb85ddf4fe06c988a52f98c23",
        )

    def test_p1_active_entry_negative_field_matrix(self) -> None:
        mutations = {
            "missing_role": lambda value: value.pop("role"),
            "wrong_role": lambda value: value.__setitem__("role", "D_behavior_screen.harmful"),
            "wrong_status": lambda value: value.__setitem__("status", "candidate_only"),
            "path_escape": lambda value: value.__setitem__("relative_path", "../selected.json"),
            "wrong_row_count": lambda value: value.__setitem__("row_count", 99),
            "wrong_byte_length": lambda value: value.__setitem__("raw_byte_length", 70704),
            "wrong_top_fields": lambda value: value["selected_top_level_ordered_fields"].reverse(),
            "wrong_record_fields": lambda value: value["selected_record_ordered_fields"].reverse(),
            "wrong_identity_field": lambda value: value.__setitem__("selected_identity_field", "source_id"),
            "wrong_source_id_field": lambda value: value.__setitem__("selected_source_id_field", "frame_position"),
            "wrong_upstream_id_field": lambda value: value.__setitem__("upstream_source_id_field", "source_id"),
            "wrong_selected_hash": lambda value: value.__setitem__("selected_raw_sha256", "0" * 64),
            "wrong_frame_hash": lambda value: value.__setitem__("canonical_ordered_frame_sha256", "0" * 64),
            "wrong_upstream_hash": lambda value: value.__setitem__("upstream_raw_sha256", "0" * 64),
            "wrong_source_rows": lambda value: value.__setitem__("source_row_count", 938),
            "wrong_eligible": lambda value: value.__setitem__("eligible_count", 238),
            "wrong_filter": lambda value: value["selection_filter"].__setitem__("value", "Physical Harm"),
            "wrong_operator": lambda value: value["selection_filter"].__setitem__("operator", "contains"),
            "wrong_quota": lambda value: value["category_quotas"].__setitem__("Assisting illegal activities", 54),
            "wrong_revision": lambda value: value.__setitem__("source_revision", "0" * 40),
            "wrong_repository": lambda value: value.__setitem__("source_repository", "other/repository"),
            "wrong_source_path": lambda value: value.__setitem__("source_path", "other.csv"),
            "wrong_prompt_field": lambda value: value.__setitem__("source_prompt_field", "prompt"),
            "wrong_license": lambda value: value.__setitem__("license", "Apache-2.0"),
            "wrong_provenance_path": lambda value: value.__setitem__(
                "license_notice_relative_path",
                "data/stage3/p1_harmful_do_not_answer_v1/category_registry.json",
            ),
            "selection_manifest_notice_alias": lambda value: value.__setitem__(
                "license_notice_relative_path",
                "data/stage3/p1_harmful_do_not_answer_v1/p1_harmful_selection_manifest.json",
            ),
            "wrong_notice_hash": lambda value: value.__setitem__(
                "license_notice_raw_sha256", "0" * 64
            ),
        }
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            root = Path(temporary)
            baseline = self._p1_fixture_root(root)
            for name, mutate in mutations.items():
                entry = copy.deepcopy(baseline)
                mutate(entry)
                self._write_entry(root, entry)
                with self.subTest(case=name):
                    with self.assertRaises(AssetError):
                        load_p1_harmful_active_entry(
                            root, "configs/stage3/p1_harmful_do_not_answer_v1.json"
                        )

    def test_p1_license_notice_token_preserving_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            root = Path(temporary)
            self._p1_fixture_root(root)
            notice = root / "data/stage3/p1_harmful_do_not_answer_v1/data_license_notice.md"
            notice.write_bytes(notice.read_bytes() + b"\ncanonical tokens retained\n")
            with self.assertRaises(AssetError):
                load_p1_harmful_active_entry(
                    root, "configs/stage3/p1_harmful_do_not_answer_v1.json"
                )

    def test_p1_historical_final_count_and_self_hash_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            root = Path(temporary)
            self._p1_fixture_root(root)
            path = root / "data/stage3/p1_harmful_do_not_answer_v1/p1_harmful_selection_manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["pool_and_selection"]["final_count"] = 99
            manifest["self_sha256"] = canonical_sha256({
                key: value for key, value in manifest.items() if key != "self_sha256"
            })
            path.write_text(
                json.dumps(manifest, ensure_ascii=True, separators=(",", ":")) + "\n",
                encoding="utf-8", newline="\n",
            )
            with self.assertRaises(AssetError):
                load_p1_harmful_active_entry(
                    root, "configs/stage3/p1_harmful_do_not_answer_v1.json"
                )

    def test_second_coherent_active_entry_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            root = Path(temporary)
            entry = self._p1_fixture_root(root)
            alternate = root / "configs/stage3/counterfeit.json"
            alternate.write_text(
                json.dumps(entry, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8", newline="\n",
            )
            with self.assertRaises(AssetError):
                load_p1_harmful_active_entry(root, "configs/stage3/counterfeit.json")

    def test_other_candidate_without_exact_active_entry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            root = Path(temporary)
            package = root / "data/other_candidate"
            package.mkdir(parents=True)
            (package / "selected.json").write_text(
                '{"candidate_only":true,"formal_input":false}\n', encoding="utf-8", newline="\n"
            )
            with self.assertRaises(AssetError):
                load_p1_harmful_active_entry(root, "configs/stage3/other_candidate.json")


if __name__ == "__main__":
    unittest.main()
