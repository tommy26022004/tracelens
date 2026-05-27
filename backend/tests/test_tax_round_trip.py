"""Tax return Form C generator → extractor round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.parser import parse_pdf
from app.ingestion.tax_extractor import extract_tax_return, looks_like_tax_return
from app.ingestion.tax_synthetic import TaxReturnGeneratorConfig, generate
from app.ingestion.types import TaxReturn


@pytest.fixture
def synthetic_tax(tmp_path: Path) -> tuple[Path, Path]:
    return generate(TaxReturnGeneratorConfig(), tmp_path)


def test_tax_extractor_matches_ground_truth(synthetic_tax: tuple[Path, Path]) -> None:
    pdf_path, gt_path = synthetic_tax
    expected = TaxReturn.model_validate_json(gt_path.read_text())
    actual = extract_tax_return(parse_pdf(pdf_path))

    assert actual.company_name == expected.company_name
    assert actual.tax_reference_number == expected.tax_reference_number
    assert actual.year_of_assessment == expected.year_of_assessment
    assert actual.gross_business_income == expected.gross_business_income
    assert actual.chargeable_income == expected.chargeable_income
    assert actual.tax_payable == expected.tax_payable


def test_tax_detector(synthetic_tax: tuple[Path, Path]) -> None:
    pdf_path, _ = synthetic_tax
    assert looks_like_tax_return(parse_pdf(pdf_path))
