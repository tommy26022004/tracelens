"""Score SUS responses exported from Google Forms.

Reads a CSV with one row per respondent. Expects 10 SUS columns in the
canonical Brooke (1986) order; row-matches by column position (so the
exact column header text doesn't matter — what matters is the order
matches the canonical question sequence in `app.evaluation.sus.SUS_QUESTIONS`).

Usage:
    python -m scripts.score_sus path/to/sus_responses.csv

Output:
    - Per-respondent SUS scores + bands
    - Aggregate statistics (mean, median, stddev, min, max)
    - Band distribution
    - PASS/FAIL verdict against the proposal target (> 70 = "Good")
"""

from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

from app.evaluation.sus import SUS_QUESTIONS, score_sus_responses

PROPOSAL_TARGET = 70.0

# Heuristic: SUS questions begin with "I " in the canonical wording.
# Anything starting with "I " is treated as a likely SUS column. We then
# trim to exactly 10 in document order — the order Google Form preserves
# matches our SUS_QUESTIONS order if the form was built per USER_STUDY_KIT.md.
SUS_COL_HINT = "I "


def _locate_sus_columns(header: list[str]) -> list[int]:
    """Return the indices of the 10 SUS columns in `header`.

    Strategy:
    1. If any header equals (case-insensitive, whitespace-normalised) one
       of the canonical SUS questions, use exact matches.
    2. Otherwise, take the first 10 columns whose header starts with "I ".
    """
    canonical_lookup = {
        " ".join(q.lower().split()): q for q in SUS_QUESTIONS
    }
    exact_indices: list[int] = []
    for idx, col in enumerate(header):
        key = " ".join(col.lower().split())
        if key in canonical_lookup:
            exact_indices.append(idx)
    if len(exact_indices) == 10:
        # Reorder by canonical question order to be robust against shuffled headers.
        order = []
        for q in SUS_QUESTIONS:
            target = " ".join(q.lower().split())
            for idx in exact_indices:
                if " ".join(header[idx].lower().split()) == target:
                    order.append(idx)
                    break
        if len(order) == 10:
            return order

    # Fallback: first 10 columns starting with "I ".
    candidates = [
        idx
        for idx, col in enumerate(header)
        if col.strip().startswith(SUS_COL_HINT)
    ]
    if len(candidates) < 10:
        raise ValueError(
            f"Found only {len(candidates)} SUS-looking columns; need 10. "
            f"Check that the CSV column headers match the canonical SUS questions "
            "(see app/evaluation/sus.SUS_QUESTIONS)."
        )
    return candidates[:10]


def _read_responses(csv_path: Path) -> tuple[list[str], list[list[int]]]:
    """Return (respondent_ids, list of 10-int response vectors)."""
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError(f"CSV {csv_path} has no data rows")

    header = rows[0]
    sus_indices = _locate_sus_columns(header)

    # Treat the first column as the timestamp/identifier; if absent, synthesise one.
    respondent_col = 0 if header and "time" in header[0].lower() else None

    respondents: list[str] = []
    responses: list[list[int]] = []
    for line_no, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # skip blank lines
        try:
            vector = [int(row[i].strip()) for i in sus_indices]
        except (IndexError, ValueError) as exc:
            raise ValueError(
                f"Row {line_no}: could not parse 10 SUS responses ({exc}). "
                "Each response must be an integer 1-5."
            ) from exc
        respondent_id = (
            row[respondent_col].strip() if respondent_col is not None else f"R{line_no - 1}"
        )
        respondents.append(respondent_id or f"R{line_no - 1}")
        responses.append(vector)
    return respondents, responses


def _band_distribution(results) -> dict[str, int]:
    bands: dict[str, int] = {}
    for r in results:
        bands[r.band] = bands.get(r.band, 0) + 1
    return bands


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python -m scripts.score_sus <path_to_csv>")
        return 2

    csv_path = Path(argv[1])
    respondents, responses = _read_responses(csv_path)
    results = [
        score_sus_responses(rid, vec)
        for rid, vec in zip(respondents, responses, strict=True)
    ]

    print("=" * 70)
    print(f"SUS SCORING REPORT — {csv_path.name}")
    print(f"N = {len(results)} respondents")
    print("=" * 70)

    print("\nPer-respondent scores:")
    for r in results:
        print(f"  {r.respondent:32}  {r.sus_score:6.2f}  [{r.band}]")

    scores = [r.sus_score for r in results]
    mean = statistics.mean(scores)
    median = statistics.median(scores)
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0.0

    print("\nAggregate statistics:")
    print(f"  Mean:     {mean:6.2f}")
    print(f"  Median:   {median:6.2f}")
    print(f"  StDev:    {stdev:6.2f}")
    print(f"  Min:      {min(scores):6.2f}")
    print(f"  Max:      {max(scores):6.2f}")

    print("\nBand distribution:")
    for band, count in sorted(_band_distribution(results).items()):
        pct = (count / len(results)) * 100
        print(f"  {band:12} {count:3}  ({pct:5.1f}%)")

    print("\nVerdict vs proposal target (> 70):")
    verdict = "PASS" if mean > PROPOSAL_TARGET else "FAIL"
    print(f"  Mean SUS = {mean:.2f}  vs target {PROPOSAL_TARGET}  ->  {verdict}")

    if mean <= 50:
        print(
            "\n  WARNING: Mean SUS <= 50. The system is rated 'Poor'. "
            "Consider iterating UX before submitting the final report."
        )

    print("=" * 70)
    return 0 if mean > PROPOSAL_TARGET else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
