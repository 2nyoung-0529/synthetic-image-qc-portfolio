"""Regenerate the portfolio charts from a QC-log dataset.

Reads ``qc_daily_summary.csv`` from a data directory and writes the three
PNG charts referenced by the README:

  * drop_reason_distribution.png -- total drops per reason
  * daily_review_volume.png      -- reviewed images per work date
  * worker_drop_rate.png         -- overall drop rate per worker

By default it reads the curated ``data/`` snapshot and writes to
``build/charts`` so the committed charts are not clobbered. Pass
``--out charts`` to regenerate them in place.

Requires matplotlib (see requirements.txt).
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: render straight to PNG, no display needed
import matplotlib.pyplot as plt

REASON_FIELDS = [
    "folder_structure_drop",
    "temporal_annotation_drop",
    "duplicate_corrupt_drop",
    "low_visibility_drop",
    "image_content_ambiguity_drop",
    "other_manual_drop",
]
REASON_LABELS = [
    "Folder\nstructure",
    "Temporal\nannotation",
    "Duplicate/\ncorrupt",
    "Low\nvisibility",
    "Content\nambiguity",
    "Other\nmanual",
]
BAR_COLOR = "#4C78A8"


def read_daily(data_dir: Path) -> list[dict[str, str]]:
    with (data_dir / "qc_daily_summary.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def chart_drop_reasons(daily: list[dict], out: Path) -> None:
    totals = [sum(int(row[field]) for row in daily) for field in REASON_FIELDS]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(REASON_LABELS, totals, color=BAR_COLOR)
    ax.set_title("Drop Reason Distribution")
    ax.set_ylabel("Dropped images")
    ax.bar_label(bars, fmt="{:,.0f}", padding=3, fontsize=9)
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def chart_daily_volume(daily: list[dict], out: Path) -> None:
    by_date: dict[str, int] = defaultdict(int)
    for row in daily:
        by_date[row["work_date"]] += int(row["reviewed_images"])
    dates = sorted(by_date)
    values = [by_date[d] for d in dates]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(dates, values, color=BAR_COLOR)
    ax.set_title("Daily Review Volume")
    ax.set_ylabel("Reviewed images")
    ax.bar_label(bars, fmt="{:,.0f}", padding=3, fontsize=9)
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def chart_worker_drop_rate(daily: list[dict], out: Path) -> None:
    reviewed: dict[str, int] = defaultdict(int)
    dropped: dict[str, int] = defaultdict(int)
    for row in daily:
        reviewed[row["worker_id"]] += int(row["reviewed_images"])
        dropped[row["worker_id"]] += int(row["dropped_images"])
    workers = sorted(reviewed)
    rates = [dropped[w] / reviewed[w] for w in workers]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(workers, rates, color=BAR_COLOR)
    ax.set_title("Drop Rate by Worker")
    ax.set_ylabel("Drop rate")
    ax.set_ylim(0, max(rates) * 1.2)
    ax.bar_label(bars, fmt="{:.1%}", padding=3, fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate portfolio charts from the QC dataset.")
    parser.add_argument("--data", type=Path, default=Path("data"), help="data directory (default: data).")
    parser.add_argument("--out", type=Path, default=Path("build/charts"),
                        help="output directory (default: build/charts). Use 'charts' to overwrite in place.")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    daily = read_daily(args.data)
    chart_drop_reasons(daily, args.out / "drop_reason_distribution.png")
    chart_daily_volume(daily, args.out / "daily_review_volume.png")
    chart_worker_drop_rate(daily, args.out / "worker_drop_rate.png")
    print(f"WROTE: 3 charts -> {args.out}")


if __name__ == "__main__":
    main()
