"""Deterministic credit narrative used when the configured LLM is unavailable."""

from __future__ import annotations

from decimal import Decimal

from app.explainability.summary import RiskSummary
from app.ratios.bank_statement_metrics import BankStatementMetrics
from app.ratios.financial_ratios import FinancialRatios, RatioBand
from app.ratios.five_c import Dimension, FiveCAssessment, Rating
from app.validation.checks import Inconsistency, Severity


def build_fallback_five_c(
    metrics: list[BankStatementMetrics],
    inconsistencies: list[Inconsistency],
    financial_ratios: list[FinancialRatios],
    allowed_chunk_ids: list[str],
    *,
    package_cash_flow: dict | None = None,
) -> FiveCAssessment:
    allowed = set(allowed_chunk_ids)
    bank_citations = _allowed(
        [f"{metric.document_id}:summary:0" for metric in metrics[:3]], allowed
    )
    financial_citations = _allowed(
        [f"{ratio.document_id}:period:0" for ratio in financial_ratios[:3]], allowed
    )
    has_critical = any(item.severity is Severity.CRITICAL for item in inconsistencies)
    has_warning = any(item.severity is Severity.WARNING for item in inconsistencies)
    _, _, total_net_change = _cash_totals(metrics, package_cash_flow)

    character_rating = (
        Rating.WEAK if has_critical else Rating.ADEQUATE if has_warning else Rating.STRONG
    )
    character_reason = (
        "Critical document inconsistencies require clarification before character can be relied upon."
        if has_critical
        else "Transaction activity is regular and no critical document inconsistency was detected."
    )

    capacity_rating = Rating.INSUFFICIENT_DATA
    capacity_reason = "No bank-statement cash-flow metrics were available."
    if metrics:
        capacity_rating = (
            Rating.STRONG if total_net_change > 0 and not has_critical else Rating.WEAK
        )
        capacity_reason = (
            f"Across {len(metrics)} bank statements, aggregate net movement is "
            f"RM {total_net_change:,.2f}."
        )

    capital_rating = Rating.INSUFFICIENT_DATA
    capital_reason = "Audited financial ratios were not available to assess the capital cushion."
    if financial_ratios:
        latest = financial_ratios[0]
        healthy = latest.debt_to_equity.band in {RatioBand.HEALTHY, RatioBand.ACCEPTABLE}
        capital_rating = Rating.STRONG if healthy else Rating.WEAK
        capital_reason = (
            f"The latest audited debt-to-equity ratio is {latest.debt_to_equity.value} "
            f"and current ratio is {latest.current_ratio.value}."
        )

    conditions_rating = Rating.INSUFFICIENT_DATA
    conditions_reason = (
        "The supplied package does not provide external market, industry, customer concentration, "
        "supplier dependence or facility-purpose evidence needed to assess Conditions."
    )
    if has_critical:
        conditions_reason += " Material validation findings must also be resolved before the package can be relied upon."

    return FiveCAssessment(
        character=Dimension(
            name="Character",
            rating=character_rating,
            reasoning=character_reason,
            evidence_chunk_ids=bank_citations,
            flags_for_human_review=["Verify adverse credit and director history externally"],
        ),
        capacity=Dimension(
            name="Capacity",
            rating=capacity_rating,
            reasoning=capacity_reason,
            evidence_chunk_ids=bank_citations,
            flags_for_human_review=["Recalculate debt service using the proposed facility terms"],
        ),
        capital=Dimension(
            name="Capital",
            rating=capital_rating,
            reasoning=capital_reason,
            evidence_chunk_ids=financial_citations,
            flags_for_human_review=["Confirm audited figures against signed statements"],
        ),
        collateral=Dimension(
            name="Collateral",
            rating=Rating.INSUFFICIENT_DATA,
            reasoning="The supplied financial package does not establish ownership, valuation, or legal enforceability of collateral.",
            evidence_chunk_ids=[],
            flags_for_human_review=["Request the asset schedule, valuation and security documents"],
        ),
        conditions=Dimension(
            name="Conditions",
            rating=conditions_rating,
            reasoning=conditions_reason,
            evidence_chunk_ids=bank_citations,
            flags_for_human_review=["Review sector outlook and facility purpose"],
        ),
    )


