"""Evaluation artefacts are reproducible and reject incomplete human data."""

import csv

import pytest

from scripts.evaluate_robustness import run
from scripts.score_usability import score_file


def test_robustness_comparison_and_scan_limitation() -> None:
    report = run()
    scenarios = {item["scenario"]: item for item in report["results"]}
    assert scenarios["original"]["scores"]["current"]["accuracy"] == 1
    assert scenarios["minor_jitter"]["scores"]["previous"]["accuracy"] == 0
    assert scenarios["minor_jitter"]["scores"]["current"]["accuracy"] == 1
    assert scenarios["image_only_scan"]["needs_ocr_detected"]
    assert scenarios["image_only_scan"]["unsupported_extraction_rejected"]


def test_usability_scorer_requires_real_complete_records(tmp_path) -> None:
    path = tmp_path / "responses.csv"
    fields = ["participant_id", "role"]
    for index in range(1, 6):
        fields.extend([f"task{index}_completed", f"task{index}_seconds"])
    fields.extend(f"sus{index}" for index in range(1, 11))
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for index in range(5):
            row = {"participant_id": f"P{index + 1:02d}", "role": "test fixture"}
            row.update({f"task{task}_completed": "yes" for task in range(1, 6)})
            row.update({f"task{task}_seconds": "30" for task in range(1, 6)})
            row.update({f"sus{item}": "4" if item % 2 else "2" for item in range(1, 11)})
            writer.writerow(row)
    report = score_file(path)
    assert report["participant_count"] == 5
    assert report["mean_sus"] == 75
    assert report["task_completion_rate"] == [1, 1, 1, 1, 1]
    path.write_text("participant_id,role\nP01,student\n", encoding="utf-8")
    with pytest.raises(ValueError, match="At least five"):
        score_file(path)
