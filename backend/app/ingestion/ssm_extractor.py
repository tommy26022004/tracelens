"""SSM registration extractor.

The form follows a `Label: Value` layout. Each field has a label that we
match against a small lexicon; the value is everything on the same row
to the right of the label, plus the immediately-following row(s) for
the multi-line address field.

For director rows we look for the "Directors:" header, then parse each
subsequent numbered line until the section ends.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from app.ingestion.parser import ParsedPage, TextSpan
from app.ingestion.types import Director, SSMRegistration

LABEL_TO_FIELD: dict[str, str] = {
    "Company Name": "company_name",
    "Registration Number": "registration_number",
    "Date of Incorporation": "incorporation_date",
    "Company Type": "company_type",
    "Business Address": "business_address",
    "Paid-Up Capital": "paid_up_capital",
}

DIRECTOR_LINE_RE = re.compile(
    r"^\d+\.\s+(.+?)\s+-\s+NRIC:\s*(\S+)\s+-\s+Role:\s*(.+)$"
)
MONEY_RE = re.compile(r"RM\s*([\d,]+\.\d{2})")
ROW_TOLERANCE = 3.0


def _group_into_rows(spans: list[TextSpan]) -> list[list[TextSpan]]:
    from collections import defaultdict

    buckets: dict[int, list[TextSpan]] = defaultdict(list)
    for span in spans:
        y_mid = (span.bbox[1] + span.bbox[3]) / 2
        bucket = int(round(y_mid / ROW_TOLERANCE) * ROW_TOLERANCE)
        buckets[bucket].append(span)
    return [sorted(group, key=lambda s: s.bbox[0]) for _, group in sorted(buckets.items())]


def _find_value(rows: list[list[TextSpan]], label: str) -> str | None:
    """Return the value half of a `Label: value` row, matching label by prefix."""
    target = f"{label}:"
    for row in rows:
        line_text = " ".join(s.text for s in row)
        if line_text.startswith(target):
            return line_text[len(target):].strip()
    return None


def _parse_incorporation_date(value: str) -> "datetime.date":
    # Handles "15 January 2024" — month name is full English.
    return datetime.strptime(value, "%d %B %Y").date()


def _parse_money(value: str) -> Decimal:
    match = MONEY_RE.search(value)
    if not match:
        raise ValueError(f"Could not parse RM amount from: {value!r}")
    return Decimal(match.group(1).replace(",", ""))


def _extract_directors(rows: list[list[TextSpan]]) -> list[Director]:
    directors: list[Director] = []
    in_section = False
    for row in rows:
        line = " ".join(s.text for s in row).strip()
        if line.startswith("Directors:"):
            in_section = True
            continue
        if not in_section:
            continue
        match = DIRECTOR_LINE_RE.match(line)
        if match:
            name, nric, role = match.groups()
            directors.append(
                Director(name=name.strip(), nric_or_passport=nric.strip(), role=role.strip())
            )
    return directors


def extract_ssm_registration(pages: list[ParsedPage]) -> SSMRegistration:
    """Parse an SSM Form 9 PDF into a structured `SSMRegistration`.

    Raises `ValueError` if any mandatory field is missing — that means
    the document is not an SSM Form 9 in the expected layout.
    """
    if not pages:
        raise ValueError("No pages supplied")
    rows: list[list[TextSpan]] = []
    for page in pages:
        rows.extend(_group_into_rows(page.spans))

    fields: dict[str, object] = {}
    for label, field in LABEL_TO_FIELD.items():
        value = _find_value(rows, label)
        if value is None:
            raise ValueError(f"Missing SSM field: {label}")
        fields[field] = value

    directors = _extract_directors(rows)
    if not directors:
        raise ValueError("No directors found — document may not be an SSM Form 9")

    return SSMRegistration(
        company_name=str(fields["company_name"]),
        registration_number=str(fields["registration_number"]),
        incorporation_date=_parse_incorporation_date(str(fields["incorporation_date"])),
        company_type=str(fields["company_type"]),
        business_address=str(fields["business_address"]),
        paid_up_capital=_parse_money(str(fields["paid_up_capital"])),
        directors=directors,
        page_count=len(pages),
    )


def looks_like_ssm(pages: list[ParsedPage]) -> bool:
    """Cheap heuristic for the pipeline router.

    Returns True if the document contains the SSM form header. Avoids
    paying the cost of full extraction just to detect the kind.
    """
    for page in pages:
        for span in page.spans:
            if "SURUHANJAYA SYARIKAT MALAYSIA" in span.text:
                return True
            if "FORM 9" in span.text.upper() and "INCORPORATION" in page.text.upper():
                return True
    return False


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from app.ingestion.parser import parse_pdf

    target = Path(sys.argv[1])
    pages = parse_pdf(target)
    print(extract_ssm_registration(pages).model_dump_json(indent=2))
