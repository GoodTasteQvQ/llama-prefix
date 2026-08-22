from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote

from stage3_pipeline.json_schema import load_schema
from tests.stage3.helpers import ACTIVE_ENTRY, P1_DIRECTORY, P1_INPUT, ROOT


class RepositoryTests(unittest.TestCase):
    def test_p1_directory_is_byte_identical_to_head(self) -> None:
        files = sorted(path for path in P1_DIRECTORY.iterdir() if path.is_file())
        self.assertEqual(len(files), 12)
        digest = hashlib.sha256(P1_INPUT.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "700c2c391c86273fca01ec9823feb66a3b1927ac39cc81d1de7567c71bebfd36",
        )
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            head_bytes = subprocess.run(
                ["git", "show", f"HEAD:{relative}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
            ).stdout
            self.assertEqual(path.read_bytes(), head_bytes, relative)
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("data/stage3/p1_harmful_do_not_answer_v1/** -text -diff", attributes)
        self.assertEqual(
            attributes.count("configs/stage3/p1_harmful_do_not_answer_v1.json text eol=lf"), 1
        )
        self.assertNotIn(b"\r\n", (ROOT / ".gitattributes").read_bytes())
        self.assertNotIn(b"\r\n", ACTIVE_ENTRY.read_bytes())
        attr = subprocess.run(
            ["git", "check-attr", "text", "eol", "--", "configs/stage3/p1_harmful_do_not_answer_v1.json"],
            cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout
        self.assertIn("text: set", attr)
        self.assertIn("eol: lf", attr)

    def test_single_design_entry_and_scientific_invariants(self) -> None:
        design_directory = ROOT / "writing/stage3 design"
        files = sorted(
            path.relative_to(design_directory).as_posix()
            for path in design_directory.rglob("*")
            if path.is_file()
        )
        self.assertEqual(files, [
            "README.md",
            "paper1_stage3_experiment_design.md",
            "paper1_stage3_protocol_amendment_p2_v2.md",
        ])
        design = (design_directory / "paper1_stage3_experiment_design.md").read_text(
            encoding="utf-8"
        )
        required = (
            "CURRENT SCIENTIFIC BASELINE / ACTIVE DEVELOPMENT",
            "compact_single_gpu",
            "Qwen only",
            "N_norm_harmful = 100",
            "N_norm_benign = 100",
            "P = 50",
            "V = 20",
            "N_benign_prompt = 30",
            "N_human_items = 720",
            "5,580",
            "K1 reuse",
            "two-phase",
            "Design Change Log",
            "smoke",
            "pilot",
            "paper",
            "P1 harmful prompt-source concretization after pre-outcome source/selection audit.",
            "Behavior-cell ARR and mean 3-gram repetition descriptive reporting explicitly migrated",
            "Libr-AI/do-not-answer",
            "460703484df354958a5e1cd7378a38fcb94a2f3e",
            "afcb3bcfe3042bf37189fc9718b53389ce0145e43b75efc3364e250e86552410",
        )
        for marker in required:
            self.assertIn(marker, design)

    def test_proof_only_paths_are_absent(self) -> None:
        absent = (
            "writing/archive/paper1_stage3_history",
            "writing/judge subagent",
            "scripts/stage3_rc2",
            "scripts/stage3_design",
            "stage3_artifacts_final_round7",
            "stage3_artifacts_final_round8",
            "stage3_artifacts_final_round9",
            "stage3_artifacts_final_round10",
            "writing/stage3 design/CURRENT_RELEASE.md",
        )
        for relative in absent:
            path = ROOT / relative
            self.assertFalse(any(path.rglob("*")) if path.is_dir() else path.exists(), relative)

    def test_active_runtime_has_no_freeze_dependencies(self) -> None:
        prohibited = (
            "FreezeLifecycle",
            "CURRENT_RELEASE",
            "verification_receipts",
            "stage3_artifacts_final_round",
            "v3_5_rc2_binding_amendment",
            "formal_lifecycle_event",
            "RUN-BLOCKED",
            "DATA_IDENTITY_BLOCKED",
            "OFFLINE-ASSET-READY",
            "FORMAL_INPUT",
            "AppendOnlyReceipt",
        )
        files = list((ROOT / "stage3_pipeline").rglob("*.py")) + list(
            (ROOT / "scripts/stage3_production").rglob("*.py")
        )
        for path in files:
            text = path.read_text(encoding="utf-8")
            for marker in prohibited:
                self.assertNotIn(marker, text, f"{marker} in {path.relative_to(ROOT)}")

    def test_active_markdown_links_resolve(self) -> None:
        documents = (
            ROOT / "writing/paper1_writing_blueprint.md",
            ROOT / "writing/paper1_claim_evidence_matrix.md",
            ROOT / "writing/paper1_stage3_execution_checklist.md",
            ROOT / "writing/paper_writing_map.md",
            ROOT / "writing/stage3 design/README.md",
            ROOT / "writing/stage3 design/paper1_stage3_experiment_design.md",
        )
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for target in link_pattern.findall(text):
                if target.startswith(("http://", "https://", "#")):
                    continue
                target_path = target.split("#", 1)[0]
                resolved = (document.parent / unquote(target_path)).resolve()
                self.assertTrue(resolved.exists(), f"broken link in {document}: {target}")
            for marker in (
                "CURRENT_RELEASE",
                "binding-amendment",
                "DESIGN-FREEZE-PASS",
                "RUN-BLOCKED",
                "Round 7",
                "Round 8",
                "Round 9",
                "Round 10",
                "Round 11",
                "Round 12",
            ):
                self.assertNotIn(marker, text, f"stale marker in {document.relative_to(ROOT)}")

    def test_staging_area_is_empty(self) -> None:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
        self.assertEqual(staged, "")

    def test_active_entry_exact_values_schemas_parse_and_no_bytecode(self) -> None:
        entry = json.loads(ACTIVE_ENTRY.read_text(encoding="utf-8"))
        self.assertEqual(entry["role"], "D_norm_confirm.harmful")
        self.assertEqual(entry["status"], "design_selected")
        self.assertEqual(entry["row_count"], 100)
        self.assertEqual(entry["source_row_count"], 939)
        self.assertEqual(entry["eligible_count"], 239)
        self.assertEqual(sum(entry["category_quotas"].values()), 100)
        schemas = sorted((ROOT / "stage3_pipeline/schemas").glob("*.json"))
        self.assertGreaterEqual(len(schemas), 9)
        for schema in schemas:
            load_schema(schema.resolve())
        bytecode = list((ROOT / "stage3_pipeline").rglob("*.pyc")) + list(
            (ROOT / "tests/stage3").rglob("*.pyc")
        )
        self.assertEqual(bytecode, [])


if __name__ == "__main__":
    unittest.main()
