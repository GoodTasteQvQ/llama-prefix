from __future__ import annotations

import copy
import os
import unittest

from stage3_pipeline.core import DECODE_CONFIG, IdentityError, LogicalIdentityRegistry, PipelineError, canonical_sha256
from stage3_pipeline.execution import (
    build_logical_plan,
    reconcile_execution,
    reconcile_support_mapping,
)
from stage3_pipeline.dose import build_call_dose_evidence
from tests.stage3.helpers import ROOT, block_identity, completed_chain, test_dose_binding


def paper_registry() -> LogicalIdentityRegistry:
    screen = [f"screen-{index:02d}" for index in range(30)]
    confirm = [f"confirm-{index:02d}" for index in range(50)]
    benign = [f"benign-{index:02d}" for index in range(30)]
    all_prompts = screen + confirm + benign
    bindings = {
        "model_revision": "fake-model-revision",
        "template_sha256": "1" * 64,
        "rendered_prompt_sha256_by_id": {
            prompt_id: canonical_sha256(["rendered", prompt_id]) for prompt_id in all_prompts
        },
        "layer": 1,
        "hook_site": "resid_post",
        "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
        "code_sha256": "2" * 64,
        "config_sha256": "3" * 64,
        "environment_sha256": "4" * 64,
    }
    return build_logical_plan(
        bindings=bindings,
        screen_prompt_ids=screen,
        confirm_prompt_ids=confirm,
        benign_prompt_ids=benign,
        vector_ids_by_index={index: f"vector-{index:02d}" for index in range(30)},
        dose_binding=test_dose_binding(),
    )


