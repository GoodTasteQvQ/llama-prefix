from __future__ import annotations

import os
import unittest

from stage3_pipeline.core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    GenerationProducer,
    PipelineError,
    TechnicalGenerationError,
    TerminalGenerationError,
    LogicalIdentityRegistry,
    parse_judge_with_retry,
)
from stage3_pipeline.execution import response_terminal_disposition
from stage3_pipeline.records import build_block_response_record
from tests.stage3.helpers import block_identity, completed_chain


class RealSmokeDispositionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.update({
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        })

    def _failed_clean_chain(self, failure: BaseException) -> tuple[dict, dict, dict]:
        identity = block_identity("harmful_clean", "disposition-failure")
        registry = LogicalIdentityRegistry()
        logical_id = registry.register(identity)

        def backend(_identity: object, _request: object) -> dict[str, object]:
            raise failure

        generation = GenerationProducer(
            registry, backend, run_mode="smoke", fake_backend=True,
        ).produce(logical_id, {
            "logical_id": logical_id,
            "generation_config": DECODE_CONFIG,
        })
        response = build_block_response_record(
            identity=identity,
            generation_record=generation,
            judge_record=None,
            dose_evidence=None,
        )
        return identity, generation, response

    def test_success_response_maps_to_completed_disposition(self) -> None:
        chain = completed_chain("harmful_clean")
        self.assertEqual(
            response_terminal_disposition(
                chain["identity"], chain["response"], chain["generation"], chain["judge"]
            ),
            "COMPLETED_PARSED",
        )

    def test_legal_terminal_failure_response_maps_without_response_alias(self) -> None:
        identity, generation, response = self._failed_clean_chain(
            TerminalGenerationError("deterministic fixture")
        )
        self.assertEqual(
            response_terminal_disposition(identity, response, generation, None),
            "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
        )

    def test_retryable_uncompleted_response_maps_to_terminal_technical_failure(self) -> None:
        identity, generation, response = self._failed_clean_chain(
            TechnicalGenerationError("retryable fixture")
        )
        self.assertEqual(generation["terminal_status"], "TERMINAL_TECHNICAL_FAILURE")
        self.assertEqual(
            response_terminal_disposition(identity, response, generation, None),
            "TERMINAL_GENERATION_TECHNICAL_FAILURE",
        )

    def test_legal_terminal_judge_failure_maps_to_judge_failure(self) -> None:
        chain = completed_chain("harmful_clean", prompt_id="disposition-judge-failure")
        judge = parse_judge_with_retry(
            chain["logical_id"],
            lambda _attempt, _request: "not-json",
            {"logical_id": chain["logical_id"], "judge_config": JUDGE_CONFIG},
            registry=chain["registry"],
            generation_record=chain["generation"],
            run_mode="smoke",
            judge_identity={
                "model_path_or_id": "fake-judge",
                "tokenizer_path_or_id": "fake-tokenizer",
                "rubric_sha256": "1" * 64,
            },
            fake_backend=True,
        )
        response = build_block_response_record(
            identity=chain["identity"],
            generation_record=chain["generation"],
            judge_record=judge,
            dose_evidence=None,
        )
        self.assertEqual(
            response_terminal_disposition(
                chain["identity"], response, chain["generation"], judge
            ),
            "TERMINAL_JUDGE_FAILURE",
        )

    def test_missing_identity_fields_fail_closed(self) -> None:
        chain = completed_chain("harmful_clean")
        with self.assertRaises(PipelineError):
            response_terminal_disposition(
                {}, chain["response"], chain["generation"], chain["judge"]
            )

    def test_fake_backend_cannot_be_declared_real(self) -> None:
        chain = completed_chain("harmful_clean")
        with self.assertRaises(PipelineError):
            GenerationProducer(
                chain["registry"],
                lambda _identity, _request: {"output_text": "fake", "diagnostics": {}},
                run_mode="smoke",
                fake_backend=False,
            )


if __name__ == "__main__":
    unittest.main()
