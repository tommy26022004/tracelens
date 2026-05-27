"""Document ingestion pipeline.

Responsibilities:
- Detect document type (bank statement, audited financials, SSM form, tax return).
- Parse with PyMuPDF + pdfplumber; fall back to Tesseract OCR for scanned PDFs.
- Chunk and embed into Qdrant for retrieval during agent reasoning.
"""
