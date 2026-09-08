#!/usr/bin/env python
"""Create publication-ready cross-model Track-B figures for Paper 1.

The visual style follows common recent IEEE TDSC conventions observed in:

1. Lai et al., "On Security Weaknesses and Vulnerabilities in Deep Learning
   Systems," IEEE TDSC, 2025. DOI: 10.1109/TDSC.2024.3482707.
2. Ennaji et al., "Adversarial Challenges in Network Intrusion Detection
   Systems: Research Insights and Future Prospects," IEEE TDSC, 2025,
   arXiv:2409.18736.

The script uses muted colors, thin neutral grids, compact shared legends,
marker/line-style redundancy, percentage axes, and vector output. It reads the
normalized Track-B CSV files produced by plot_judge_v2_results.py.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator, PercentFormatter


METHOD_ORDER = [
    "rogue_v1",
    "no_cache",
    "decode_only",
    "full",
    "first_k",
    "decay",
]

EXPECTED_STRENGTHS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

METHOD_LABELS = {
    "rogue_v1": "Rogue v1",
    "no_cache": "No-cache",
    "decode_only": "Decode-only",
    "full": "Full",
    "first_k": "First-k",
    "decay": "Decay",
}

# Low-saturation, colorblind-friendly colors inspired by recent TDSC figures.
METHOD_STYLES: dict[str, dict[str, Any]] = {
    "rogue_v1": {
        "color": "#4F9994",
        "marker": "o",
        "linestyle": "-",
    },
    "no_cache": {
        "color": "#E6A04B",
        "marker": "s",
        "linestyle": "--",
    },
    "decode_only": {
        "color": "#E06B5D",
        "marker": "^",
        "linestyle": "-",
    },
    "full": {
        "color": "#5B88B2",
        "marker": "D",
        "linestyle": "-.",
    },
    "first_k": {
        "color": "#9589B8",
        "marker": "P",
        "linestyle": ":",
    },
    "decay": {
        "color": "#737373",
        "marker": "X",
        "linestyle": (0, (5, 2)),
    },
}

MODEL_BAR_COLORS = {
    "qwen": "#4F9994",
    "llama": "#E06B5D",
}

REQUIRED_COLUMNS = {
    "method",
    "strength",
    "num_records",
    "asr",
    "broken_rate",
    "mean_arr",
    "mean_repetition_rate",
}


@dataclass(frozen=True)
class ModelSeries:
    key: str
    title: str
    short_label: str
    rows: list[dict[str, Any]]
    n_per_condition: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate TDSC-style cross-model Paper-1 figures."
    )
    parser.add_argument(
        "--qwen-csv",
        default=(
            "results/stage1_phase_aware/formal/qwen25/judge_summaries/"
            "qwen25_stage1_qwen3_v2_all6_full1000_plots/tables/trackB_curves.csv"
        ),
        help="Qwen Track-B normalized CSV.",
    )
    parser.add_argument(
        "--llama-csv",
        default=(
            "results/stage1_phase_aware/formal/llama31/judge_summaries/"
            "llama31_stage1_qwen3_v2_100sample_plots/tables/trackB_curves.csv"
        ),
        help="Llama3.1 Track-B normalized CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "results/stage1_phase_aware/formal/"
            "cross_model_paper1/tdsc_style_figures"
        ),
        help="Directory for generated figures and manifest.json.",
    )
    parser.add_argument(
        "--formats",
        default="png,pdf,svg",
        help="Comma-separated output formats.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=320,
        help="PNG resolution.",
    )
    parser.add_argument(
        "--arr-column",
        default="mean_arr",
        help=(
            "ARR column to plot. The current default is the legacy ARR rule; "
            "a future recomputed CSV may supply an ARR-v2 column here."
        ),
    )
    return parser


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 8.2,
            "axes.titlesize": 8.6,
            "axes.labelsize": 8.2,
            "axes.titleweight": "bold",
            "axes.linewidth": 0.65,
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#202020",
            "xtick.labelsize": 7.4,
            "ytick.labelsize": 7.4,
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 3.0,
            "ytick.major.size": 3.0,
            "legend.fontsize": 7.3,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.edgecolor": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def read_trackb_csv(path: Path, arr_column: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Track-B CSV not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        required = set(REQUIRED_COLUMNS)
        required.add(arr_column)
        missing = sorted(required - columns)
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(missing)}")

        rows: list[dict[str, Any]] = []
        for raw in reader:
            method = raw["method"]
            if method not in METHOD_ORDER:
                raise ValueError(f"Unexpected method {method!r} in {path}")
            row = dict(raw)
            row["strength"] = float(raw["strength"])
            row["num_records"] = int(raw["num_records"])
            for key in [
                "asr",
                "broken_rate",
                "mean_arr",
                "mean_repetition_rate",
                arr_column,
            ]:
                row[key] = float(raw[key])
                if not 0.0 <= row[key] <= 1.0:
                    raise ValueError(f"{key}={row[key]} is outside [0, 1] in {path}")
            rows.append(row)

    validate_coverage(path, rows)
    return rows


def validate_coverage(path: Path, rows: list[dict[str, Any]]) -> None:
    if len(rows) != len(METHOD_ORDER) * len(EXPECTED_STRENGTHS):
        raise ValueError(
            f"Expected 54 Track-B rows in {path}, found {len(rows)}"
        )
    for method in METHOD_ORDER:
        actual = sorted(
            row["strength"] for row in rows if row["method"] == method
        )
        if actual != EXPECTED_STRENGTHS:
            raise ValueError(
                f"Strength coverage mismatch for {method} in {path}: {actual}"
            )


def build_model_series(
    key: str,
    title: str,
    short_label: str,
    rows: list[dict[str, Any]],
) -> ModelSeries:
    sample_sizes = sorted({int(row["num_records"]) for row in rows})
    if len(sample_sizes) != 1:
        raise ValueError(f"{title} has inconsistent sample sizes: {sample_sizes}")
    return ModelSeries(
        key=key,
        title=title,
        short_label=short_label,
        rows=rows,
        n_per_condition=sample_sizes[0],
    )


def group_by_method(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {method: [] for method in METHOD_ORDER}
    for row in rows:
        grouped[row["method"]].append(row)
    for values in grouped.values():
        values.sort(key=lambda row: row["strength"])
    return grouped


def style_axis(ax: Axes, *, ylim: tuple[float, float], major_y: float) -> None:
    ax.set_xlim(-0.03, 2.03)
    ax.set_ylim(*ylim)
    ax.set_xticks(EXPECTED_STRENGTHS)
    ax.set_xticklabels([f"{value:g}" for value in EXPECTED_STRENGTHS])
    ax.yaxis.set_major_locator(MultipleLocator(major_y))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    ax.grid(
        axis="y",
        color="#D7D7D7",
        linewidth=0.55,
        linestyle=(0, (2, 2)),
    )
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_method_lines(ax: Axes, rows: list[dict[str, Any]], metric: str) -> None:
    grouped = group_by_method(rows)
    for method in METHOD_ORDER:
        values = grouped[method]
        style = METHOD_STYLES[method]
        ax.plot(
            [row["strength"] for row in values],
            [row[metric] for row in values],
            color=style["color"],
            marker=style["marker"],
            linestyle=style["linestyle"],
            linewidth=1.45,
            markersize=4.1,
            markerfacecolor="white",
            markeredgewidth=1.0,
            label=METHOD_LABELS[method],
            zorder=3,
        )


def model_panel_title(index: int, model: ModelSeries) -> str:
    letter = chr(ord("a") + index)
    return (
        f"({letter}) {model.title} "
        f"(N={model.n_per_condition:,} per c)"
    )


def add_shared_method_legend(fig: Figure, axes: Iterable[Axes], y: float) -> None:
    first_axis = next(iter(axes))
    handles, labels = first_axis.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, y),
        ncol=3,
        frameon=False,
        handlelength=2.6,
        columnspacing=1.45,
        handletextpad=0.55,
    )


def save_figure(
    fig: Figure,
    output_dir: Path,
    stem: str,
    formats: list[str],
    dpi: int,
) -> list[str]:
    paths: list[str] = []
    for fmt in formats:
        path = output_dir / f"{stem}.{fmt}"
        kwargs: dict[str, Any] = {
            "bbox_inches": "tight",
            "pad_inches": 0.03,
        }
        if fmt == "png":
            kwargs["dpi"] = dpi
        fig.savefig(path, **kwargs)
        paths.append(str(path))
    plt.close(fig)
    return paths


def plot_two_panel_metric(
    models: list[ModelSeries],
    metric: str,
    ylabel: str,
    ylim: tuple[float, float],
    major_y: float,
    output_dir: Path,
    stem: str,
    formats: list[str],
    dpi: int,
) -> list[str]:
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 3.12), sharey=True)
    for index, (ax, model) in enumerate(zip(axes, models, strict=True)):
        plot_method_lines(ax, model.rows, metric)
        style_axis(ax, ylim=ylim, major_y=major_y)
        ax.set_title(model_panel_title(index, model), loc="left", pad=7)
        ax.set_xlabel("Rogue-calibrated strength, c")
    axes[0].set_ylabel(ylabel)
    add_shared_method_legend(fig, axes, y=-0.005)
    fig.subplots_adjust(left=0.085, right=0.99, top=0.90, bottom=0.25, wspace=0.12)
    return save_figure(fig, output_dir, stem, formats, dpi)


def plot_arr_repetition(
    models: list[ModelSeries],
    arr_column: str,
    output_dir: Path,
    formats: list[str],
    dpi: int,
) -> list[str]:
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 5.35), sharex=True, sharey=True)
    metrics = [
        (arr_column, "ARR (legacy rule)"),
        ("mean_repetition_rate", "Mean 3-gram repetition rate"),
    ]
    panel_index = 0
    for row_index, model in enumerate(models):
        for col_index, (metric, ylabel) in enumerate(metrics):
            ax = axes[row_index][col_index]
            plot_method_lines(ax, model.rows, metric)
            style_axis(ax, ylim=(0.0, 1.02), major_y=0.2)
            letter = chr(ord("a") + panel_index)
            ax.set_title(
                f"({letter}) {model.short_label}: {ylabel}",
                loc="left",
                pad=6,
            )
            if col_index == 0:
                ax.set_ylabel("Rate")
            if row_index == len(models) - 1:
                ax.set_xlabel("Rogue-calibrated strength, c")
            panel_index += 1
    add_shared_method_legend(fig, axes.flat, y=0.005)
    fig.subplots_adjust(left=0.085, right=0.99, top=0.95, bottom=0.15, hspace=0.32, wspace=0.12)
    return save_figure(
        fig,
        output_dir,
        "fig_trackb_arr_repetition_cross_model",
        formats,
        dpi,
    )


def peak_row(rows: list[dict[str, Any]], method: str, metric: str) -> dict[str, Any]:
    values = [row for row in rows if row["method"] == method]
    return max(values, key=lambda row: (row[metric], -row["strength"]))


def row_at_strength(
    rows: list[dict[str, Any]], method: str, strength: float
) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if row["method"] == method and row["strength"] == strength
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one {method} row at c={strength}, found {len(matches)}")
    return matches[0]


def add_bar_labels(
    ax: Axes,
    containers: list[Any],
    labels: list[list[str]],
    padding: float,
) -> None:
    for container, container_labels in zip(containers, labels, strict=True):
        ax.bar_label(
            container,
            labels=container_labels,
            padding=padding,
            fontsize=6.8,
            color="#333333",
        )


def plot_summary_bars(
    models: list[ModelSeries],
    output_dir: Path,
    formats: list[str],
    dpi: int,
) -> list[str]:
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 3.62), sharey=True)
    y_positions = list(range(len(METHOD_ORDER)))
    bar_height = 0.34

    qwen, llama = models
    peak_qwen = [peak_row(qwen.rows, method, "asr") for method in METHOD_ORDER]
    peak_llama = [peak_row(llama.rows, method, "asr") for method in METHOD_ORDER]
    c2_qwen = [row_at_strength(qwen.rows, method, 2.0) for method in METHOD_ORDER]
    c2_llama = [row_at_strength(llama.rows, method, 2.0) for method in METHOD_ORDER]

    panels = [
        (
            axes[0],
            [row["asr"] for row in peak_qwen],
            [row["asr"] for row in peak_llama],
            "(a) Peak ASR across c",
            0.42,
            [f"{100 * row['asr']:.1f}%@{row['strength']:g}" for row in peak_qwen],
            [f"{100 * row['asr']:.1f}%@{row['strength']:g}" for row in peak_llama],
        ),
        (
            axes[1],
            [row["broken_rate"] for row in c2_qwen],
            [row["broken_rate"] for row in c2_llama],
            "(b) Broken rate at c=2",
            1.05,
            [f"{100 * row['broken_rate']:.1f}%" for row in c2_qwen],
            [f"{100 * row['broken_rate']:.1f}%" for row in c2_llama],
        ),
    ]

    for ax, qwen_values, llama_values, title, xmax, q_labels, l_labels in panels:
        q_container = ax.barh(
            [y - bar_height / 2 for y in y_positions],
            qwen_values,
            height=bar_height,
            color=MODEL_BAR_COLORS["qwen"],
            alpha=0.92,
            label=f"Qwen2.5 (N={qwen.n_per_condition:,})",
        )
        l_container = ax.barh(
            [y + bar_height / 2 for y in y_positions],
            llama_values,
            height=bar_height,
            color=MODEL_BAR_COLORS["llama"],
            alpha=0.92,
            label=f"Llama3.1 (N={llama.n_per_condition:,})",
        )
        ax.set_title(title, loc="left", pad=7)
        ax.set_xlim(0.0, xmax)
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
        ax.xaxis.set_major_locator(MultipleLocator(0.1 if xmax < 0.5 else 0.2))
        ax.grid(
            axis="x",
            color="#D7D7D7",
            linewidth=0.55,
            linestyle=(0, (2, 2)),
        )
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xlabel("Rate")
        add_bar_labels(
            ax,
            [q_container, l_container],
            [q_labels, l_labels],
            padding=2.0,
        )

    axes[0].set_yticks(y_positions)
    axes[0].set_yticklabels([METHOD_LABELS[method] for method in METHOD_ORDER])
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=2,
        frameon=False,
        columnspacing=2.2,
    )
    fig.subplots_adjust(left=0.14, right=0.96, top=0.91, bottom=0.17, wspace=0.38)
    return save_figure(
        fig,
        output_dir,
        "fig_trackb_summary_bars",
        formats,
        dpi,
    )


def main() -> int:
    args = build_parser().parse_args()
    configure_style()

    formats = [item.strip().lower() for item in args.formats.split(",") if item.strip()]
    unsupported = sorted(set(formats) - {"png", "pdf", "svg"})
    if unsupported:
        raise ValueError(f"Unsupported figure formats: {', '.join(unsupported)}")

    qwen_path = Path(args.qwen_csv)
    llama_path = Path(args.llama_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    qwen = build_model_series(
        "qwen25",
        "Qwen2.5-7B-Instruct",
        "Qwen2.5",
        read_trackb_csv(qwen_path, args.arr_column),
    )
    llama = build_model_series(
        "llama31",
        "Llama-3.1-8B-Instruct",
        "Llama3.1",
        read_trackb_csv(llama_path, args.arr_column),
    )
    models = [qwen, llama]

    figures: list[str] = []
    figures.extend(
        plot_two_panel_metric(
            models,
            "asr",
            "Paper-1 four-class ASR",
            (0.0, 0.42),
            0.1,
            output_dir,
            "fig_trackb_asr_cross_model",
            formats,
            args.dpi,
        )
    )
    figures.extend(
        plot_two_panel_metric(
            models,
            "broken_rate",
            "Broken rate",
            (0.0, 1.02),
            0.2,
            output_dir,
            "fig_trackb_broken_cross_model",
            formats,
            args.dpi,
        )
    )
    figures.extend(
        plot_arr_repetition(
            models,
            args.arr_column,
            output_dir,
            formats,
            args.dpi,
        )
    )
    figures.extend(plot_summary_bars(models, output_dir, formats, args.dpi))

    manifest = {
        "qwen_csv": str(qwen_path),
        "llama_csv": str(llama_path),
        "output_dir": str(output_dir),
        "arr_column": args.arr_column,
        "arr_note": (
            "The current mean_arr is the legacy rule and includes the "
            "language-sensitive empty_or_truncated heuristic."
        ),
        "methods": METHOD_ORDER,
        "strengths": EXPECTED_STRENGTHS,
        "sample_sizes": {
            "qwen25": qwen.n_per_condition,
            "llama31": llama.n_per_condition,
        },
        "style_references": [
            {
                "title": (
                    "On Security Weaknesses and Vulnerabilities in Deep "
                    "Learning Systems"
                ),
                "venue": "IEEE TDSC 2025",
                "doi": "10.1109/TDSC.2024.3482707",
                "arxiv": "2406.08688",
            },
            {
                "title": (
                    "Adversarial Challenges in Network Intrusion Detection "
                    "Systems: Research Insights and Future Prospects"
                ),
                "venue": "IEEE TDSC 2025",
                "arxiv": "2409.18736",
            },
        ],
        "figures": figures,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
