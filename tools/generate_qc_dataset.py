"""Synthetic QC-log dataset generator.

Reproduces an *equivalent* dataset to the curated snapshot under ``data/``:
same schema and the same internal identities that ``tools/validate_data.py``
enforces. Given a fixed ``--seed`` the output is deterministic, so the
dataset is reproducible from code without shipping any real data.

The committed ``data/`` directory is a curated snapshot. Running this script
does not overwrite it unless you explicitly point ``--out`` at ``data``; by
default it writes to a throwaway directory that you can validate separately.

Guaranteed invariants (identical to the validator's checks):
  * daily:  reviewed == accepted + dropped
  * daily:  dropped  == sum(the six drop-reason columns)
  * daily:  drop_rate == dropped / reviewed
  * batch:  reviewed == accepted + dropped
  * batch:  main_drop_code exists in the codebook
  * per (work_date, worker_id): sum of batch reviewed/accepted/dropped
            equals the daily row

Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path

# --- Fixed reference tables ------------------------------------------------

WORKERS = ["QC001", "QC002", "QC003", "QC004"]

SHIFTS = {
    "QC001": "09:00-18:00",
    "QC002": "09:00-18:00",
    "QC003": "10:00-19:00",
    "QC004": "10:00-19:00",
}

# Start hour used to lay out batch timestamps within a shift.
START_HOUR = {"QC001": 9, "QC002": 9, "QC003": 10, "QC004": 10}

# Per-worker daily review-volume band. QC001 runs a higher-throughput station.
REVIEW_BAND = {
    "QC001": (9000, 9300),
    "QC002": (7300, 7700),
    "QC003": (7300, 7700),
    "QC004": (7300, 7700),
}

# Drop-reason columns and their fixed share of total drops. These shares are
# the design constants behind the curated snapshot; each reason column is
# derived from the daily drop count via a largest-remainder split so the six
# columns always sum back to ``dropped``.
REASON_FIELDS = [
    "folder_structure_drop",
    "temporal_annotation_drop",
    "duplicate_corrupt_drop",
    "low_visibility_drop",
    "image_content_ambiguity_drop",
    "other_manual_drop",
]
REASON_SHARES = [0.429829, 0.309854, 0.089836, 0.079822, 0.030792, 0.059866]

# Codebook: drop_code -> (category, definition). Also emitted as drop_codebook.csv.
CODEBOOK = [
    ("FOLDER_STRUCTURE", "folder_structure", "폴더 계층, 파일 배치 또는 산출물 규칙 불일치"),
    ("TEMPORAL_ANNOTATION", "temporal_annotation", "객체 시작·종료 시점, 프레임 구간 또는 시계열 연속성 오류"),
    ("DUPLICATE_CORRUPT", "duplicate_corrupt", "중복 파일, 손상 파일, 0KB 또는 읽기 오류"),
    ("LOW_VISIBILITY", "low_visibility", "블러, 과다 노출, 가림 또는 식별 불가 프레임"),
    ("IMAGE_CONTENT_AMBIGUITY", "image_content_ambiguity", "클래스 라벨 정확도 등 라벨링 기준 부적합 이미지"),
    ("METADATA_MISMATCH", "metadata_mismatch", "거리, 환경 또는 클래스 메타데이터와 실제 이미지 불일치"),
    ("OTHER_MANUAL", "other_manual", "상세 사유가 분리되지 않은 기타 수동 검토 드롭"),
]

# main_drop_code candidates for batches (OTHER_MANUAL stays a daily-only residual).
BATCH_CODES = [code for code, _, _ in CODEBOOK if code != "OTHER_MANUAL"]

REVIEW_NOTE = {
    "FOLDER_STRUCTURE": "폴더 구조 또는 산출물 규칙 불일치",
    "TEMPORAL_ANNOTATION": "객체 출현/이탈 구간 불명확 또는 프레임 간 불연속 발생",
    "DUPLICATE_CORRUPT": "중복 또는 손상 이미지 포함",
    "LOW_VISIBILITY": "흐림/저조도/가림 등으로 객체 식별 기준 충족 불가",
    "IMAGE_CONTENT_AMBIGUITY": "객체 클래스 Label 불일치",
    "METADATA_MISMATCH": "거리/환경 메타데이터와 실제 프레임 불일치",
}

DAILY_NOTE = {
    "FOLDER_STRUCTURE": "폴더 구조 오류",
    "TEMPORAL_ANNOTATION": "시계열 어노테이션 오류",
    "DUPLICATE_CORRUPT": "중복 파일 검출",
    "LOW_VISIBILITY": "blur 및 저조도로 객체 식별 불가",
    "IMAGE_CONTENT_AMBIGUITY": "야간 환경으로 객체 식별 기준 충족 불가",
    "METADATA_MISMATCH": "거리·환경 메타와 실제 프레임 불일치",
}

ENVIRONMENTS = ["day_clear", "night_lowlight", "rain_wetroad", "mixed_indoor_outdoor"]
DISTANCE_BUCKETS = ["0-10m", "10-30m", "30m+"]
WORKFLOW_STATUS = ["PASS_TO_NEXT", "REVIEW_COMPLETE", "DROP_AND_ARCHIVE"]

ENV_SCOPE = ["주간, 오전(맑음)", "주간, 오후(맑음)", "주간, 오후(흐림)", "주간, 저녁(맑음)", "야간"]
DISTANCE_SCOPE = {"0-10m": "근거리(0~10m)", "10-30m": "중거리(10~30m)", "30m+": "원거리(30m+)"}

BATCHES_PER_DAY = 4

DAILY_HEADER = [
    "work_date", "worker_id", "shift", "reviewed_images", "accepted_images",
    "dropped_images", "drop_rate", *REASON_FIELDS, "avg_qc_sec_per_image",
    "environment_scope", "distance_scope", "primary_issue_category", "note",
]
ACTION_HEADER = [
    "event_ts", "worker_id", "batch_id", "session_id", "source_path",
    "distance_bucket", "environment_condition", "batch_reviewed",
    "batch_accepted", "batch_dropped", "main_drop_code", "workflow_status",
    "batch_disposition", "avg_qc_sec", "nas_input_path", "nas_output_path",
    "review_note",
]


def largest_remainder(total: int, weights: list[float]) -> list[int]:
    """Split ``total`` into integers proportional to ``weights``.

    Uses the largest-remainder method, so the returned parts always sum
    back to exactly ``total``.
    """
    weight_sum = sum(weights)
    raw = [total * w / weight_sum for w in weights]
    floors = [int(x) for x in raw]
    remainder = total - sum(floors)
    # Hand the leftover units to the parts with the largest fractional loss.
    order = sorted(range(len(weights)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in range(remainder):
        floors[order[i]] += 1
    return floors


def split_reviewed(total: int, parts: int) -> list[int]:
    """Split reviewed volume as evenly as possible, remainder to the first batches."""
    base = total // parts
    rem = total % parts
    return [base + (1 if i < rem else 0) for i in range(parts)]


def build_day(rng: random.Random, work_date: str, worker: str) -> tuple[dict, list[dict]]:
    low, high = REVIEW_BAND[worker]
    reviewed = rng.randint(low, high)
    drop_rate_target = rng.uniform(0.38, 0.46)
    dropped = round(reviewed * drop_rate_target)
    accepted = reviewed - dropped

    reasons = largest_remainder(dropped, REASON_SHARES)

    batch_reviewed = split_reviewed(reviewed, BATCHES_PER_DAY)
    batch_dropped = largest_remainder(dropped, [float(v) for v in batch_reviewed])
    batch_accepted = [r - d for r, d in zip(batch_reviewed, batch_dropped)]

    ww = f"{WORKERS.index(worker) + 1:02d}"
    yyyymmdd = work_date.replace("-", "")
    session_id = f"SES-{yyyymmdd}-{ww}"
    start = datetime.fromisoformat(f"{work_date} {START_HOUR[worker]:02d}:00:00")

    action_rows: list[dict] = []
    batch_codes: list[str] = []
    for b in range(BATCHES_PER_DAY):
        code = rng.choice(BATCH_CODES)
        batch_codes.append(code)
        bucket = rng.choice(DISTANCE_BUCKETS)
        env = rng.choice(ENVIRONMENTS)
        # Timestamps step through the shift with a little jitter.
        ts = start + timedelta(minutes=b * 120 + rng.randint(0, 55))
        batch_id = f"{yyyymmdd}_{ww}_B{b + 1}"
        action_rows.append({
            "event_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "worker_id": worker,
            "batch_id": batch_id,
            "session_id": session_id,
            "source_path": f"/nas/raw/{work_date}/{worker}/{batch_id}",
            "distance_bucket": bucket,
            "environment_condition": env,
            "batch_reviewed": batch_reviewed[b],
            "batch_accepted": batch_accepted[b],
            "batch_dropped": batch_dropped[b],
            "main_drop_code": code,
            "workflow_status": rng.choice(WORKFLOW_STATUS),
            "batch_disposition": "PARTIAL_PASS",
            "avg_qc_sec": round(rng.uniform(1.44, 2.08), 2),
            "nas_input_path": f"/nas/input/{session_id}/{batch_id}",
            "nas_output_path": f"/nas/output/{session_id}/{batch_id}",
            "review_note": REVIEW_NOTE[code],
        })

    # The daily representative reason = the most frequent batch code that day.
    # Iterate over the list (stable order) so ties break deterministically
    # regardless of the process hash seed.
    counts = Counter(batch_codes)
    primary = max(batch_codes, key=lambda code: counts[code])
    daily_row = {
        "work_date": work_date,
        "worker_id": worker,
        "shift": SHIFTS[worker],
        "reviewed_images": reviewed,
        "accepted_images": accepted,
        "dropped_images": dropped,
        "drop_rate": f"{dropped / reviewed:.6f}",
        **{field: value for field, value in zip(REASON_FIELDS, reasons)},
        "avg_qc_sec_per_image": round(rng.uniform(1.60, 1.82), 4),
        "environment_scope": rng.choice(ENV_SCOPE),
        "distance_scope": DISTANCE_SCOPE[rng.choice(DISTANCE_BUCKETS)],
        "primary_issue_category": primary,
        "note": DAILY_NOTE[primary],
    }
    return daily_row, action_rows


def summary_rows(daily: list[dict]) -> list[dict]:
    total_reviewed = sum(int(r["reviewed_images"]) for r in daily)
    total_accepted = sum(int(r["accepted_images"]) for r in daily)
    total_dropped = sum(int(r["dropped_images"]) for r in daily)
    weighted = sum(int(r["reviewed_images"]) * float(r["avg_qc_sec_per_image"]) for r in daily)
    rows = [
        ("total_reviewed_images", total_reviewed, "images", "sum(qc_daily_summary.reviewed_images)"),
        ("total_accepted_images", total_accepted, "images", "sum(qc_daily_summary.accepted_images)"),
        ("total_dropped_images", total_dropped, "images", "sum(qc_daily_summary.dropped_images)"),
        ("overall_drop_rate", round(total_dropped / total_reviewed, 6), "ratio", "total_dropped_images / total_reviewed_images"),
        ("avg_daily_reviewed_per_worker", round(total_reviewed / len(daily), 2), "images", "total_reviewed_images / worker-day rows"),
        ("weighted_avg_qc_sec", round(weighted / total_reviewed, 4), "seconds", "sum(reviewed_images * avg_qc_sec_per_image) / total_reviewed_images"),
    ]
    for field in REASON_FIELDS:
        share = sum(int(r[field]) for r in daily) / total_dropped
        name = field.replace("_drop", "_share_of_drops")
        rows.append((name, round(share, 6), "ratio", f"sum({field}) / total_dropped_images"))
    return [{"metric": m, "value": v, "unit": u, "calculation": c} for m, v, u, c in rows]


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def date_range(start: str, days: int) -> list[str]:
    first = date_cls.fromisoformat(start)
    return [(first + timedelta(days=i)).isoformat() for i in range(days)]


def generate(out: Path, seed: int, start: str, days: int) -> None:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)

    daily: list[dict] = []
    action: list[dict] = []
    for work_date in date_range(start, days):
        for worker in WORKERS:
            daily_row, action_rows = build_day(rng, work_date, worker)
            daily.append(daily_row)
            action.extend(action_rows)

    write_csv(out / "qc_daily_summary.csv", DAILY_HEADER, daily)
    write_csv(out / "qc_action_log.csv", ACTION_HEADER, action)
    write_csv(
        out / "drop_codebook.csv",
        ["drop_code", "category", "definition"],
        [{"drop_code": c, "category": cat, "definition": d} for c, cat, d in CODEBOOK],
    )
    write_csv(
        out / "summary_statistics.csv",
        ["metric", "value", "unit", "calculation"],
        summary_rows(daily),
    )
    print(f"WROTE: {len(daily)} daily rows, {len(action)} action rows -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic QC-log dataset.")
    parser.add_argument("--out", type=Path, default=Path("build/data"),
                        help="output data directory (default: build/data; validate with "
                             "'python tools/validate_data.py build'). Use 'data' to regenerate in place.")
    parser.add_argument("--seed", type=int, default=20250312, help="RNG seed for reproducibility.")
    parser.add_argument("--start", default="2025-03-12", help="first work date (YYYY-MM-DD).")
    parser.add_argument("--days", type=int, default=3, help="number of consecutive work dates.")
    args = parser.parse_args()
    generate(args.out, args.seed, args.start, args.days)


if __name__ == "__main__":
    main()