def unattempted_dispositions(
    registry: LogicalIdentityRegistry,
    *,
    support_status: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    status = support_status or {}
    result: list[dict[str, object]] = []
    for row in registry.records():
        block = row["identity"]["block"]
        if status.get("A") == "NON_ESTIMABLE_IDENTITY" and block in {"P2_A_all", "P2_A_content"}:
            reason = "SUPPORT_A_NON_ESTIMABLE_IDENTITY"
        elif status.get("T") == "NON_ESTIMABLE_IDENTITY" and block in {"P2_T_all", "P2_T_content", "benign_T"}:
            reason = "SUPPORT_T_NON_ESTIMABLE_IDENTITY"
        else:
            reason = "EXTERNAL_INPUT_INTEGRITY"
        result.append({
            "schema_version": "paper1-stage3-execution-disposition-v2",
            "logical_id": row["logical_id"],
            "identity_sha256": canonical_sha256(row["identity"]),
            "terminal_disposition": "UNATTEMPTED_DUE_INTEGRITY_BLOCK",
            "generation_record_sha256": None,
            "judge_record_sha256": None,
            "response_record_sha256": None,
            "integrity_block_reason": reason,
        })
    return result


def support_mapping_dispositions(
    registry: LogicalIdentityRegistry,
    support_records: list[dict[str, object]],
    *,
    support_status: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    result = unattempted_dispositions(registry, support_status=support_status)
    by_id = {record["logical_id"]: record for record in support_records}
    for disposition in result:
        record = by_id.get(disposition["logical_id"])
        if record is None:
            continue
        disposition.update({
            "terminal_disposition": record["terminal_status"],
            "generation_record_sha256": record["generation_record_sha256"],
            "judge_record_sha256": record["judge_record_sha256"],
            "response_record_sha256": record["record_sha256"],
            "integrity_block_reason": None,
        })
    return result


def support_rows(registry: LogicalIdentityRegistry) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in registry.records():
        identity = row["identity"]
        if identity["block"] != "support":
            continue
        logical_id = row["logical_id"]
        evidence = build_call_dose_evidence(
            identity=identity, dose_binding=test_dose_binding(), generation_status="COMPLETED",
            pre_hook_l2=2.0, post_hook_l2=2.1, vector_alignment=0.5, cosine_drift=0.1,
        )
        record: dict[str, object] = {
            "schema_version": "paper1-stage3-support-response-record-v1",
            "protocol_version": "paper1-stage3-current-v1",
            "run_mode": "paper",
            "paper_result_eligible": False,
            "fake_backend": True,
            "logical_id": logical_id,
            "identity_sha256": canonical_sha256(identity),
            "generation_record_sha256": canonical_sha256(["generation", logical_id]),
            "judge_record_sha256": canonical_sha256(["judge", logical_id]),
            "prompt_id": identity["prompt_id"],
            "vector_id": identity["vector_id"],
            "anchor": identity["anchor"],
            "estimator": identity["estimator"],
            "scheduled_identity_match": True,
            "generation_completed": True,
            "judge_eligible": True,
            "judge_label_parsed": True,
            "identity_complete": True,
            "identity_collision": False,
            "dose_denominator_valid": True,
            "dose_geometry_finite": True,
            "post_dtype_alpha_finite": True,
            "generation_terminal_status": "COMPLETED",
            "judge_terminal_status": "PARSED",
            "dose_evidence": evidence,
            "label": "safe",
            "terminal_status": "COMPLETED_PARSED",
            "missingness_code": None,
            "retained": True,
        }
        record["record_sha256"] = canonical_sha256(record)
        records.append(record)
    return records


def mark_judge_failure(record: dict[str, object]) -> None:
    record["judge_label_parsed"] = False
    record["judge_terminal_status"] = "TERMINAL_PARSE_OR_INFRASTRUCTURE_FAILURE"
    record["label"] = None
    record["terminal_status"] = "TERMINAL_JUDGE_FAILURE"
    record["missingness_code"] = "TERMINAL_JUDGE_FAILURE"
    record["retained"] = False
    record["record_sha256"] = canonical_sha256(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )


class ExecutionReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.update({
            "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "TEMP": str(ROOT / ".codex-temp"), "TMP": str(ROOT / ".codex-temp"),
        })

    def test_small_registry_reconciliation_derives_all_counts(self) -> None:
        chain = completed_chain("support")
        result = chain["reconciliation"]
        self.assertEqual(result["scheduled_logical_ids"], 1)
        self.assertEqual(result["generation_first_pass_calls"], 1)
        self.assertEqual(result["judge_parsed"], 1)
        self.assertEqual(result["terminal_partition"]["COMPLETED_PARSED"], 1)
        self.assertEqual(result["k1_additional_generation_calls"], 0)
        self.assertEqual(result["k1_additional_judge_calls"], 0)
        self.assertEqual(len(result["support_mapping_sha256"]), 64)
        chain = completed_chain("support", prompt_id="support-source-binding")
        with self.assertRaises(PipelineError):
            reconcile_support_mapping(
                chain["registry"], run_mode="smoke", support_records=[],
                dispositions=[chain["disposition"]],
            )

    def test_duplicate_missing_unexpected_and_overlap_fail_closed(self) -> None:
        chain = completed_chain("support")
        base = {
            "registry": chain["registry"], "run_mode": "smoke",
            "generation_records": [chain["generation"]], "judge_records": [chain["judge"]],
            "response_records": [chain["response"]], "dispositions": [chain["disposition"]],
            "dose_binding": chain["dose_binding"],
        }
        cases = [
            {**base, "generation_records": [chain["generation"], chain["generation"]]},
            {**base, "dispositions": []},
            {**base, "dispositions": [chain["disposition"], chain["disposition"]]},
        ]
        other = completed_chain("support", prompt_id="unexpected")
        cases.append({**base, "generation_records": [chain["generation"], other["generation"]]})
        for index, case in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises((IdentityError, PipelineError)):
                    reconcile_execution(**case)

    def test_forged_record_and_disposition_lineage_fail(self) -> None:
        chain = completed_chain("P2_A_all")
        response = copy.deepcopy(chain["response"])
        response["identity_sha256"] = "f" * 64
        response["record_sha256"] = canonical_sha256({key: value for key, value in response.items() if key != "record_sha256"})
        with self.assertRaises(PipelineError):
            reconcile_execution(
                chain["registry"], run_mode="smoke", generation_records=[chain["generation"]],
                judge_records=[chain["judge"]], response_records=[response],
                dispositions=[chain["disposition"]], dose_binding=chain["dose_binding"],
            )
        disposition = copy.deepcopy(chain["disposition"])
        disposition["response_record_sha256"] = "f" * 64
        with self.assertRaises(PipelineError):
            reconcile_execution(
                chain["registry"], run_mode="smoke", generation_records=[chain["generation"]],
                judge_records=[chain["judge"]], response_records=[chain["response"]],
                dispositions=[disposition], dose_binding=chain["dose_binding"],
            )

    def test_paper_5580_partition_and_small_profile_distinction(self) -> None:
        registry = paper_registry()
        dispositions = unattempted_dispositions(
            registry,
            support_status={"A": "NON_ESTIMABLE_IDENTITY", "T": "NON_ESTIMABLE_IDENTITY"},
        )
        result = reconcile_execution(
            registry, run_mode="paper", generation_records=[], judge_records=[],
            response_records=[], dispositions=dispositions, dose_binding=test_dose_binding(),
        )
        self.assertEqual(result["scheduled_logical_ids"], 5_580)
        self.assertEqual(result["unattempted_count"], 5_580)
        small = LogicalIdentityRegistry()
        small.register(block_identity("support"))
        with self.assertRaises(IdentityError):
            reconcile_execution(
                small, run_mode="paper", generation_records=[], judge_records=[],
                response_records=[], dispositions=[], dose_binding=test_dose_binding(),
            )
        self.assertEqual(completed_chain()["reconciliation"]["scheduled_logical_ids"], 1)

    def test_paper_same_total_wrong_block_composition_fails_closed(self) -> None:
        wrong = LogicalIdentityRegistry()
        for index in range(5_580):
            wrong.register(block_identity("support", f"wrong-support-{index}"))
        with self.assertRaises((IdentityError, PipelineError)):
            reconcile_execution(
                wrong, run_mode="paper", generation_records=[], judge_records=[],
                response_records=[], dispositions=[], dose_binding=test_dose_binding(),
            )

    def test_support_supported_and_limited_keep_fixed_downstream_n(self) -> None:
        registry = paper_registry()
        records = support_rows(registry)
        dispositions = support_mapping_dispositions(registry, records)
        supported = reconcile_support_mapping(
            registry, run_mode="paper", support_records=records, dispositions=dispositions
        )
        self.assertEqual(supported["anchors"]["A"]["status"], "SUPPORTED")
        self.assertEqual(supported["anchors"]["A"]["downstream_logical_ids"], 2_000)
        self.assertEqual(supported["anchors"]["T"]["downstream_logical_ids"], 2_600)
        self.assertEqual(supported["anchors"]["H"]["downstream_logical_ids"], 0)
        limited_rows = copy.deepcopy(records)
        changed = 0
        for record in limited_rows:
            if record["anchor"] == "A" and changed < 20:
                mark_judge_failure(record)
                changed += 1
        limited_dispositions = support_mapping_dispositions(registry, limited_rows)
        limited = reconcile_support_mapping(
            registry, run_mode="paper", support_records=limited_rows,
            dispositions=limited_dispositions,
        )
        self.assertEqual(limited["anchors"]["A"]["status"], "SUPPORT_LIMITED")
        self.assertTrue(limited["anchors"]["A"]["estimation_only"])
        self.assertEqual(limited["anchors"]["A"]["downstream_logical_ids"], 2_000)

    def test_support_nonestimable_maps_exact_fixed_ids_and_wrong_mapping_fails(self) -> None:
        registry = paper_registry()
        records = support_rows(registry)
        removed = next(index for index, record in enumerate(records) if record["anchor"] == "A")
        records.pop(removed)
        dispositions = support_mapping_dispositions(
            registry, records, support_status={"A": "NON_ESTIMABLE_IDENTITY"}
        )
        mapped = reconcile_support_mapping(
            registry, run_mode="paper", support_records=records, dispositions=dispositions
        )
        self.assertEqual(mapped["anchors"]["A"]["status"], "NON_ESTIMABLE_IDENTITY")
        self.assertEqual(mapped["anchors"]["A"]["unattempted_due_integrity_block"], 2_000)
        wrong = copy.deepcopy(dispositions)
        target = next(
            item for item in wrong
            if item["integrity_block_reason"] == "SUPPORT_A_NON_ESTIMABLE_IDENTITY"
        )
        target["integrity_block_reason"] = "EXTERNAL_INPUT_INTEGRITY"
        with self.assertRaises(PipelineError):
            reconcile_support_mapping(
                registry, run_mode="paper", support_records=records, dispositions=wrong
            )
        forged_hash = copy.deepcopy(dispositions)
        forged_hash[0]["identity_sha256"] = "f" * 64
        with self.assertRaises(IdentityError):
            reconcile_support_mapping(
                registry, run_mode="paper", support_records=records, dispositions=forged_hash
            )
        cross_anchor = copy.deepcopy(dispositions)
        unrelated_id = next(
            row["logical_id"] for row in registry.records()
            if row["identity"]["block"] == "benign_T"
        )
        unrelated = next(item for item in cross_anchor if item["logical_id"] == unrelated_id)
        unrelated["integrity_block_reason"] = "SUPPORT_A_NON_ESTIMABLE_IDENTITY"
        with self.assertRaises(PipelineError):
            reconcile_support_mapping(
                registry, run_mode="paper", support_records=records, dispositions=cross_anchor
            )
        t_records = support_rows(registry)
        t_records.pop(next(index for index, record in enumerate(t_records) if record["anchor"] == "T"))
        t_dispositions = support_mapping_dispositions(
            registry, t_records, support_status={"T": "NON_ESTIMABLE_IDENTITY"}
        )
        t_mapped = reconcile_support_mapping(
            registry, run_mode="paper", support_records=t_records, dispositions=t_dispositions
        )
        self.assertEqual(t_mapped["anchors"]["T"]["unattempted_due_integrity_block"], 2_600)

    def test_support_duplicate_and_forged_anchor_fail_closed(self) -> None:
        registry = paper_registry()
        records = support_rows(registry)
        dispositions = support_mapping_dispositions(registry, records)
        with self.assertRaises(IdentityError):
            reconcile_support_mapping(
                registry, run_mode="paper", support_records=records + [records[0]],
                dispositions=dispositions,
            )
        forged = copy.deepcopy(records)
        forged[0]["anchor"] = "T" if forged[0]["anchor"] == "A" else "A"
        forged[0]["record_sha256"] = canonical_sha256(
            {key: value for key, value in forged[0].items() if key != "record_sha256"}
        )
        with self.assertRaises(IdentityError):
            reconcile_support_mapping(
                registry, run_mode="paper", support_records=forged,
                dispositions=dispositions,
            )


if __name__ == "__main__":
    unittest.main()
