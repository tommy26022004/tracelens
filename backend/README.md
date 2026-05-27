# Backend — FYP Agentic SME Loan Analysis

FastAPI + LangGraph service powering document ingestion, multi-step ReAct agent reasoning, and explainable risk summarisation.

## Quickstart

```bash
# install uv: https://docs.astral.sh/uv/
uv sync
uv run uvicorn app.main:app --reload
```

## Folder layout

```
app/
├── api/             # HTTP routes (auth, documents, analysis)
├── core/            # config, security, db sessions, logging
├── ingestion/       # PyMuPDF + Tesseract OCR + chunking → Qdrant
├── agent/           # LangGraph ReAct graph + tools + prompts
├── extraction/      # financial figure extraction
├── validation/      # cross-document consistency checks
├── ratios/          # DSR, D/E, current ratio, 5C scoring
├── explainability/  # source-traced citations, FEATERS-aligned output
├── models/          # SQLAlchemy ORM models
├── schemas/         # Pydantic request/response schemas
└── main.py          # FastAPI app entry
```

Each domain folder maps directly to a step in the proposal's 6-step agent workflow.
