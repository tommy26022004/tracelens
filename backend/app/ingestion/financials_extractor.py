"""Audited financials extractor.

The generator emits a 3-table layout (Income Statement, Cash Flow,
Balance Sheet). Each row is `Label  current_year_value  prior_year_value`.
Numbers wrapped in parentheses are negative — standard accounting
notation, but trivial to forget when writing the parser.

The extractor:
1. Groups text spans into rows by y-coordinate (same trick as bank
   statements).
2. Walks rows looking for label keywords from a small lexicon.
3. Pulls the two right-most money tokens off the matched row.

This is deliberately heuristic. Real audited financials vary wildly
in layout (segmental notes, JV adjustments, FX), and the proposal's
research contribution is in the *agent* not the OCR — so the pipeline
treats real-world layout variation as a downstream LLM extraction
problem (deferred).
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from app.ingestion.parser import ParsedPage, TextSpan
from app.ingestion.provenance import labelled_sources, source_location
from app.ingestion.types import AuditedFinancials, FinancialPeriod

ROW_TOLERANCE = 3.0
MONEY_RE = re.compile(r"\(?\d{1,3}(?:,\d{3})*\.\d{2}\)?")
HEADER_KEYWORDS = (
    "INCOME STATEMENT",
    "BALANCE SHEET",
    "CASH FLOW",
    "STATEMENT OF",
    "AUDITED",
    "FINANCIAL STATEMENTS",
)
FOR_YEAR_RE = re.compile(r"For the financial year ended\s+(\d{1,2}\s+\w+\s+\d{4})")
RM_THOUSANDS_RE = re.compile(r"\bRM\s*(?:['\u2019]\s*000|THOUSANDS?)\b", re.IGNORECASE)

ROW_LABELS: dict[str, str] = {
    "Revenue": "revenue",
    "Cost of Sales": "cost_of_sales",
    "Gross Profit": "gross_profit",
    "Operating Expenses": "operating_expenses",
    "EBIT": "ebit",
    "Interest Expense": "interest_expense",
    "Net Profit": "net_profit",
    "Cash from Operations": "cash_from_operations",
    "Current Assets": "current_assets",
    "Non-Current Assets": "non_current_assets",
    "Current Liabilities": "current_liabilities",
    "Non-Current Liabilities": "non_current_liabilities",
    "Total Equity": "total_equity",
}

# Fields that flip sign because the PDF shows them as negative for clarity
# (e.g. "Cost of Sales: (2,300.00)" means an outflow, but our model stores
# the absolute magnitude on a dedicated field). The synthetic generator
# renders these with a leading minus sign, which translates to parentheses
# via `_money`. The extractor stores their absolute magnitude.
EXPENSE_FIELDS = {"cost_of_sales", "operating_expenses", "interest_expense"}


def _group_into_rows(spans: list[TextSpan]) -> list[list[TextSpan]]:
    from collections import defaultdict

    buckets: dict[int, list[TextSpan]] = defaultdict(list)
    for span in spans:
        y_mid = (span.bbox[1] + span.bbox[3]) / 2
        bucket = int(round(y_mid / ROW_TOLERANCE) * ROW_TOLERANCE)
        buckets[bucket].append(span)
    return [sorted(group, key=lambda s: s.bbox[0]) for _, group in sorted(buckets.items())]


def _parse_money(token: str) -> Decimal:
    """Parse `1,234.56` or `(1,234.56)` into a signed Decimal."""
    negative = token.startswith("(") and token.endswith(")")
    cleaned = token.strip("()").replace(",", "")
    value = Decimal(cleaned)
    return -value if negative else value


def _find_two_money_tokens(line_text: str) -> tuple[Decimal, Decimal] | None:
    """Return the last two money-looking tokens from a row, or None."""
    matches = MONEY_RE.findall(line_text)
    if len(matches) < 2:
        return None
    return _parse_money(matches[-2]), _parse_money(matches[-1])


def _financial_unit(pages: list[ParsedPage]) -> tuple[str, Decimal]:
    full_text = "\n".join(page.text for page in pages)
    if RM_THOUSANDS_RE.search(full_text):
        return "RM'000", Decimal("1000")
    return "RM", Decimal("1")


def _extract_company_and_year(pages: list[ParsedPage]) -> tuple[str, str]:
    """First-line company name and parsed financial year end."""
    if not pages:
        raise ValueError("No pages")
    first_rows = _group_into_rows(pages[0].spans)
    if not first_rows:
        raise ValueError("First page is empty")
    company_name = first_rows[0][0].text.strip()

    for row in first_rows:
        text = " ".join(s.text for s in row)
        match = FOR_YEAR_RE.search(text)
        if match:
            return company_name, match.group(1)
    raise ValueError("Could not locate 'For the financial year ended' line")


def _extract_auditor(pages: list[ParsedPage]) -> str:
    for page in pages:
        for span in page.spans:
            if span.text.startswith("Audited by:"):
                return span.text.removeprefix("Audited by:").strip()
    raise ValueError("Missing 'Audited by:' line")


def extract_audited_financials(pages: list[ParsedPage]) -> AuditedFinancials:
    """Parse a 2-period audited financials PDF into a structured object."""
    if not pages:
        raise ValueError("No pages supplied")
    company_name, year_str = _extract_company_and_year(pages)
    auditor = _extract_auditor(pages)
    fy_end = datetime.strptime(year_str, "%d %B %Y").date()
    display_unit, unit_multiplier = _financial_unit(pages)

    rows: list[list[TextSpan]] = []
    for page in pages:
        rows.extend(_group_into_rows(page.spans))

    current_vals: dict[str, Decimal] = {}
    prior_vals: dict[str, Decimal] = {}
    field_sources = {}
    seen_headers: set[str] = set()

    for row in rows:
        line = " ".join(s.text for s in row).strip()
        upper = line.upper()
        # Skip section headers but record them for sanity checks.
        if any(h in upper for h in HEADER_KEYWORDS):
            seen_headers.add(upper)
            continue
        for label, field in ROW_LABELS.items():
            if line.startswith(label) and field not in current_vals:
                values = _find_two_money_tokens(line)
                if values is None:
                    continue
                current, prior = values
                field_sources[field] = source_location(row)
                if field in EXPENSE_FIELDS:
                    current_vals[field] = abs(current)
                    prior_vals[field] = abs(prior)
                else:
                    current_vals[field] = current
                    prior_vals[field] = prior
                break

    required_fields = {
        "revenue",
        "cost_of_sales",
        "gross_profit",
        "operating_expenses",
        "ebit",
        "interest_expense",
        "net_profit",
        "current_assets",
        "non_current_assets",
        "current_liabilities",
        "non_current_liabilities",
        "total_equity",
        "cash_from_operations",
    }
    missing = required_fields - current_vals.keys()
    if missing:
        raise ValueError(
            f"Missing required financial fields: {sorted(missing)}. "
            "Document may not match the supported audited-financials layout."
        )

    if unit_multiplier != 1:
        current_vals = {name: value * unit_multiplier for name, value in current_vals.items()}
        prior_vals = {name: value * unit_multiplier for name, value in prior_vals.items()}

    prior_year_end = fy_end.replace(year=fy_end.year - 1)
    current_period = FinancialPeriod(period_end=fy_end, source_fields=field_sources, **current_vals)
    prior_period = FinancialPeriod(
        period_end=prior_year_end, source_fields=field_sources, **prior_vals
    )

    return AuditedFinancials(
        company_name=company_name,
        auditor=auditor,
        financial_year_end=fy_end,
        periods=[current_period, prior_period],
        display_unit=display_unit,
        canonical_unit="RM",
        unit_multiplier=unit_multiplier,
        page_count=len(pages),
        source_fields={
            "company_name": source_location(_group_into_rows(pages[0].spans)[0]),
            **labelled_sources(
                rows,
                {
                    "Audited by:": "auditor",
                    "For the financial year ended": "financial_year_end",
                },
            ),
        },
    )


def looks_like_audited_financials(pages: list[ParsedPage]) -> bool:
    """Cheap detector for the pipeline router."""
    for page in pages:
        full_text = page.text.upper()
        if "INCOME STATEMENT" in full_text or "BALANCE SHEET" in full_text:
            return True
        if "AUDITED BY:" in full_text and "FINANCIAL YEAR ENDED" in full_text:
            return True
    return False


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from app.ingestion.parser import parse_pdf

    pages = parse_pdf(Path(sys.argv[1]))
    print(extract_audited_financials(pages).model_dump_json(indent=2))
