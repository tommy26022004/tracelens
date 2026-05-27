"""Audited financials generator → parser → extractor round-trip."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.financials_extractor import (
    extract_audited_financials,
    looks_like_audited_financials,
)
from app.ingestion.financials_synthetic import FinancialsGeneratorConfig, generate
from app.ingestion.parser import parse_pdf
from app.ingestion.types import AuditedFinancials


@pytest.fixture
def synthetic_financials(tmp_path: Path) -> tuple[Path, Path]:
    return generate(FinancialsGeneratorConfig(seed=13), tmp_path)


def test_financials_extractor_recovers_all_fields(synthetic_financials: tuple[Path, Path]) -> None:
    pdf_path, gt_path = synthetic_financials
    expected = AuditedFinancials.model_validate_json(gt_path.read_text())
    actual = extract_audited_financials(parse_pdf(pdf_path))

    assert actual.company_name == expected.company_name
    assert actual.auditor == expected.auditor
    assert actual.financial_year_end == expected.financial_year_end
    assert len(actual.periods) == len(expected.periods) == 2

    for got, want in zip(actual.periods, expected.periods, strict=True):
        assert got.period_end == want.period_end
        # Allow 1-cent tolerance for floating-point rendering round trips.
        for field in (
            "revenue", "cost_of_sales", "gross_profit", "operating_expenses",
            "ebit", "interest_expense", "net_profit",
            "current_assets", "non_current_assets",
            "current_liabilities", "non_current_liabilities", "total_equity",
            "cash_from_operations",
        ):
            got_val = getattr(got, field)
            want_val = getattr(want, field)
            assert abs(got_val - want_val) <= Decimal("0.01"), (
                f"{field}: got {got_val}, want {want_val}"
            )


def test_financials_detector_recognises_layout(synthetic_financials: tuple[Path, Path]) -> None:
    pdf_path, _ = synthetic_financials
    assert looks_like_audited_financials(parse_pdf(pdf_path))


def test_financials_extractor_rejects_non_financials(tmp_path: Path) -> None:
    import pymupdf

    blank = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(blank)
    doc.close()
    pages = parse_pdf(blank)
    assert not looks_like_audited_financials(pages)
