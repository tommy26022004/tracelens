"""Deterministic checks for package completeness and accounting coherence."""

from __future__ import annotations

from decimal import Decimal

from app.ingestion.package_inventory import PackageInventory
from app.ingestion.types import AuditedFinancials
from app.validation.checks import Inconsistency, Severity


def run_package_checks(
    inventory_payload: dict,
    financials: list[AuditedFinancials],
    financial_document_ids: list[str],
) -> list[Inconsistency]:
    if not inventory_payload:
        return []
    inventory = PackageInventory.model_validate(inventory_payload)
    findings: list[Inconsistency] = []
    for document_id in inventory.duplicate_document_ids:
        findings.append(
            Inconsistency(
                code="DUPLICATE_DOCUMENT",
                severity=Severity.WARNING,
                message=f"Document {document_id} duplicates another uploaded PDF.",
                citations=[],
            )
        )
    if inventory.missing_bank_months:
        findings.append(
            Inconsistency(
                code="MISSING_BANK_MONTHS",
                severity=Severity.WARNING,
                message="Missing bank coverage for: " + ", ".join(inventory.missing_bank_months),
                citations=[],
            )
        )
    if inventory.missing_core_kinds:
        findings.append(
            Inconsistency(
                code="MISSING_CORE_DOCUMENTS",
                severity=Severity.WARNING,
                message="Missing core document types: " + ", ".join(inventory.missing_core_kinds),
                citations=[],
            )
        )
    if inventory.failed_documents:
        findings.append(
            Inconsistency(
                code="DOCUMENT_EXTRACTION_FAILURES",
                severity=Severity.WARNING,
                message=f"{inventory.failed_documents} document(s) could not be extracted or indexed.",
                citations=[],
            )
        )
    for financial, document_id in zip(financials, financial_document_ids, strict=True):
        for index, period in enumerate(financial.periods):
            delta = period.total_assets - period.total_liabilities - period.total_equity
            if abs(delta) > Decimal("0.01"):
                findings.append(
                    Inconsistency(
                        code="AUDITED_ACCOUNTING_EQUATION",
                        severity=Severity.CRITICAL,
                        message=(
                            f"Audited FY{period.period_end.year} does not balance; "
                            f"assets less liabilities and equity differ by RM {delta}."
                        ),
                        citations=[f"{document_id}:period:{index}"],
                    )
                )
    return findings
