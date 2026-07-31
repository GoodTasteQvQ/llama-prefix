"""Neutral adapters for the current Stage 3 statistical implementations."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .statistics import human_quota, reference_statistics, retained_bootstrap, two_phase


class StatisticsAdapter:
    """Expose the current statistical algorithms through one stable API."""

    def p1(self, strata: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
        return reference_statistics.p1_interval(
            dict(strata), replicates=10_000, min_success=9_500
        )

    def p2_raw(self, members: Sequence[dict[str, Any]]) -> dict[str, Any]:
        return reference_statistics.p2_raw_simultaneous(
            list(members), replicates=9_999, min_success=9_500
        )

    def retained_k1(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return retained_bootstrap.analyze_k1(payload, fixture_mode=False)

    def retained_harmful_clean(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return retained_bootstrap.analyze_harmful_clean(payload, fixture_mode=False)

    def retained_benign_broken(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return retained_bootstrap.analyze_benign_broken(payload, fixture_mode=False)

    def two_phase_point(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return two_phase.point_estimates(payload)

    def two_phase_interval(
        self, payload: Mapping[str, Any], *, vector_aware: bool
    ) -> dict[str, Any]:
        block = two_phase.BLOCKS["vector" if vector_aware else "prompt"]
        return two_phase.simultaneous_interval(payload, block)

    def fixed720(self, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return human_quota.allocate_human_sample(records, n_total=720, master_seed=42)


def implementation_inventory() -> dict[str, Any]:
    """Describe active statistical coverage without release or hash semantics."""
    return {
        "status": "IMPLEMENTATION_AVAILABLE",
        "algorithms": [
            "p1-bootstrap",
            "p2-raw-two-way",
            "retained-bootstrap",
            "two-phase-correction",
            "fixed720",
        ],
        "alternate_algorithm": False,
    }
