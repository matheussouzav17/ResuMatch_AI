"""
Ponto de entrada da aplicação FastAPI.

Rodar localmente:
    uvicorn app.main:app --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.services.claude_service import ClaudeResumeService

settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cria o serviço (e o cliente HTTP da Anthropic) uma única vez e o fecha no shutdown."""
    app.state.resume_service = ClaudeResumeService(settings)
    logging.getLogger(__name__).info("ResuMatch AI iniciado (modelo=%s)", settings.claude_model)
    yield
    await app.state.resume_service.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API que adapta currículos para vagas específicas usando o Claude (Anthropic).",
    lifespan=lifespan,
    # Em produção, a documentação interativa fica desligada.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

# CORS: libera apenas as origens do frontend listadas em CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Retry-After"],
)

register_exception_handlers(app)
app.include_router(router)
