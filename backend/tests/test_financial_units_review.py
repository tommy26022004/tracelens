import json
from pathlib import Path

from app.ingestion.chunker import chunk_audited_financials
from app.ingestion.financials_extractor import extract_audited_financials
from app.ingestion.parser import parse_pdf
from app.ratios.financial_ratios import compute_financial_ratios


def test_case14_normalises_rm_thousands_to_canonical_rm_without_changing_ratios():
    root = Path(__file__).resolve().parents[2] / "data/ordered_tests_v1/14_units_rm_thousands"
    truth = json.loads((root / "ground_truth.json").read_text(encoding="utf-8"))["documents"][
        "financials_rm_thousands.pdf"
    ]
    financials = extract_audited_financials(parse_pdf(root / "upload/financials_rm_thousands.pdf"))

    assert financials.display_unit == "RM'000"
    assert financials.canonical_unit == "RM"
    assert str(financials.unit_multiplier) == "1000"
    for period in financials.periods:
        expected = truth["periods"][str(period.period_end.year)]
        for field, value in expected.items():
            assert str(getattr(period, field)) == value, f"{period.period_end.year} {field}"
            assert period.source_fields[field].page == truth["field_pages"][field]

    ratios = compute_financial_ratios(financials, "financials-rm-thousands")
    assert ratios.source_display_unit == "RM'000"
    assert str(ratios.unit_multiplier) == "1000"
    assert str(ratios.inputs["revenue"]) == "120000.00"
    assert str(ratios.current_ratio.value) == truth["expected_ratios_2025"]["current_ratio"]
    assert str(ratios.debt_to_equity.value) == truth["expected_ratios_2025"]["debt_to_equity"]
    assert (
        str(ratios.net_profit_margin.value)
        == truth["expected_ratios_2025"]["net_profit_margin_fraction"]
    )
    assert str(ratios.interest_coverage.value) == truth["expected_ratios_2025"]["interest_coverage"]

    chunks = chunk_audited_financials(financials, "financials-rm-thousands")
    assert "Revenue (current): RM 120000.00" in chunks[0].text
    assert "values normalized to RM using multiplier 1000" in chunks[0].text
    assert chunks[0].source_metadata["source_display_unit"] == "RM'000"
