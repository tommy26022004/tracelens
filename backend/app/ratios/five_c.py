"""5C credit-assessment schema + prompt construction.

The actual LLM call is performed by the agent's `assess_5c_node`. This
module owns:
- the schema the LLM must produce (one `Dimension` block per C),
- prompt construction that bundles the deterministic evidence so the
  LLM doesn't have to re-extract figures.

Keeping prompts in code (not strings in `nodes.py`) makes them
versionable and testable independently of LangGraph.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.ratios.bank_statement_metrics import BankStatementMetrics
from app.validation.checks import Inconsistency


class Rating(str, Enum):
    STRONG = "strong"
    ADEQUATE = "adequate"
    WEAK = "weak"
    INSUFFICIENT_DATA = "insufficient_data"


class Dimension(BaseModel):
    name: str = Field(description="Character | Capacity | Capital | Collateral | Conditions")
    rating: Rating
    reasoning: str = Field(
        description="2-3 sentences explaining the rating in plain English"
    )
    evidence_chunk_ids: list[str] = Field(
        default_factory=list,
        description="chunk_ids from the ingested documents supporting this rating",
    )
    flags_for_human_review: list[str] = Field(
        default_factory=list,
        description="Specific items the loan officer should double-check",
    )


class FiveCAssessment(BaseModel):
    character: Dimension
    capacity: Dimension
    capital: Dimension
    collateral: Dimension
    conditions: Dimension


_DIMENSION_GUIDANCE: dict[str, str] = {
    "Character": (
        "Look at deposit regularity, recurring counterparties, and the presence "
        "of tax/EPF/SOCSO outflows as proxies for business discipline."
    ),
    "Capacity": (
        "Use avg_daily_inflow, net_change, and largest_credit to judge whether "
        "current cash flow can service additional debt."
    ),
    "Capital": (
        "Without audited financials, capital cannot be assessed quantitatively. "
        "Rate as INSUFFICIENT_DATA unless evidence is exceptionally strong."
    ),
    "Collateral": (
        "Bank statements do not disclose collateral. Rate INSUFFICIENT_DATA and "
        "flag the missing CTOS / asset schedule for human follow-up."
    ),
    "Conditions": (
        "Comment only on what's visible in the statement: counterparty mix, "
        "industry signals from descriptions (e.g. PEPPOL, LHDN tax, supplier names)."
    ),
}


def build_prompt(
    metrics: list[BankStatementMetrics],
    inconsistencies: list[Inconsistency],
) -> str:
    """Compose a single prompt for all 5 dimensions.

    The deterministic evidence (metrics + inconsistencies) is pasted in
    full so the LLM never has to re-derive numbers from chunks.
    """
    metrics_block = "\n".join(
        f"- {m.document_id}: period_days={m.period_days}, "
        f"transactions={m.transaction_count}, "
        f"net_change=RM{m.net_change}, "
        f"avg_daily_inflow=RM{m.avg_daily_inflow}, "
        f"avg_daily_outflow=RM{m.avg_daily_outflow}, "
        f"deposit_count={m.deposit_count}, withdrawal_count={m.withdrawal_count}, "
        f"closing_balance=RM{m.end_of_period_balance}, "
        f"balance_volatility=RM{m.balance_volatility}"
        for m in metrics
    ) or "- (no metrics)"

    inconsistencies_block = "\n".join(
        f"- [{i.severity.value.upper()}] {i.code}: {i.message} "
        f"(citations: {', '.join(i.citations) or '—'})"
        for i in inconsistencies
    ) or "- (none detected)"

    guidance_block = "\n".join(
        f"- {name}: {guidance}" for name, guidance in _DIMENSION_GUIDANCE.items()
    )

    return f"""You are assisting a Malaysian loan officer assess an SME credit application.
Produce a 5C assessment (Character, Capacity, Capital, Collateral, Conditions).

You MUST:
1. Base every claim on the evidence provided below.
2. Cite specific chunk_ids in `evidence_chunk_ids` for each dimension.
3. Rate `insufficient_data` rather than guess when bank statements alone cannot
   support the dimension (especially Capital and Collateral — those need audited
   financials and asset schedules respectively).
4. Never assert a credit decision. You provide assessment input only.

Per-dimension guidance:
{guidance_block}

Evidence — deterministic metrics:
{metrics_block}

Evidence — validation findings:
{inconsistencies_block}

Return a FiveCAssessment object."""
