"""
Injeção de dependências das rotas.

Os serviços são criados uma única vez no startup (lifespan, em `main.py`) e
guardados em `app.state`. As rotas pedem o que precisam via `Depends`, o que
também facilita substituí-los por fakes nos testes
(`app.dependency_overrides`).
"""

from fastapi import Request

from app.services.document_parser import DocumentParser
from app.services.job_scraper import JobScraper
from app.services.optimization_service import ResumeOptimizationService


def get_optimization_service(request: Request) -> ResumeOptimizationService:
    return request.app.state.optimization_service


def get_document_parser(request: Request) -> DocumentParser:
    return request.app.state.document_parser


def get_job_scraper(request: Request) -> JobScraper:
    return request.app.state.job_scraper
