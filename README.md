# FYP — Agentic AI for Explainable SME Loan Document Analysis

Final-Year Project · Asia Pacific University (Malaysia) · BSc (Hons) IT — FinTech
Tran Quang Dat (TP079959) · 2026

An agentic AI system that ingests Malaysian SME loan document packages
(bank statements, audited financials, SSM registration, tax returns),
cross-validates financial figures across documents using a LangGraph ReAct
agent, and produces a source-traced, BNM FEATERS-aligned risk summary for
the loan officer.

> The system does **not** make credit decisions. It assists human loan
> officers by automating extraction, cross-validation, and explanation.

See [`docs/FYP_Proposal.md`](docs/FYP_Proposal.md) for the full proposal and
[`docs/FYP_Context.md`](docs/FYP_Context.md) for background and decisions.

---

## Repo layout

```
FYP/
├── backend/             # FastAPI + LangGraph + Qdrant client (uv-managed)
│   ├── app/
│   │   ├── api/         # HTTP routes
│   │   ├── core/        # config, db, llm provider abstraction
│   │   ├── ingestion/   # PyMuPDF / pdfplumber / Tesseract OCR
│   │   ├── agent/       # LangGraph ReAct graph + tools
│   │   ├── extraction/  # financial figure extraction
│   │   ├── validation/  # cross-document checks
│   │   ├── ratios/      # DSR, D/E, 5C scoring
│   │   ├── explainability/  # source-traced citations
│   │   ├── models/      # SQLAlchemy ORM
│   │   └── schemas/     # Pydantic DTOs
│   ├── tests/
│   └── alembic/
├── frontend/            # SvelteKit loan-officer dashboard (placeholder)
├── infra/docker/        # extra container assets (init SQL, etc.)
├── data/                # sample documents (gitignored)
├── docs/                # proposal, context, design notes
└── docker-compose.yml   # full stack: backend + frontend + postgres + redis + qdrant
```

---

## Tech stack

| Layer | Tool | Notes |
|---|---|---|
| Agent | LangGraph (ReAct) | Same framework used at Kollect internship |
| LLM | Google Gemini API (Flash, free tier) | Wrapped behind provider-agnostic `app.core.llm` |
| Doc parsing | PyMuPDF + pdfplumber + Tesseract OCR | The genuinely new research area |
| Vector DB | Qdrant (self-hosted) | |
| Backend | FastAPI + SQLAlchemy + Alembic | uv for dependency management |
| Frontend | SvelteKit | |
| Data stores | PostgreSQL 16, Redis 7 | |
| Infra | Docker Compose | localhost demo |

---

## Local development

### Prerequisites
- Docker Desktop
- [`uv`](https://docs.astral.sh/uv/) for the backend
- Node 20+ for the frontend (once initialised)

### Bring up the stack

```bash
# 1. Configure secrets
cp backend/.env.example backend/.env
# fill in GEMINI_API_KEY etc.

# 2. Infra only (postgres + redis + qdrant)
docker compose up -d postgres redis qdrant

# 3. Backend (host, with hot reload)
cd backend
uv sync
uv run uvicorn app.main:app --reload

# 4. Or run everything containerised
docker compose up --build
```

The backend exposes:
- Swagger UI → http://localhost:8000/docs
- Health    → http://localhost:8000/health

### Tests

```bash
cd backend
uv run pytest
```

---

## Roadmap (mapped to proposal timeline)

| Phase | Folder mostly touched |
|---|---|
| 1 — Research & Design | `docs/` |
| 2 — Document Pipeline | `backend/app/ingestion/` |
| 3 — Agent Development | `backend/app/agent/`, `extraction/`, `validation/`, `ratios/` |
| 4 — Explainability    | `backend/app/explainability/` |
| 5 — Dashboard         | `frontend/` |
| 6 — Evaluation        | `backend/tests/`, `docs/evaluation/` |
| 7 — Write-up          | `docs/` |
