"""Document-type detection for the pipeline router.

The agent's `parse_node` parses every PDF. The extract stage then asks
this module which structured extractor to use. Detection is intentionally
cheap (header keyword sniffing) — full parsing already happened, so we
just inspect the text spans.
"""

from __future__ import annotations

from app.ingestion.parser import ParsedPage
from app.ingestion.ssm_extractor import looks_like_ssm
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
    """Best-effort classification. Returns UNKNOWN when no detector matches."""
    if looks_like_ssm(pages):
        return DocumentKind.SSM_REGISTRATION
    if _looks_like_bank_statement(pages):
        return DocumentKind.BANK_STATEMENT
    return DocumentKind.UNKNOWN
