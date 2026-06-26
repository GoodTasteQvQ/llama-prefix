#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from activation_guard import ExperimentConfig, ExperimentRunner
from activation_guard.vectors import ensure_random_vector_pool


ALPHA_GRID = [round(0.25 * index, 2) for index in range(0, 9)]


def parse_float_grid(raw: str | None, default: Iterable[float]) -> list[float]:
    if raw is None:
        return [float(item) for item in default]
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("alpha-grid cannot be empty")
    return [float(item) for item in values]


def resolve_vector_indices(
    *,
    mode: str,
    num_vectors: int,
    single_vector_index: int,
    vector_start: int | None,
    vector_end: int | None,
) -> list[int]:
    if mode == "debug":
        return [single_vector_index]
    start = 0 if vector_start is None else vector_start
    end = (num_vectors - 1) if vector_end is None else vector_end
    if start < 0 or end < 0 or start >= num_vectors or end >= num_vectors or start > end:
        raise ValueError(
            f"Invalid vector range [{start}, {end}] for num_vectors={num_vectors}"
        )
    return list(range(start, end + 1))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run stage1 Track A fixed-alpha semantic audit.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--vector-pool", default="./results/stage1_phase_aware/random_vector_pools/qwen25_stage1_vectors.pt")
    parser.add_argument("--num-vectors", type=int, default=1000)
    parser.add_argument("--mode", choices=["debug", "formal"], default="formal")
    parser.add_argument("--single-vector-index", type=int, default=0)
    parser.add_argument("--single-alpha", type=float, default=1.0)
    parser.add_argument("--vector-start", type=int, default=None)
    parser.add_argument("--vector-end", type=int, default=None)
    parser.add_argument("--alpha-grid", default=None)
    parser.add_argument("--prompt-limit", type=int, default=None)
    parser.add_argument("--prompt-offset", type=int, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = ExperimentConfig.from_json(args.config)
    if args.prompt_limit is not None:
        config.dataset.limit = args.prompt_limit
    if args.prompt_offset is not None:
        config.dataset.offset = args.prompt_offset
    runner = ExperimentRunner(config)
    try:
        pool_info = ensure_random_vector_pool(
            vector_path=args.vector_pool,
            hidden_dim=runner.model.config.hidden_size,
            num_vectors=args.num_vectors,
            seed=config.generation.seed,
            normalize=True,
        )
        prompts = runner.get_prompts()
        vector_indices = resolve_vector_indices(
            mode=args.mode,
            num_vectors=args.num_vectors,
            single_vector_index=args.single_vector_index,
            vector_start=args.vector_start,
            vector_end=args.vector_end,
        )
        alpha_grid = (
            [args.single_alpha]
            if args.mode == "debug"
            else parse_float_grid(args.alpha_grid, ALPHA_GRID)
        )
        runs = []
        total_tasks = len(vector_indices) * len(alpha_grid)
        completed_tasks = 0
        t_start_all = time.time()
        print(f"[progress] START total_tasks={total_tasks} vectors={len(vector_indices)} alphas={len(alpha_grid)}", flush=True)
        for v_idx, vector_index in enumerate(vector_indices):
            t_vec_start = time.time()
            for a_idx, alpha in enumerate(alpha_grid):
                attack_override = {
                    "vector_source": "tensor_file",
                    "vector_path": pool_info["vector_path"],
                    "vector_index": vector_index,
                    "strength_mode": "fixed_alpha",
                    "coefficient": alpha,
                    "effective_alpha": alpha,
                    "coefficient_c": None,
                    "activation_norm_mu": None,
                    "mu_source": None,
                    "mu_config": {},
                }
                experiment_name = f"{config.experiment_name}_vector{vector_index:04d}_alpha{alpha:.2f}"
                summary = runner.run(
                    prompts=prompts,
                    attack_override=attack_override,
                    experiment_name=experiment_name,
                    tags=list(config.tags) + ["stage1", "track-a", args.mode],
                    output_path=None,
                )
                runs.append({
                    "experiment_name": experiment_name,
                    "vector_index": vector_index,
                    "alpha": alpha,
                    "mean_arr": summary["mean_arr"],
                    "mean_repetition_rate": summary["mean_repetition_rate"],
                    "mean_latency_seconds": summary["mean_latency_seconds"],
                    "phase_audit_summary": summary["phase_audit_summary"],
                })
                completed_tasks += 1
                elapsed_all = time.time() - t_start_all
                avg_per_task = elapsed_all / completed_tasks
                remaining = avg_per_task * (total_tasks - completed_tasks)
                print(
                    f"[progress] {completed_tasks}/{total_tasks} "
                    f"vector={vector_index} alpha={alpha:.2f} "
                    f"elapsed={elapsed_all:.0f}s eta={remaining:.0f}s "
                    f"mean_arr={summary['mean_arr']:.4f}",
                    flush=True,
                )
            vec_elapsed = time.time() - t_vec_start
            print(
                f"[progress] VECTOR_DONE vector={vector_index} ({v_idx+1}/{len(vector_indices)}) "
                f"took={vec_elapsed:.0f}s",
                flush=True,
            )
    finally:
        runner.close()

    payload = {
        "track": "fixed_alpha",
        "mode": args.mode,
        "config": config.to_dict(),
        "vector_pool": pool_info,
        "vector_start": vector_indices[0],
        "vector_end": vector_indices[-1],
        "vector_indices": vector_indices,
        "alpha_grid": alpha_grid,
        "prompt_limit": config.dataset.limit,
        "prompt_offset": config.dataset.offset,
        "runs": runs,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(output_path)
    total_elapsed = time.time() - t_start_all
    print(f"[progress] ALL_DONE total_elapsed={total_elapsed:.0f}s saved_to={output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
