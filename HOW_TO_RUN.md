# How to Run

## Prerequisites

- Install and start Docker Desktop.
- Ensure `backend/.env` contains a valid `GEMINI_API_KEY`.
- Run commands from the project root: `C:\Users\Dell\OneDrive - Asia Pacific University\APU SUBJECT\Year 3\FYP\System`.

## Start the Entire System

```powershell
docker compose up --build
```

This single command starts:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API documentation: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- Qdrant: http://localhost:6333

Use `Ctrl+C` to stop the foreground process.

## Start in the Background

```powershell
docker compose up -d --build
```

View all logs:

```powershell
docker compose logs -f
```

View only application logs:

```powershell
docker compose logs -f frontend backend
```

## Stop the Entire System

```powershell
docker compose down
```

## Check Service Status

```powershell
docker compose ps
```

All application containers should show `Up`; the backend, PostgreSQL, and Redis should become `healthy`.

## Rebuild After Dependency Changes

```powershell
docker compose up -d --build --force-recreate
```

Normal source-code changes are mounted into the development containers. Rebuilding is mainly required after changing `backend/pyproject.toml`, `frontend/package.json`, or either Dockerfile.

The backend does not hot-reload. After Python source changes, run `docker compose restart backend`. If frontend file watching misses Windows-mounted edits, run `docker compose restart frontend`, then refresh the browser.

## Review Citations and Original PDFs

Upload a package again after the September 2026 citation update. Older runs cannot recover originals that were already deleted, and their page references are not treated as verified.

- Citations display as numbered sources, with original filenames and verified page numbers in tooltips and the **Sources cited or retrieved** list.
- Click a source to compare extracted evidence with the original page preview. Select another supporting page when the evidence spans multiple pages, or open the original PDF.
- Successful analyses archive PDFs and minimal source metadata in `data/source_documents/` when using Docker. A backend started directly on the host defaults to `backend/data/source_documents/`. Both locations are ignored by Git; `SOURCE_DOCUMENTS_DIR` overrides the directory.
- Original PDFs remain on disk after upload cleanup and container restarts. Job/result history is still in memory; source retention is not yet full application persistence.
- Use synthetic or appropriately authorised documents. This local prototype has no access-control layer for the source endpoints and is not ready for public exposure.

## Review RAG Evidence

### Dashboard navigation

- **Overview** opens by default: processing/retrieval status, a provisional headline, recommended human checks and expandable 5C dimensions. Full assessment text is collapsed until requested.
- **Documents & Evidence** contains the package inventory, searchable source catalogue and retrieval audit.
- **Technical Details** contains calculated metrics, node timings and diagnostic messages.
- Consecutive citations are grouped behind **View N sources**, preserving each individual source link. Selecting a source opens a right-side panel with supporting pages and the original PDF. Press Escape or Close to return.
- These are presentation changes only: model output, ratings, retrieval and calculations are unchanged.

- Re-upload packages after the RAG update to create current application/document-kind/embedding-space metadata. Do not delete the collection.
- Expand the retrieval panel to inspect queries, selected excerpts, pages, similarity scores, warnings and consuming nodes.
- Local embeddings use lexical feature hashing, not a semantic model. Similarity is not confidence or creditworthiness; thresholds are not yet calibrated on held-out queries.
- Forecast evidence is labelled separately from actual results. Empty retrieval is not proof of no risk.
- Optional backend settings: `RAG_SCORE_THRESHOLD=0.12`, `RAG_RESULTS_PER_QUERY=3`, `RAG_CHUNK_CHARS=1800`, `RAG_CONTEXT_CHARS=20000`. Restart the backend after changes.
- Document search requires `application_id`. UI chunk lookup sends this scope; legacy unscoped lookup remains supported and is not authenticated access.
- Retrieval audit data remains in memory; durable job/result history is not implemented.

Verification (2026-09-26): Docker is running again. Browser QA processed 32 synthetic PDFs / 337 pages and verified the redesigned navigation, source search, citation groups and PDF page switching. Retrieval remained partial with seven excerpts. UI verification does not establish the correctness of model claims or complete supporting-document coverage. No factory reset or data deletion is required.
