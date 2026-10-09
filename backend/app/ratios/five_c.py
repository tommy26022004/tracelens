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
from app.ratios.financial_ratios import FinancialRatios
from app.validation.checks import Inconsistency


class Rating(str, Enum):
    STRONG = "strong"
    ADEQUATE = "adequate"
    WEAK = "weak"
    INSUFFICIENT_DATA = "insufficient_data"


class Dimension(BaseModel):
    name: str = Field(description="Character | Capacity | Capital | Collateral | Conditions")
    rating: Rating
    reasoning: str = Field(description="2-3 sentences explaining the rating in plain English")
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
        "Describe observed inflows and outflows, but do not treat account credits "
        "as profit or infer repayment ability without debt obligations. Missing "
        "documents or limited coverage alone never justify a weak rating. "
        "Use insufficient_data when repayment evidence is incomplete. Audited cash from "
        "operations, EBIT and interest coverage are relevant partial evidence even without "
        "bank statements. Acknowledge these facts rather than claiming no evidence exists."
    ),
    "Capital": (
        "If audited financials are present, use Debt-to-Equity and Total Equity to "
        "judge the capital cushion. Otherwise rate as INSUFFICIENT_DATA."
    ),
    "Collateral": (
        "Inspect retrieved facility/security evidence for collateral disclosures. "
        "Bank statements alone cannot establish collateral. If insufficient, rate "
        "INSUFFICIENT_DATA and request the relevant security or asset documents."
    ),
    "Conditions": (
        "Use retrieved management accounts and supporting evidence for documented "
        "operating risks. Keep forecasts separate from historical actuals; do not "
        "infer market stability from regular banking transactions alone."
    ),
}


def build_prompt(
    metrics: list[BankStatementMetrics],
    inconsistencies: list[Inconsistency],
    *,
    financial_ratios: list[FinancialRatios] | None = None,
    allowed_chunk_ids: list[str] | None = None,
    package_evidence: str = "",
    retrieved_evidence: str = "",
) -> str:
    """Compose a single prompt for all 5 dimensions.

    The deterministic evidence (metrics + inconsistencies + financial
    ratios) is pasted in full so the LLM never has to re-derive numbers
    from chunks.
    """
    financial_ratios = financial_ratios or []
    allowed_chunk_ids = allowed_chunk_ids or []
    prompt_metrics = _representative_metrics(metrics)
    metrics_block = (
        "\n".join(
            f"- {m.document_id} (source_chunk_id={m.document_id}:summary:0): "
            f"days={m.period_days}, txns={m.transaction_count}, "
            f"credits=RM{m.total_credits}, debits=RM{m.total_debits}, "
            f"net=RM{m.net_change}, reconciliation_diff="
            f"RM{m.net_change - (m.total_credits - m.total_debits)}, "
            f"daily_inflow=RM{m.avg_daily_inflow}, closing=RM{m.end_of_period_balance}"
            for m in prompt_metrics
        )
        or "- (no metrics)"
    )
    if len(prompt_metrics) < len(metrics):
        metrics_block += (
            f"\n- ({len(metrics) - len(prompt_metrics)} additional statements omitted from "
            "the prompt; use package cash-flow aggregates for package-level claims)"
        )

    ratios_block = (
        "\n".join(
            "\n".join(
                [
                    f"- {r.document_id} (FY end {r.period_end}; "
                    f"source_chunk_id={r.document_id}:period:0):",
                    f"    Current Ratio: {r.current_ratio.value} [{r.current_ratio.band.value}]",
                    f"    Debt-to-Equity: {r.debt_to_equity.value} [{r.debt_to_equity.band.value}]",
                    f"    Net Profit Margin: {r.net_profit_margin.value} [{r.net_profit_margin.band.value}]",
                    f"    Interest Coverage: {r.interest_coverage.value} [{r.interest_coverage.band.value}]",
                    f"    DSR: {r.dsr.value} [{r.dsr.band.value}] (unavailable without verified repayments)",
                    "    Key inputs (RM): "
                    + ", ".join(
                        f"{name}={r.inputs.get(name)}"
                        for name in (
                            "current_assets",
                            "current_liabilities",
                            "non_current_liabilities",
                            "total_equity",
                            "revenue",
                            "net_profit",
                            "ebit",
                            "interest_expense",
                            "cash_from_operations",
                        )
                    ),
                ]
            )
            for r in financial_ratios
        )
        or "- (no audited financial ratios — Capital/Capacity assessment is limited)"
    )

    inconsistencies_block = (
        "\n".join(
            f"- [{i.severity.value.upper()}] {i.code}: {i.message} "
            f"(citations: {', '.join(i.citations) or '—'})"
            for i in inconsistencies
        )
        or "- (none detected)"
    )

    guidance_block = "\n".join(
        f"- {name}: {guidance}" for name, guidance in _DIMENSION_GUIDANCE.items()
    )
    allowed_block = ", ".join(allowed_chunk_ids) or "(none)"

    return f"""You are assisting a Malaysian loan officer assess an SME credit application.
Produce a 5C assessment (Character, Capacity, Capital, Collateral, Conditions).

You MUST:
1. Base every claim on the evidence provided below.
2. Cite specific chunk_ids in `evidence_chunk_ids` for each dimension.
3. Rate `insufficient_data` rather than guess when bank statements alone cannot
   support the dimension (especially Capital and Collateral — those need audited
   financials and asset schedules respectively).
4. Never assert a credit decision. You provide assessment input only.
5. Use only exact chunk_ids from the allowed list. Do not create metric names,
   ratio names, document ids, or other synthetic identifiers as citations.

Allowed chunk_ids:
{allowed_block}

Per-dimension guidance:
{guidance_block}

Evidence — deterministic metrics:
{metrics_block}

Evidence — financial ratios from audited statements:
{ratios_block}

Evidence — validation findings:
{inconsistencies_block}

Evidence — package totals, coverage and document identity:
{package_evidence}

{retrieved_evidence}

Use the provided package totals for package-level claims. Address all material
validation findings, including missing documents, missing months and duplicate
uploads. A package-level absence check comes from the inventory, not a PDF page;
do not invent a document citation for missing evidence.

Return a FiveCAssessment object."""


def _representative_metrics(
    metrics: list[BankStatementMetrics], limit: int = 5
) -> list[BankStatementMetrics]:
    if len(metrics) <= limit:
        return metrics
    indexes = {round(position * (len(metrics) - 1) / (limit - 1)) for position in range(limit)}
    return [metric for index, metric in enumerate(metrics) if index in indexes]
