"""Malaysian Form C tax return extractor.

Same label-based approach as the SSM extractor. The set of required
fields is small enough that we can match each line by prefix.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.ingestion.parser import ParsedPage, TextSpan
from app.ingestion.provenance import labelled_sources
from app.ingestion.types import TaxReturn

ROW_TOLERANCE = 3.0
MONEY_RE = re.compile(r"RM\s*([\d,]+\.\d{2})")


def _group_into_rows(spans: list[TextSpan]) -> list[list[TextSpan]]:
    from collections import defaultdict

    buckets: dict[int, list[TextSpan]] = defaultdict(list)
    for span in spans:
        y_mid = (span.bbox[1] + span.bbox[3]) / 2
        bucket = int(round(y_mid / ROW_TOLERANCE) * ROW_TOLERANCE)
        buckets[bucket].append(span)
    return [sorted(group, key=lambda s: s.bbox[0]) for _, group in sorted(buckets.items())]


def _find_value(rows: list[list[TextSpan]], label: str) -> str | None:
    target = f"{label}:"
    for row in rows:
        text = " ".join(s.text for s in row)
        if text.startswith(target):
            return text[len(target) :].strip()
    return None


def _parse_money(value: str) -> Decimal:
    match = MONEY_RE.search(value)
    if not match:
        raise ValueError(f"Cannot parse RM amount: {value!r}")
    return Decimal(match.group(1).replace(",", ""))


def extract_tax_return(pages: list[ParsedPage]) -> TaxReturn:
    if not pages:
        raise ValueError("No pages supplied")

    rows: list[list[TextSpan]] = []
    for page in pages:
        rows.extend(_group_into_rows(page.spans))

    company = _find_value(rows, "Company Name")
    tax_ref = _find_value(rows, "Tax Reference Number")
    ya = _find_value(rows, "Year of Assessment")
    gross = _find_value(rows, "Gross Business Income")
    chargeable = _find_value(rows, "Chargeable Income")
    payable = _find_value(rows, "Tax Payable")

    if not all([company, tax_ref, ya, gross, chargeable, payable]):
        raise ValueError("Missing required Form C fields")

    return TaxReturn(
        company_name=str(company),
        tax_reference_number=str(tax_ref),
        year_of_assessment=int(str(ya).strip()),
        gross_business_income=_parse_money(str(gross)),
        chargeable_income=_parse_money(str(chargeable)),
        tax_payable=_parse_money(str(payable)),
        page_count=len(pages),
        source_fields=labelled_sources(
            rows,
            {
                "Company Name:": "company_name",
                "Tax Reference Number:": "tax_reference_number",
                "Year of Assessment:": "year_of_assessment",
                "Gross Business Income:": "gross_business_income",
                "Chargeable Income:": "chargeable_income",
                "Tax Payable:": "tax_payable",
            },
        ),
    )


def looks_like_tax_return(pages: list[ParsedPage]) -> bool:
    for page in pages:
        upper = page.text.upper()
        if "LEMBAGA HASIL DALAM NEGERI" in upper:
            return True
        if "FORM C" in upper and "CHARGEABLE INCOME" in upper:
            return True
    return False


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from app.ingestion.parser import parse_pdf

    pages = parse_pdf(Path(sys.argv[1]))
    print(extract_tax_return(pages).model_dump_json(indent=2))
