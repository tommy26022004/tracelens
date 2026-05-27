"""FYP evaluation harness.

Four metrics derived directly from the proposal (section 12):

- `extraction_accuracy` — extracted fields vs ground truth
- `faithfulness` — citation validity (no hallucinated chunk_ids)
- `latency` — wall-clock time per node and end-to-end
- `usability` — SUS questionnaire scoring helper

Each metric is a pure function — feeds the unified runner in
`scripts/evaluate.py` which assembles all of them into a single
report.
"""

from app.evaluation.extraction_accuracy import (
    ExtractionAccuracyReport,
    score_audited_financials,
    score_bank_statement,
    score_ssm_registration,
    score_tax_return,
)
from app.evaluation.faithfulness import FaithfulnessReport, score_faithfulness
from app.evaluation.latency import LatencyReport, time_graph_run
from app.evaluation.sus import SUS_QUESTIONS, score_sus_responses

__all__ = [
    "ExtractionAccuracyReport",
    "FaithfulnessReport",
    "LatencyReport",
    "SUS_QUESTIONS",
    "score_audited_financials",
    "score_bank_statement",
    "score_faithfulness",
    "score_ssm_registration",
    "score_sus_responses",
    "score_tax_return",
    "time_graph_run",
]
