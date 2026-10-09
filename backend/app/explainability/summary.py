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
NON_CITATION_LABELS = {"INFO", "WARNING", "CRITICAL"}
INVENTORY_CLAIM_RE = re.compile(
    r"\b(?:document coverage gaps?|missing (?:bank statements?|months?|core documents?|documents?)|incomplete package)\b",
    re.IGNORECASE,
)
TRAILING_CITATIONS_RE = re.compile(r"(?P<citations>(?:\s*\[[^\[\]]+\])+)(?P<period>[.!?])\s*$")
CONTRAST_RE = re.compile(r",?\s+(?:but|while|although)\s+", re.IGNORECASE)


class RiskSummary(BaseModel):
    headline: str = Field(description="One-sentence overview, ending with one citation")
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
    package_evidence: str = "",
    retrieved_evidence: str = "",
) -> str:
    financial_ratios = financial_ratios or []
    prompt_metrics = _representative_metrics(metrics)
    metrics_block = (
        "\n".join(
            f"- {m.document_id}: credits=RM{m.total_credits}, debits=RM{m.total_debits}, "
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
            "the prompt; summarise package cash-flow aggregates instead of monthly detail)"
        )

    ratios_block = (
        "\n".join(
            f"- {r.document_id} FY {r.period_end}: "
            f"Current={r.current_ratio.value}[{r.current_ratio.band.value}], "
            f"D/E={r.debt_to_equity.value}[{r.debt_to_equity.band.value}], "
            f"NPM={(r.net_profit_margin.value * 100) if r.net_profit_margin.value is not None else None}%[{r.net_profit_margin.band.value}], "
            f"ICR={r.interest_coverage.value}[{r.interest_coverage.band.value}], "
            f"DSR={r.dsr.value}[{r.dsr.band.value}] (unavailable without verified repayments); "
            f"CFO=RM{r.inputs.get('cash_from_operations')}, EBIT=RM{r.inputs.get('ebit')}, "
            f"equity=RM{r.inputs.get('total_equity')}, revenue=RM{r.inputs.get('revenue')}, "
            f"net_profit=RM{r.inputs.get('net_profit')}"
            for r in financial_ratios
        )
        or "- (no audited financial ratios)"
    )

    flags_block = (
        "\n".join(
            f"- {i.severity.value.upper()}: {i.code}: {i.message} "
            f"(citations: {', '.join(i.citations)})"
            for i in inconsistencies
        )
        or "- (none detected)"
    )

    five_c_block = "\n".join(
        f"- {dim.name}: {dim.rating.value} — {dim.reasoning[:450]} "
        f"(evidence: {', '.join(dim.evidence_chunk_ids[:3]) or '—'})"
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
5. Address every material validation finding. Package inventory checks
   (missing months/documents, duplicate uploads) are system observations:
   identify them as such and do not invent PDF citations for absent evidence.
   In the headline, place citations immediately after the supplied-document
   claim they support, before any contrasting package-inventory limitation.
   Preserve the supplied severity exactly. Never describe a WARNING as a
   critical warning, critical finding, or critical alert. If uncertain, omit
   severity adjectives and refer to the structured validation finding.
6. Use short paragraphs of at most 2-3 sentences, separated by blank lines.
   Separate document scope, financial results, ratios and each 5C dimension.
   Preserve the supplied 5C ratings and limitations; never upgrade Character based on
   limited banking history or the mere presence of registration and tax documents.
   Registration and a tax return do not prove compliance, filing acceptance or payment.
   Report profit margins as percentages. DSR=None means unavailable, never
   estimate repayments or call debt servicing healthy without a verified schedule.
   Organise them in this order: document scope, observed financial facts,
   provisional assessment, and limitations. Do not repeat the same metrics.
   Prefer a concise overview and notable trends to a month-by-month recital.
   Cite all sources needed for an aggregate claim and avoid duplicate ids
   within the same citation group.

Allowed chunk_ids (cite only from this list):
{", ".join(allowed_chunk_ids)}

Bank-statement metrics:
{metrics_block}

Financial ratios (from audited statements):
{ratios_block}

Validation findings:
{flags_block}

5C assessment:
{five_c_block}

Package totals, coverage and document identity:
{package_evidence}

{retrieved_evidence}

Return a RiskSummary object."""


def _representative_metrics(
    metrics: list[BankStatementMetrics], limit: int = 3
) -> list[BankStatementMetrics]:
    if len(metrics) <= limit:
        return metrics
    indexes = {round(position * (len(metrics) - 1) / (limit - 1)) for position in range(limit)}
    return [metric for index, metric in enumerate(metrics) if index in indexes]


def extract_citations(text: str) -> list[str]:
    """Return every chunk_id-like token wrapped in square brackets.

    Handles the LLM's occasional habit of comma-joining citations inside a
    single bracket pair (e.g. `[doc-1:period:0, doc-1:period:1]`).
    """
    found: list[str] = []
    for raw in CITATION_RE.findall(text):
        for token in CITATION_SPLIT_RE.split(raw):
            token = token.strip()
            if token and token.upper() not in NON_CITATION_LABELS:
                found.append(token)
    return found


def normalise_inventory_headline_citations(text: str) -> str:
    """Keep source citations attached to supplied-document facts, not absence checks."""
    inventory_claim = INVENTORY_CLAIM_RE.search(text)
    trailing = TRAILING_CITATIONS_RE.search(text)
    if not inventory_claim or not trailing:
        return text

    prefix = text[: trailing.start()].rstrip()
    contrasts = [
        match for match in CONTRAST_RE.finditer(prefix) if match.end() <= inventory_claim.start()
    ]
    if not contrasts:
        return prefix + trailing.group("period")

    contrast = contrasts[-1]
    sourced_claim = prefix[: contrast.start()].rstrip()
    inventory_clause = prefix[contrast.start() :]
    citations = trailing.group("citations").strip()
    return f"{sourced_claim} {citations}{inventory_clause}{trailing.group('period')}"


def has_unsupported_critical_label(summary: RiskSummary, findings: list[Inconsistency]) -> bool:
    if any(finding.severity.value == "critical" for finding in findings):
        return False
    text = "\n".join([summary.headline, summary.body, *summary.recommended_human_checks])
    return bool(
        re.search(
            r"\bcritical\s+(?:(?:validation|system|risk)\s+)?(?:warning|finding|alert|flag|severity)\b"
            r"|\b(?:severity|warning|finding|alert|flag)\s*(?:is|was|:|=|of)?\s*[\"']?critical\b",
            text,
            re.IGNORECASE,
        )
    )
