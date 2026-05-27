"""System Usability Scale (SUS) — 10-question questionnaire + scoring.

SUS is the standard usability instrument (Brooke 1986). The 10 items
alternate positive/negative; the scoring formula converts five-point
Likert responses into a 0-100 number where >70 is "good" (the proposal
target).

This module is paperwork-shaped on purpose: we ship the question text
and the scoring rule, and let the dashboard or evaluation script
collect responses out-of-band.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

SUS_QUESTIONS: list[str] = [
    "I think that I would like to use this system frequently.",
    "I found the system unnecessarily complex.",
    "I thought the system was easy to use.",
    "I think that I would need the support of a technical person to use this system.",
    "I found the various functions in this system were well integrated.",
    "I thought there was too much inconsistency in this system.",
    "I would imagine that most people would learn to use this system very quickly.",
    "I found the system very cumbersome to use.",
    "I felt very confident using the system.",
    "I needed to learn a lot of things before I could get going with this system.",
]

# Positive-worded items (0-indexed): odd questions in 1-indexed SUS = 1,3,5,7,9
POSITIVE_INDICES = {0, 2, 4, 6, 8}


class SUSResult(BaseModel):
    respondent: str
    raw_responses: list[int] = Field(description="One score per question, 1-5 Likert")
    sus_score: float = Field(description="0-100; >70 'Good', >85 'Excellent'")
    band: str


def _band(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "OK"
    return "Poor"


def score_sus_responses(respondent: str, responses: list[int]) -> SUSResult:
    """Apply the standard SUS scoring rule.

    Each positive question: contribution = response − 1.
    Each negative question: contribution = 5 − response.
    Sum × 2.5 → 0-100 score.
    """
    if len(responses) != len(SUS_QUESTIONS):
        raise ValueError(f"Expected {len(SUS_QUESTIONS)} responses, got {len(responses)}")
    for r in responses:
        if not 1 <= r <= 5:
            raise ValueError(f"Response {r} outside 1-5 Likert range")

    contributions = []
    for idx, response in enumerate(responses):
        if idx in POSITIVE_INDICES:
            contributions.append(response - 1)
        else:
            contributions.append(5 - response)

    raw = sum(contributions) * 2.5
    return SUSResult(
        respondent=respondent,
        raw_responses=responses,
        sus_score=raw,
        band=_band(raw),
    )
