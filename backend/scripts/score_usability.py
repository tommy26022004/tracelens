"""Score actual participant records; reject missing or invented inputs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from app.evaluation.sus import score_sus_responses


def score_file(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))
    if len(rows) < 5:
        raise ValueError("At least five completed participant responses are required")
    seen = set()
    participants = []
    for row in rows:
        identifier = row["participant_id"].strip()
        role = row["role"].strip()
        if not identifier or identifier in seen or not role:
            raise ValueError("Participant IDs must be unique and roles must be recorded")
        seen.add(identifier)
        responses = [int(row[f"sus{index}"]) for index in range(1, 11)]
        sus = score_sus_responses(identifier, responses)
        tasks = []
        for index in range(1, 6):
            completed = row[f"task{index}_completed"].strip().lower()
            if completed not in {"yes", "no"}:
                raise ValueError(f"{identifier}: task {index} must be yes or no")
            seconds = float(row[f"task{index}_seconds"])
            if seconds < 0:
                raise ValueError("Task duration cannot be negative")
            tasks.append({"completed": completed == "yes", "seconds": seconds})
        participants.append({"id": identifier, "role": role, "sus_score": sus.sus_score, "tasks": tasks})
    return {
        "participants": participants,
        "participant_count": len(participants),
        "mean_sus": round(statistics.mean(item["sus_score"] for item in participants), 2),
        "task_completion_rate": [
            round(sum(item["tasks"][index]["completed"] for item in participants) / len(participants), 4)
            for index in range(5)
        ],
        "sample_limitation": "Report participant roles; a convenience sample is not evidence of loan-officer usability.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("responses", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    try:
        report = score_file(args.responses)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    output = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