def build_fallback_summary(
    metrics: list[BankStatementMetrics],
    inconsistencies: list[Inconsistency],
    five_c: FiveCAssessment,
    financial_ratios: list[FinancialRatios],
    allowed_chunk_ids: list[str],
    *,
    package_cash_flow: dict | None = None,
    package_inventory: dict | None = None,
    needs_ocr_pages: dict[str, list[int]] | None = None,
    document_parse_failures: dict[str, str] | None = None,
) -> RiskSummary:
    allowed = set(allowed_chunk_ids)
    bank_citation = _first_allowed(
        [f"{metric.document_id}:summary:0" for metric in metrics], allowed
    )
    financial_citation = _first_allowed(
        [f"{ratio.document_id}:period:0" for ratio in financial_ratios], allowed
    )
    fallback_citation = bank_citation or financial_citation or next(iter(allowed), "")
    total_credits, total_debits, total_net = _cash_totals(metrics, package_cash_flow)
    bank_sources = " ".join(
        f"[{citation}]"
        for citation in dict.fromkeys(
            _allowed([f"{metric.document_id}:summary:0" for metric in metrics], allowed)
        )
    )

    package_inventory = package_inventory or {}
    needs_ocr_pages = needs_ocr_pages or {}
    document_parse_failures = document_parse_failures or {}
    extraction_failed = (
        package_inventory.get("total_documents", 0) > 0
        and package_inventory.get("extracted_documents", 0) == 0
        and package_inventory.get("failed_documents", 0) > 0
    )
    revenue_finding = next(
        (item for item in inconsistencies if item.code == "AUDITED_VS_TAX_REVENUE"),
        None,
    )
    revenue_citations = _allowed(revenue_finding.citations, allowed) if revenue_finding else []
    if extraction_failed and document_parse_failures:
        headline = (
            "Invalid or damaged PDF detected; no document evidence was extracted and no "
            "financial conclusion is supported."
        )
    elif extraction_failed and needs_ocr_pages:
        headline = (
            "Image-only PDF detected; OCR is required but is not currently supported, "
            "so no document evidence was extracted."
        )
    elif extraction_failed:
        headline = (
            "Document extraction failed; no credit assessment can be supported from the "
            "submitted package."
        )
    elif revenue_finding:
        source_tags = " ".join(f"[{citation}]" for citation in revenue_citations)
        headline = (
            "Audited and tax-reported income figures require reconciliation before reliance"
            + (f" {source_tags}" if source_tags else "")
            + "."
        )
    else:
        headline = "The application package was processed using deterministic fallback assessment"
        if fallback_citation:
            headline += f" [{fallback_citation}]"
        headline += "."

    paragraphs: list[str] = []
    if extraction_failed:
        paragraphs.append(
            "No uploaded document was successfully extracted or indexed. The following 5C "
            "ratings reflect unavailable evidence, not an assessment of applicant strength."
        )
    else:
        paragraphs.append(
            "This narrative was generated by the deterministic fallback because the configured AI assessment was unavailable."
        )
    if metrics and bank_citation:
        paragraphs.append(
            f"Using the validated package totals, total credits are RM {total_credits:,.2f}, "
            f"total debits are RM {total_debits:,.2f}, and aggregate net movement is "
            f"RM {total_net:,.2f} {bank_sources}."
        )
    if financial_ratios and financial_citation:
        latest = financial_ratios[0]
        paragraphs.append(
            f"The latest audited current ratio is {latest.current_ratio.value} and debt-to-equity "
            f"is {latest.debt_to_equity.value} [{financial_citation}]."
        )
    if inconsistencies:
        cited_findings = [item for item in inconsistencies if item.citations]
        if cited_findings:
            finding_details = []
            for finding in cited_findings:
                source_tags = " ".join(
                    f"[{citation}]" for citation in _allowed(finding.citations, allowed)
                )
                finding_details.append(
                    f"{finding.code}: {finding.message}"
                    + (f" {source_tags}" if source_tags else "")
                )
            paragraphs.append(
                f"Validation identified {len(inconsistencies)} finding(s) requiring review: "
                + " ".join(finding_details)
            )
    elif fallback_citation:
        paragraphs.append(
            f"No deterministic cross-document inconsistency was detected [{fallback_citation}]."
        )
    paragraphs.append(
        "Collateral remains insufficiently evidenced and must be verified by a loan officer before any credit decision."
    )

    checks = sorted(
        {
            flag
            for dimension in (
                five_c.character,
                five_c.capacity,
                five_c.capital,
                five_c.collateral,
                five_c.conditions,
            )
            for flag in dimension.flags_for_human_review
        }
    )
    body = "\n\n".join(paragraphs)
    cited = sorted({citation for citation in allowed if f"[{citation}]" in headline + body})
    return RiskSummary(
        headline=headline,
        body=body,
        recommended_human_checks=checks,
        cited_chunk_ids=cited,
    )


def _cash_totals(
    metrics: list[BankStatementMetrics], package_cash_flow: dict | None
) -> tuple[Decimal, Decimal, Decimal]:
    if package_cash_flow:
        credits = sum(
            (Decimal(str(value)) for value in package_cash_flow["monthly_credits"].values()),
            Decimal(0),
        )
        debits = sum(
            (Decimal(str(value)) for value in package_cash_flow["monthly_debits"].values()),
            Decimal(0),
        )
        return credits, debits, Decimal(str(package_cash_flow["net_cash_change"]))
    return (
        sum((metric.total_credits for metric in metrics), Decimal(0)),
        sum((metric.total_debits for metric in metrics), Decimal(0)),
        sum((metric.net_change for metric in metrics), Decimal(0)),
    )


def _allowed(citations: list[str], allowed: set[str]) -> list[str]:
    return [citation for citation in citations if citation in allowed]


def _first_allowed(citations: list[str], allowed: set[str]) -> str:
    return next((citation for citation in citations if citation in allowed), "")
