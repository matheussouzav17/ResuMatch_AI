"""
Ponto de entrada da aplicação FastAPI.

Rodar localmente:
    uvicorn app.main:app --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.services.claude_service import ClaudeResumeService
from app.services.document_parser import DocumentParser
from app.services.job_scraper import JobScraper
from app.services.optimization_service import ResumeOptimizationService

settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cria os serviços (e seus clientes HTTP) uma única vez e os fecha no shutdown."""
    ai_service = ClaudeResumeService(settings)
    job_scraper = JobScraper(settings)
    app.state.document_parser = DocumentParser(max_bytes=settings.max_upload_bytes)
    app.state.job_scraper = job_scraper
    app.state.optimization_service = ResumeOptimizationService(ai_service, job_scraper)
    logging.getLogger(__name__).info("ResuMatch AI iniciado (modelo=%s)", settings.claude_model)
    yield
    await ai_service.close()
    await job_scraper.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API que adapta currículos para vagas específicas usando o Claude (Anthropic). "
        "Aceita documentos base em PDF, DOCX ou TXT e vagas em texto ou por link."
    ),
    lifespan=lifespan,
    # Em produção, a documentação interativa fica desligada.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

# CORS: libera as origens listadas em CORS_ORIGINS e, em desenvolvimento,
# qualquer porta de localhost (CORS_ORIGIN_REGEX).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_origin_regex_or_none,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Retry-After"],
)

register_exception_handlers(app)
app.include_router(router)

# Frontend estático: se a pasta ../frontend existir, ela é servida em /app/
# (mesma origem da API, então não depende de CORS).
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:
        return RedirectResponse(url="/app/")
