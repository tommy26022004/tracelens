"""Ground-truth bank PDF under small deterministic OCR/layout shifts."""

from dataclasses import replace

import pytest

from app.evaluation.extraction_accuracy import score_bank_statement
from app.ingestion.extractor import extract_bank_statement
from app.ingestion.parser import parse_pdf
from app.ingestion.synthetic import GeneratorConfig, generate
from app.ingestion.types import BankStatement


@pytest.mark.parametrize("vertical_shift", [0.0, 0.5, 1.0, 1.4])
def test_small_span_offsets_preserve_extracted_fields(tmp_path, vertical_shift: float) -> None:
    pdf, ground_truth = generate(GeneratorConfig(seed=21, n_transactions=14, num_months=1), tmp_path)
    expected = BankStatement.model_validate_json(ground_truth.read_text())
    pages = parse_pdf(pdf)
    shifted_pages = []
    for page in pages:
        spans = []
        for index, span in enumerate(page.spans):
            offset = vertical_shift if index % 2 else -vertical_shift
            left, top, right, bottom = span.bbox
            spans.append(replace(span, bbox=(left + 18, top + offset, right + 18, bottom + offset)))
        shifted_pages.append(replace(page, spans=spans))
    actual = extract_bank_statement(shifted_pages)
    report = score_bank_statement(expected, actual)
    assert report.accuracy == 1.0, report.mismatches
