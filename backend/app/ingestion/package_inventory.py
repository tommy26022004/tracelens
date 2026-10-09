"""Build package-level inventory, grouping and completeness information."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from app.ingestion.parser import ParsedPage
from app.ingestion.types import DocumentKind

CORE_KINDS = {
    DocumentKind.BANK_STATEMENT,
    DocumentKind.AUDITED_FINANCIALS,
    DocumentKind.SSM_REGISTRATION,
    DocumentKind.TAX_RETURN,
}


class InventoryDocument(BaseModel):
    document_id: str
    kind: DocumentKind
    page_count: int
    sha256: str
    extraction_status: str
    duplicate_of: str | None = None
    account_number: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    financial_year: int | None = None


class PackageInventory(BaseModel):
    documents: list[InventoryDocument]
    total_documents: int
    total_pages: int
    extracted_documents: int
    failed_documents: int
    documents_by_kind: dict[str, int]
    bank_coverage_by_account: dict[str, list[str]]
    missing_bank_months: list[str]
    financial_years: list[int]
    missing_core_kinds: list[str]
    duplicate_document_ids: list[str]
    complete: bool


def build_package_inventory(
    document_ids: list[str],
    document_kinds: dict[str, DocumentKind],
    parsed_pages: dict[str, list[ParsedPage]],
    document_hashes: dict[str, str],
    extracted_metadata: dict[str, dict[str, Any]],
) -> PackageInventory:
    first_by_hash: dict[str, str] = {}
    documents: list[InventoryDocument] = []
    kind_counts: dict[str, int] = defaultdict(int)
    coverage: dict[str, set[str]] = defaultdict(set)
    financial_years: set[int] = set()
    duplicates: list[str] = []

    for document_id in document_ids:
        kind = document_kinds.get(document_id, DocumentKind.UNKNOWN)
        metadata = extracted_metadata.get(document_id, {})
        digest = document_hashes.get(document_id, "")
        duplicate_of = first_by_hash.get(digest) if digest else None
        if digest and duplicate_of is None:
            first_by_hash[digest] = document_id
        elif duplicate_of is not None:
            duplicates.append(document_id)

        account_number = metadata.get("account_number")
        period_start = metadata.get("period_start")
        if account_number and period_start:
            coverage[str(account_number)].add(str(period_start)[:7])
        year = metadata.get("financial_year")
        if isinstance(year, int):
            financial_years.add(year)
        kind_counts[kind.value] += 1
        documents.append(
            InventoryDocument(
                document_id=document_id,
                kind=kind,
                page_count=len(parsed_pages.get(document_id, [])),
                sha256=digest,
                extraction_status=str(metadata.get("status", "failed")),
                duplicate_of=duplicate_of,
                account_number=account_number,
                period_start=period_start,
                period_end=metadata.get("period_end"),
                financial_year=year,
            )
        )

    observed_months = {month for months in coverage.values() for month in months}
    observed_year = max((int(month[:4]) for month in observed_months), default=None)
    expected_months = (
        {f"{observed_year}-{month:02d}" for month in range(1, 13)}
        if observed_year is not None
        else set()
    )
    missing_months = sorted(expected_months - observed_months)
    present_kinds = set(document_kinds.values())
    missing_core = sorted(kind.value for kind in CORE_KINDS - present_kinds)
    extracted = sum(
        document.extraction_status in {"extracted", "indexed"} for document in documents
    )
    failed = len(documents) - extracted
    return PackageInventory(
        documents=documents,
        total_documents=len(documents),
        total_pages=sum(document.page_count for document in documents),
        extracted_documents=extracted,
        failed_documents=failed,
        documents_by_kind=dict(sorted(kind_counts.items())),
        bank_coverage_by_account={key: sorted(value) for key, value in sorted(coverage.items())},
        missing_bank_months=missing_months,
        financial_years=sorted(financial_years),
        missing_core_kinds=missing_core,
        duplicate_document_ids=duplicates,
        complete=not missing_months and not missing_core and not duplicates and failed == 0,
    )
