from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, applications, auth, cases, documents, history
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(applications.router, prefix="/api/applications", tags=["applications"])
app.include_router(history.router, prefix="/api/history", tags=["development-history"])
app.include_router(cases.router, prefix="/api/cases", tags=["company-cases"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
