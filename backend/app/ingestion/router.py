"""Document-type detection for the pipeline router.

The agent's `parse_node` parses every PDF. The extract stage then asks
this module which structured extractor to use. Detection is intentionally
cheap (header keyword sniffing) — full parsing already happened, so we
just inspect the text spans.
"""

from __future__ import annotations

from app.ingestion.financials_extractor import looks_like_audited_financials
from app.ingestion.parser import ParsedPage
from app.ingestion.ssm_extractor import looks_like_ssm
from app.ingestion.tax_extractor import looks_like_tax_return
from app.ingestion.types import DocumentKind


def _looks_like_bank_statement(pages: list[ParsedPage]) -> bool:
    if not pages:
        return False
    for span in pages[0].spans:
        text_upper = span.text.upper()
        if "STATEMENT OF ACCOUNT" in text_upper:
            return True
        if "ACCOUNT NUMBER" in text_upper and any(
            "STATEMENT PERIOD" in s.text.upper() for s in pages[0].spans
        ):
            return True
    return False


def detect_document_kind(pages: list[ParsedPage]) -> DocumentKind:
    """Best-effort classification. Returns UNKNOWN when no detector matches.

    Order matters: tax return is checked before audited financials because
    the Form C header is more distinctive than a generic "INCOME STATEMENT"
    keyword, and we want a precise classification.
    """
    if looks_like_ssm(pages):
        return DocumentKind.SSM_REGISTRATION
    if looks_like_tax_return(pages):
        return DocumentKind.TAX_RETURN
    if looks_like_audited_financials(pages):
        return DocumentKind.AUDITED_FINANCIALS
    if _looks_like_bank_statement(pages):
        return DocumentKind.BANK_STATEMENT
    return DocumentKind.UNKNOWN
