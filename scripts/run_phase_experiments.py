#!/usr/bin/env python
"""Run paper-oriented phase-aware activation steering experiments."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from activation_guard import ExperimentConfig, ExperimentRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run phase-aware activation steering experiments from a JSON config.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to an experiment JSON config.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = Path(args.config).resolve()
    config = ExperimentConfig.from_json(config_path)
    runner = ExperimentRunner(config)
    try:
        summary = runner.run()
    finally:
        runner.close()

    print(f"Finished experiment: {summary['experiment_name']}")
    print(f"Prompts processed: {summary['num_prompts']}")
    print(f"Mean ARR: {summary['mean_arr']:.4f}")
    print(f"Mean repetition rate: {summary['mean_repetition_rate']:.4f}")
    print(f"Mean latency (s): {summary['mean_latency_seconds']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
