"""Risk-summary schema and prompt construction.

The LLM call lives in the agent's `summarise_node`; this module owns
the shape of the output and the prompt that produces it.

Output contract: every factual claim in `body` must end with one or
more inline `[chunk_id]` citations. The verification step in
`summarise_node` rejects (and re-prompts) any summary that contains
chunk_ids not present in the input.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.ratios.bank_statement_metrics import BankStatementMetrics
from app.ratios.financial_ratios import FinancialRatios
from app.ratios.five_c import FiveCAssessment
from app.validation.checks import Inconsistency

CITATION_RE = re.compile(r"\[([^\[\]]+?)\]")
# Inner separator — LLMs sometimes emit `[id1, id2]` instead of `[id1][id2]`.
CITATION_SPLIT_RE = re.compile(r"\s*[,;]\s*")


class RiskSummary(BaseModel):
    headline: str = Field(
        description="One-sentence overview, ending with one citation"
    )
    body: str = Field(
        description=(
            "Multi-paragraph narrative. EVERY factual claim must end with one or "
            "more inline citations like [doc-1:transaction:5]. No standalone facts."
        )
    )
    recommended_human_checks: list[str] = Field(
        default_factory=list,
        description="Specific items the loan officer should manually review",
    )
    cited_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Deduplicated list of every chunk_id cited in the summary",
    )


def build_prompt(
    metrics: list[BankStatementMetrics],
    inconsistencies: list[Inconsistency],
    five_c: FiveCAssessment,
    allowed_chunk_ids: list[str],
    *,
    financial_ratios: list[FinancialRatios] | None = None,
) -> str:
    financial_ratios = financial_ratios or []
    metrics_block = "\n".join(
        f"- {m.document_id}: net_change=RM{m.net_change}, "
        f"avg_daily_inflow=RM{m.avg_daily_inflow}, deposits={m.deposit_count}, "
        f"closing=RM{m.end_of_period_balance}"
        for m in metrics
    ) or "- (no metrics)"

    ratios_block = "\n".join(
        f"- {r.document_id} FY {r.period_end}: "
        f"Current={r.current_ratio.value}[{r.current_ratio.band.value}], "
        f"D/E={r.debt_to_equity.value}[{r.debt_to_equity.band.value}], "
        f"NPM={r.net_profit_margin.value}[{r.net_profit_margin.band.value}], "
        f"ICR={r.interest_coverage.value}[{r.interest_coverage.band.value}], "
        f"DSR={r.dsr.value}[{r.dsr.band.value}]"
        for r in financial_ratios
    ) or "- (no audited financial ratios)"

    flags_block = "\n".join(
        f"- [{i.severity.value.upper()}] {i.message} "
        f"(citations: {', '.join(i.citations)})"
        for i in inconsistencies
    ) or "- (none detected)"

    five_c_block = "\n".join(
        f"- {dim.name}: {dim.rating.value} — {dim.reasoning} "
        f"(evidence: {', '.join(dim.evidence_chunk_ids) or '—'})"
        for dim in (
            five_c.character,
            five_c.capacity,
            five_c.capital,
            five_c.collateral,
            five_c.conditions,
        )
    )

    return f"""You are drafting an SME credit assessment summary for a Malaysian loan officer
to review. You DO NOT make a credit decision — you summarise findings.

Rules:
1. Every factual claim MUST be followed by one or more citations in square
   brackets, e.g. "Average daily inflow is RM 2,910 [doc-1:summary:0]."
2. Only cite chunk_ids that appear in the allowed list below. Inventing
   chunk_ids is an audit failure.
3. Be specific: name the bank, the period, and the standout figures.
4. End with a brief "recommended human checks" list — items the loan
   officer should personally verify (e.g. missing collateral disclosure).

Allowed chunk_ids (cite only from this list):
{', '.join(allowed_chunk_ids)}

Bank-statement metrics:
{metrics_block}

Financial ratios (from audited statements):
{ratios_block}

Validation findings:
{flags_block}

5C assessment:
{five_c_block}

Return a RiskSummary object."""


def extract_citations(text: str) -> list[str]:
    """Return every chunk_id-like token wrapped in square brackets.

    Handles the LLM's occasional habit of comma-joining citations inside a
    single bracket pair (e.g. `[doc-1:period:0, doc-1:period:1]`).
    """
    found: list[str] = []
    for raw in CITATION_RE.findall(text):
        for token in CITATION_SPLIT_RE.split(raw):
            token = token.strip()
            if token:
                found.append(token)
    return found
