#!/usr/bin/env python
"""Prepare Paper-1 judge-v2 tables and plots from phase-aware summary JSON.

The script expects the JSON produced by scripts/summarize_phase_results.py.
It writes:
  - normalized all-condition CSV
  - Track A fixed-alpha control CSV/Markdown table
  - Track B CSV
  - Track B c-vs-metric plots for ASR, broken rate, ARR, and repetition
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from pathlib import Path
from typing import Any


EXPERIMENT_RE = re.compile(
    r"^stage1_(?P<track>track[AB])_(?P<model>.+?)_"
    r"(?P<method>rogue_v1|no_cache|decode_only|full|first_k|decay)_"
    r"(?P<strength_name>alpha|c)(?P<strength>[0-9]+(?:\.[0-9]+)?)_judge_subset$"
)

METHOD_ORDER = ["rogue_v1", "no_cache", "decode_only", "full", "first_k", "decay"]
TRACK_ORDER = {"trackA": 0, "trackB": 1}
METHOD_COLORS = {
    "rogue_v1": "#2f6fdd",
    "no_cache": "#8a5cf6",
    "decode_only": "#d14b3f",
    "full": "#20845a",
    "first_k": "#e08d1a",
    "decay": "#6f7f8f",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create Paper-1 tables and plots from Qwen judge-v2 summary JSON."
    )
    parser.add_argument(
        "--summary",
        default=(
            "results/stage1_phase_aware/formal/qwen25/judge_summaries/"
            "qwen25_stage1_qwen3_v2_judge_summary.json"
        ),
        help="Input summary JSON from summarize_phase_results.py.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/stage1_phase_aware/formal/qwen25/judge_summaries/qwen25_stage1_qwen3_v2_plots",
        help="Directory for generated CSV/Markdown tables and PNG figures.",
    )
    parser.add_argument(
        "--title-prefix",
        default="Qwen2.5-7B-Instruct judged by Qwen3-8B",
        help="Prefix used in figure titles.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=220,
        help="Figure DPI.",
    )
    parser.add_argument(
        "--formats",
        default="png,svg",
        help="Comma-separated figure formats. png uses matplotlib; svg is dependency-free.",
    )
    return parser


def pct(value: float | None) -> str:
    if value is None:
        return ""
    return f"{100.0 * value:.1f}%"


def metric(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    return float(value) if value is not None else default


def parse_rows(summary_path: Path) -> list[dict[str, Any]]:
    raw_rows = json.loads(summary_path.read_text(encoding="utf-8"))
    parsed: list[dict[str, Any]] = []
    failures: list[str] = []
    for row in raw_rows:
        name = row.get("experiment_name", "")
        match = EXPERIMENT_RE.match(name)
        if not match:
            failures.append(name)
            continue
        info = match.groupdict()
        label_counts = row.get("label_counts", {})
        parsed.append(
            {
                "experiment_name": name,
                "track": info["track"],
                "model": info["model"],
                "method": info["method"],
                "strength_name": info["strength_name"],
                "strength": float(info["strength"]),
                "num_records": int(row.get("num_records", 0)),
                "asr": metric(row, "asr"),
                "broken_rate": metric(row, "broken_rate"),
                "refusal_rate": metric(row, "refusal_rate", metric(row, "harmful_refusal_rate")),
                "safe_rate": metric(row, "safe_rate", metric(row, "harmful_safe_rate")),
                "rogue_compatible_asr": metric(row, "rogue_compatible_asr"),
                "short_response_rule_rate": metric(row, "short_response_rule_rate"),
                "mean_arr": metric(row, "mean_arr"),
                "mean_repetition_rate": metric(row, "mean_repetition_rate"),
                "empty_or_truncated_rate": metric(row, "empty_or_truncated_rate"),
                "language_switch_rate": metric(row, "language_switch_rate"),
                "avg_output_tokens": metric(row, "avg_output_tokens"),
                "avg_output_chars": metric(row, "avg_output_chars"),
                "unsafe_count": int(label_counts.get("unsafe", 0)),
                "broken_count": int(label_counts.get("broken", 0)),
                "refusal_count": int(label_counts.get("refusal", 0)),
                "safe_count": int(label_counts.get("safe", 0)),
            }
        )
    if failures:
        joined = "\n  ".join(failures)
        raise ValueError(f"Could not parse experiment_name for {len(failures)} rows:\n  {joined}")
    parsed.sort(
        key=lambda r: (
            TRACK_ORDER.get(r["track"], 99),
            METHOD_ORDER.index(r["method"]) if r["method"] in METHOD_ORDER else 99,
            r["strength"],
        )
    )
    return parsed


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_tracka_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "| method | alpha | n | ASR | broken | refusal | safe | ARR | repetition |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {method} | {strength:.2f} | {num_records} | {asr} | {broken} | {refusal} | "
            "{safe} | {arr} | {rep} |".format(
                method=row["method"],
                strength=row["strength"],
                num_records=row["num_records"],
                asr=pct(row["asr"]),
                broken=pct(row["broken_rate"]),
                refusal=pct(row["refusal_rate"]),
                safe=pct(row["safe_rate"]),
                arr=pct(row["mean_arr"]),
                rep=pct(row["mean_repetition_rate"]),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        return None
    return plt


def grouped_by_method(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {method: [] for method in METHOD_ORDER}
    for row in rows:
        grouped.setdefault(row["method"], []).append(row)
    for values in grouped.values():
        values.sort(key=lambda row: row["strength"])
    return grouped


def plot_single_metric_png(
    rows: list[dict[str, Any]],
    output_path: Path,
    metric_key: str,
    ylabel: str,
    title: str,
    dpi: int,
) -> bool:
    plt = get_matplotlib()
    if plt is None:
        return False
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for method, values in grouped_by_method(rows).items():
        if not values:
            continue
        ax.plot(
            [row["strength"] for row in values],
            [row[metric_key] for row in values],
            marker="o",
            linewidth=2.0,
            label=method,
        )
    ax.set_title(title)
    ax.set_xlabel("Rogue-calibrated strength c")
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
    return True


def plot_arr_repetition_png(
    rows: list[dict[str, Any]],
    output_path: Path,
    title_prefix: str,
    dpi: int,
) -> bool:
    plt = get_matplotlib()
    if plt is None:
        return False
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4), sharex=True)
    for ax, metric_key, ylabel, subtitle in [
        (axes[0], "mean_arr", "ARR", "c vs ARR"),
        (axes[1], "mean_repetition_rate", "Repetition rate", "c vs repetition"),
    ]:
        for method, values in grouped_by_method(rows).items():
            if not values:
                continue
            ax.plot(
                [row["strength"] for row in values],
                [row[metric_key] for row in values],
                marker="o",
                linewidth=2.0,
                label=method,
            )
        ax.set_title(subtitle)
        ax.set_xlabel("Rogue-calibrated strength c")
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)
    axes[1].legend(frameon=False)
    fig.suptitle(f"{title_prefix}: Track B corruption diagnostics", y=1.02)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return True


def svg_polyline(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def plot_single_metric_svg(
    rows: list[dict[str, Any]],
    output_path: Path,
    metric_key: str,
    ylabel: str,
    title: str,
) -> None:
    width, height = 920, 560
    left, right, top, bottom = 88, 210, 68, 74
    plot_w = width - left - right
    plot_h = height - top - bottom
    grouped = grouped_by_method(rows)
    xs = [row["strength"] for row in rows]
    ys = [row[metric_key] for row in rows]
    x_min, x_max = min(xs), max(xs)
    y_max = max(max(ys) * 1.12, 0.05)
    colors = METHOD_COLORS

    def sx(x: float) -> float:
        return left + (x - x_min) / (x_max - x_min) * plot_w

    def sy(y: float) -> float:
        return top + plot_h - y / y_max * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,Helvetica,sans-serif;fill:#202124} .tick{font-size:13px;fill:#5f6368} .title{font-size:20px;font-weight:700} .label{font-size:15px;font-weight:600}</style>",
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="34" class="title">{html.escape(title)}</text>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333" stroke-width="1.2"/>',
    ]
    for i in range(6):
        y_val = y_max * i / 5
        y = sy(y_val)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#e8eaed"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="tick">{y_val:.2f}</text>')
    for x_val in sorted(set(xs)):
        x = sx(x_val)
        parts.append(f'<line x1="{x:.1f}" y1="{top + plot_h}" x2="{x:.1f}" y2="{top + plot_h + 6}" stroke="#333"/>')
        parts.append(f'<text x="{x:.1f}" y="{top + plot_h + 26}" text-anchor="middle" class="tick">{x_val:.2f}</text>')
    for method, values in grouped.items():
        if not values:
            continue
        points = [(sx(row["strength"]), sy(row[metric_key])) for row in values]
        color = colors.get(method, "#444")
        parts.append(f'<polyline points="{svg_polyline(points)}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x, y in points:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.2" fill="{color}"/>')
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 20}" text-anchor="middle" class="label">Rogue-calibrated strength c</text>')
    parts.append(f'<text x="22" y="{top + plot_h / 2:.1f}" text-anchor="middle" class="label" transform="rotate(-90 22 {top + plot_h / 2:.1f})">{html.escape(ylabel)}</text>')
    legend_x, legend_y = left + plot_w + 34, top + 20
    for idx, method in enumerate(METHOD_ORDER):
        y = legend_y + idx * 28
        color = colors.get(method, "#444")
        parts.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 28}" y2="{y}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<circle cx="{legend_x + 14}" cy="{y}" r="4" fill="{color}"/>')
        parts.append(f'<text x="{legend_x + 38}" y="{y + 5}" class="tick">{method}</text>')
    parts.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def plot_arr_repetition_svg(rows: list[dict[str, Any]], output_path: Path, title_prefix: str) -> None:
    width, height = 1120, 520
    panel_w, panel_h = 430, 330
    panels = [
        {"x0": 82, "y0": 92, "metric": "mean_arr", "title": "c vs ARR", "ylabel": "ARR"},
        {
            "x0": 612,
            "y0": 92,
            "metric": "mean_repetition_rate",
            "title": "c vs repetition",
            "ylabel": "Repetition rate",
        },
    ]
    grouped = grouped_by_method(rows)
    xs = [row["strength"] for row in rows]
    x_min, x_max = min(xs), max(xs)
    colors = METHOD_COLORS

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,Helvetica,sans-serif;fill:#202124} .tick{font-size:13px;fill:#5f6368} .title{font-size:20px;font-weight:700} .subtitle{font-size:16px;font-weight:700} .label{font-size:14px;font-weight:600}</style>",
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="82" y="38" class="title">{html.escape(title_prefix)}: Track B corruption diagnostics</text>',
    ]

    for panel in panels:
        x0, y0 = panel["x0"], panel["y0"]
        metric_key = panel["metric"]
        ys = [row[metric_key] for row in rows]
        y_max = max(max(ys) * 1.12, 0.05)

        def sx(x: float) -> float:
            return x0 + (x - x_min) / (x_max - x_min) * panel_w

        def sy(y: float) -> float:
            return y0 + panel_h - y / y_max * panel_h

        parts.append(f'<text x="{x0}" y="{y0 - 28}" class="subtitle">{html.escape(panel["title"])}</text>')
        parts.append(f'<line x1="{x0}" y1="{y0 + panel_h}" x2="{x0 + panel_w}" y2="{y0 + panel_h}" stroke="#333" stroke-width="1.2"/>')
        parts.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + panel_h}" stroke="#333" stroke-width="1.2"/>')
        for i in range(5):
            y_val = y_max * i / 4
            y = sy(y_val)
            parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + panel_w}" y2="{y:.1f}" stroke="#e8eaed"/>')
            parts.append(f'<text x="{x0 - 10}" y="{y + 4:.1f}" text-anchor="end" class="tick">{y_val:.2f}</text>')
        for x_val in sorted(set(xs)):
            x = sx(x_val)
            parts.append(f'<line x1="{x:.1f}" y1="{y0 + panel_h}" x2="{x:.1f}" y2="{y0 + panel_h + 6}" stroke="#333"/>')
            parts.append(f'<text x="{x:.1f}" y="{y0 + panel_h + 25}" text-anchor="middle" class="tick">{x_val:.2f}</text>')
        for method, values in grouped.items():
            if not values:
                continue
            points = [(sx(row["strength"]), sy(row[metric_key])) for row in values]
            color = colors.get(method, "#444")
            parts.append(f'<polyline points="{svg_polyline(points)}" fill="none" stroke="{color}" stroke-width="3"/>')
            for x, y in points:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.2" fill="{color}"/>')
        parts.append(f'<text x="{x0 + panel_w / 2:.1f}" y="{height - 36}" text-anchor="middle" class="label">Rogue-calibrated strength c</text>')
        parts.append(f'<text x="{x0 - 56}" y="{y0 + panel_h / 2:.1f}" text-anchor="middle" class="label" transform="rotate(-90 {x0 - 56} {y0 + panel_h / 2:.1f})">{html.escape(panel["ylabel"])}</text>')

    legend_x, legend_y = 948, 96
    for idx, method in enumerate(METHOD_ORDER):
        y = legend_y + idx * 28
        color = colors.get(method, "#444")
        parts.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 28}" y2="{y}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<circle cx="{legend_x + 14}" cy="{y}" r="4" fill="{color}"/>')
        parts.append(f'<text x="{legend_x + 38}" y="{y + 5}" class="tick">{method}</text>')
    parts.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    summary_path = Path(args.summary)
    output_dir = Path(args.output_dir)
    table_dir = output_dir / "tables"
    figure_dir = output_dir / "figures"
    formats = {item.strip().lower() for item in args.formats.split(",") if item.strip()}

    rows = parse_rows(summary_path)
    track_a = [row for row in rows if row["track"] == "trackA"]
    track_b = [row for row in rows if row["track"] == "trackB"]

    write_csv(table_dir / "all_conditions.csv", rows)
    write_csv(table_dir / "trackA_fixed_alpha_control.csv", track_a)
    write_csv(table_dir / "trackB_curves.csv", track_b)
    write_tracka_markdown(table_dir / "trackA_fixed_alpha_control.md", track_a)

    figures: list[str] = []
    warnings: list[str] = []
    if "png" in formats:
        made_png = True
        made_png &= plot_single_metric_png(
            track_b,
            figure_dir / "trackB_c_vs_asr.png",
            "asr",
            "ASR (paper-1 four-class unsafe rate)",
            f"{args.title_prefix}: Track B c vs ASR",
            args.dpi,
        )
        made_png &= plot_single_metric_png(
            track_b,
            figure_dir / "trackB_c_vs_broken_rate.png",
            "broken_rate",
            "Broken rate",
            f"{args.title_prefix}: Track B c vs broken rate",
            args.dpi,
        )
        made_png &= plot_arr_repetition_png(
            track_b,
            figure_dir / "trackB_c_vs_arr_repetition.png",
            args.title_prefix,
            args.dpi,
        )
        if made_png:
            figures.extend(
                [
                    str(figure_dir / "trackB_c_vs_asr.png"),
                    str(figure_dir / "trackB_c_vs_broken_rate.png"),
                    str(figure_dir / "trackB_c_vs_arr_repetition.png"),
                ]
            )
        else:
            warnings.append("matplotlib is not available; skipped PNG output.")
    if "svg" in formats:
        plot_single_metric_svg(
            track_b,
            figure_dir / "trackB_c_vs_asr.svg",
            "asr",
            "ASR (paper-1 four-class unsafe rate)",
            f"{args.title_prefix}: Track B c vs ASR",
        )
        plot_single_metric_svg(
            track_b,
            figure_dir / "trackB_c_vs_broken_rate.svg",
            "broken_rate",
            "Broken rate",
            f"{args.title_prefix}: Track B c vs broken rate",
        )
        plot_arr_repetition_svg(
            track_b,
            figure_dir / "trackB_c_vs_arr_repetition.svg",
            args.title_prefix,
        )
        figures.extend(
            [
                str(figure_dir / "trackB_c_vs_asr.svg"),
                str(figure_dir / "trackB_c_vs_broken_rate.svg"),
                str(figure_dir / "trackB_c_vs_arr_repetition.svg"),
            ]
        )

    manifest = {
        "summary": str(summary_path),
        "output_dir": str(output_dir),
        "num_rows": len(rows),
        "trackA_rows": len(track_a),
        "trackB_rows": len(track_b),
        "tables": [
            str(table_dir / "all_conditions.csv"),
            str(table_dir / "trackA_fixed_alpha_control.csv"),
            str(table_dir / "trackA_fixed_alpha_control.md"),
            str(table_dir / "trackB_curves.csv"),
        ],
        "figures": figures,
        "warnings": warnings,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
