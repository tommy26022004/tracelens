"""End-to-end generation and extraction test for a realistic package."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.extractor import extract_bank_statement
from app.ingestion.financials_extractor import extract_audited_financials
from app.ingestion.parser import parse_pdf
from app.ingestion.ssm_extractor import extract_ssm_registration
from app.ingestion.tax_extractor import extract_tax_return
from scripts.generate_realistic_packages import generate_realistic_package


@pytest.fixture(scope="module")
def realistic_package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("realistic_package")
    generate_realistic_package(output)
    return output


def test_realistic_package_has_expected_workload(realistic_package: Path) -> None:
    pdfs = list(realistic_package.rglob("*.pdf"))
    assert len(pdfs) == 32

    import pymupdf

    total_pages = 0
    for pdf_path in pdfs:
        with pymupdf.open(pdf_path) as document:
            total_pages += document.page_count
    assert total_pages == 337


def test_core_documents_remain_extractable(realistic_package: Path) -> None:
    bank = extract_bank_statement(
        parse_pdf(realistic_package / "bank/operating_account/statement_2025_01.pdf")
    )
    financials = extract_audited_financials(
        parse_pdf(realistic_package / "audited/audited_financials_2025.pdf")
    )
    ssm = extract_ssm_registration(parse_pdf(realistic_package / "ssm/ssm_registration.pdf"))
    tax = extract_tax_return(parse_pdf(realistic_package / "tax/tax_return_YA2025.pdf"))

    assert len(bank.transactions) == 56
    assert financials.page_count == 40
    assert ssm.page_count == 25
    assert tax.page_count == 20
