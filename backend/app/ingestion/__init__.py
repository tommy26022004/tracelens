"""Document ingestion pipeline.

Pipeline shape (bank statement, Phase 2 vertical slice):

    raw PDF
      → parser.parse_pdf()        # PyMuPDF text + bbox per page
      → extractor.extract_bank_statement()  # structured transactions + summary
      → chunker.chunk_for_embedding()       # citation-preserving chunks
      → store.upsert_chunks()               # Qdrant

OCR fallback (Tesseract) is triggered when a page's extracted text density
falls below `parser.TEXT_DENSITY_THRESHOLD` — not implemented yet.

Submodules are intentionally not re-exported here so that touching one
domain piece (e.g. just the synthetic generator) doesn't force-load the
entire pipeline.
"""
