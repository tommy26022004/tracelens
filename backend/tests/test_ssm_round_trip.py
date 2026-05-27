"""SSM generator → parser → extractor round-trip test."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.parser import parse_pdf
from app.ingestion.ssm_extractor import extract_ssm_registration, looks_like_ssm
from app.ingestion.ssm_synthetic import SSMGeneratorConfig, generate
from app.ingestion.types import SSMRegistration


@pytest.fixture
def synthetic_ssm(tmp_path: Path) -> tuple[Path, Path]:
    return generate(SSMGeneratorConfig(seed=7), tmp_path)


def test_ssm_extractor_matches_ground_truth(synthetic_ssm: tuple[Path, Path]) -> None:
    pdf_path, gt_path = synthetic_ssm
    expected = SSMRegistration.model_validate_json(gt_path.read_text())
    actual = extract_ssm_registration(parse_pdf(pdf_path))

    assert actual.company_name == expected.company_name
    assert actual.registration_number == expected.registration_number
    assert actual.incorporation_date == expected.incorporation_date
    assert actual.company_type == expected.company_type
    assert actual.business_address == expected.business_address
    assert actual.paid_up_capital == expected.paid_up_capital
    assert len(actual.directors) == len(expected.directors)
    for got, want in zip(actual.directors, expected.directors, strict=True):
        assert got.name == want.name
        assert got.nric_or_passport == want.nric_or_passport
        assert got.role == want.role


def test_ssm_detector_recognises_form(synthetic_ssm: tuple[Path, Path]) -> None:
    pdf_path, _ = synthetic_ssm
    assert looks_like_ssm(parse_pdf(pdf_path))


def test_ssm_extractor_rejects_non_ssm(tmp_path: Path) -> None:
    import pymupdf

    blank = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(blank)
    doc.close()

    pages = parse_pdf(blank)
    assert not looks_like_ssm(pages)
