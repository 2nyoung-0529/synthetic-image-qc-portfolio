from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main(root: Path) -> None:
    data = root / "data"
    daily = rows(data / "qc_daily_summary.csv")
    action = rows(data / "qc_action_log.csv")
    codebook = rows(data / "drop_codebook.csv")
    reason_fields = [
        "folder_structure_drop",
        "temporal_annotation_drop",
        "duplicate_corrupt_drop",
        "low_visibility_drop",
        "image_content_ambiguity_drop",
        "other_manual_drop",
    ]
    for row in daily:
        reviewed = int(row["reviewed_images"])
        accepted = int(row["accepted_images"])
        dropped = int(row["dropped_images"])
        assert reviewed == accepted + dropped, f"daily decision mismatch: {row}"
        assert dropped == sum(int(row[field]) for field in reason_fields), f"daily reason mismatch: {row}"
        assert abs(float(row["drop_rate"]) - dropped / reviewed) < 0.000001, f"drop rate mismatch: {row}"

    grouped = defaultdict(lambda: [0, 0, 0])
    for row in action:
        reviewed = int(row["batch_reviewed"])
        accepted = int(row["batch_accepted"])
        dropped = int(row["batch_dropped"])
        assert reviewed == accepted + dropped, f"batch decision mismatch: {row}"
        assert row["main_drop_code"] in {item["drop_code"] for item in codebook}, f"unknown code: {row}"
        key = (row["event_ts"][:10], row["worker_id"])
        for index, value in enumerate((reviewed, accepted, dropped)):
            grouped[key][index] += value

    for row in daily:
        key = (row["work_date"], row["worker_id"])
        expected = [int(row[name]) for name in ("reviewed_images", "accepted_images", "dropped_images")]
        assert grouped[key] == expected, f"daily/action mismatch: {key}: {grouped[key]} != {expected}"

    print(f"PASS: {len(daily)} daily rows, {len(action)} action rows, all reconciliation checks succeeded")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
