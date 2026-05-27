"""Source-traced risk summary generation (Step 6 of agent workflow).

The explainability layer turns the structured outputs of earlier nodes
(metrics, inconsistencies, 5C assessment) into a natural-language
summary in which every claim carries an inline `[chunk_id]` citation
the dashboard can resolve back to a specific PDF row.
"""

from app.explainability.summary import RiskSummary, build_prompt

__all__ = ["RiskSummary", "build_prompt"]
