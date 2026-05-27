"""PDF parsing — text + bounding boxes per page using PyMuPDF.

This is the first stage of the ingestion pipeline. It does NOT understand
bank statements — it only turns a PDF into structured text spans that the
extractor (next stage) can reason about.

Citation traceability requirement (FEATERS-aligned):
every span keeps its 1-indexed page number and bounding box so that any
downstream figure or claim can be traced back to a precise PDF region.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

# A page is considered "scanned" when its extracted text contains fewer
# characters than this threshold — extractor.py will then route it through
# OCR fallback (not yet implemented).
TEXT_DENSITY_THRESHOLD: int = 40


@dataclass(frozen=True)
class TextSpan:
    """One visual line of text on a page with its bounding box."""

    text: str
    page: int
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points


@dataclass(frozen=True)
class ParsedPage:
    page: int
    width: float
    height: float
    spans: list[TextSpan]
    needs_ocr: bool

    @property
    def text(self) -> str:
        return "\n".join(span.text for span in self.spans)


def parse_pdf(path: Path) -> list[ParsedPage]:
    """Open a PDF and return one ParsedPage per page.

    Uses PyMuPDF's `get_text("dict")` to keep bounding boxes alongside text.
    Pages flagged `needs_ocr=True` should be re-parsed via OCR before the
    extractor sees them.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    pages: list[ParsedPage] = []
    with pymupdf.open(path) as doc:
        for page_index, page in enumerate(doc, start=1):
            spans: list[TextSpan] = []
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                # block type 0 == text, 1 == image (skip images for now)
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    line_text = "".join(
                        span.get("text", "") for span in line.get("spans", [])
                    ).strip()
                    if not line_text:
                        continue
                    bbox = tuple(line["bbox"])  # type: ignore[assignment]
                    spans.append(TextSpan(text=line_text, page=page_index, bbox=bbox))

            total_chars = sum(len(s.text) for s in spans)
            pages.append(
                ParsedPage(
                    page=page_index,
                    width=page.rect.width,
                    height=page.rect.height,
                    spans=spans,
                    needs_ocr=total_chars < TEXT_DENSITY_THRESHOLD,
                )
            )
    return pages


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1])
    for parsed in parse_pdf(target):
        print(f"--- Page {parsed.page} ({len(parsed.spans)} spans, needs_ocr={parsed.needs_ocr}) ---")
        for span in parsed.spans[:8]:
            print(f"  [{span.bbox[0]:.0f},{span.bbox[1]:.0f}] {span.text}")
