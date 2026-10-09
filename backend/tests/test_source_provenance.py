from dataclasses import replace

from app.ingestion.chunker import (
    chunk_audited_financials,
    chunk_bank_statement,
    chunk_ssm_registration,
    chunk_tax_return,
)
from app.ingestion.financials_extractor import extract_audited_financials
from app.ingestion.financials_synthetic import (
    FinancialsGeneratorConfig,
)
from app.ingestion.financials_synthetic import (
    generate as generate_financials,
)
from app.ingestion.parser import parse_pdf
from app.ingestion.ssm_extractor import extract_ssm_registration
from app.ingestion.ssm_synthetic import SSMGeneratorConfig
from app.ingestion.ssm_synthetic import generate as generate_ssm
from app.ingestion.tax_extractor import extract_tax_return
from app.ingestion.tax_synthetic import TaxReturnGeneratorConfig
from app.ingestion.tax_synthetic import generate as generate_tax
from tests.test_chunker import _sample_statement


def _shifted_pages(path, offset):
    return [
        replace(
            page,
            page=page.page + offset,
            spans=[replace(span, page=span.page + offset) for span in page.spans],
        )
        for page in parse_pdf(path)
    ]


def _assert_locations_exist(chunks, pages):
    originals = {page.page: page.text for page in pages}
    for chunk in chunks:
        locations = chunk.source_metadata["source_locations"]
        assert locations
        assert chunk.page == min(location["page"] for location in locations)
        assert chunk.source_metadata["source_pages"] == sorted(
            {location["page"] for location in locations}
        )
        for location in locations:
            for part in location["text"].split():
                assert part in originals[location["page"]]


def test_financial_periods_use_extracted_locations_not_period_index(tmp_path):
    pdf, _ = generate_financials(FinancialsGeneratorConfig(seed=13), tmp_path)
    pages = _shifted_pages(pdf, 7)
    financials = extract_audited_financials(pages)
    chunks = chunk_audited_financials(financials, "audited")
    _assert_locations_exist(chunks, pages)
    assert all(chunk.page >= 8 for chunk in chunks)
    assert chunks[1].source_metadata["source_pages"] == chunks[2].source_metadata["source_pages"]
    assert len(chunks[1].source_metadata["source_pages"]) > 1


def test_tax_and_ssm_citations_preserve_later_page_locations(tmp_path):
    tax_pdf, _ = generate_tax(TaxReturnGeneratorConfig(), tmp_path / "tax")
    tax_pages = _shifted_pages(tax_pdf, 5)
    _assert_locations_exist(chunk_tax_return(extract_tax_return(tax_pages), "tax"), tax_pages)
    ssm_pdf, _ = generate_ssm(SSMGeneratorConfig(), tmp_path / "ssm")
    ssm_pages = _shifted_pages(ssm_pdf, 4)
    chunks = chunk_ssm_registration(extract_ssm_registration(ssm_pages), "ssm")
    _assert_locations_exist(chunks, ssm_pages)
    assert all(chunk.page >= 5 for chunk in chunks)


def test_source_less_summary_does_not_invent_page_one():
    chunk = chunk_bank_statement(_sample_statement(), "manual")[0]
    assert chunk.page is None
    assert chunk.source_metadata["source_pages"] == []
