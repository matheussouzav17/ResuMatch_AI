"""Importação de vagas a partir do link do anúncio."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_job_scraper
from app.schemas.documents import JobExtractionRequest, JobExtractionResponse
from app.schemas.resume import ErrorResponse
from app.services.job_scraper import JobScraper

router = APIRouter(prefix="/api/v1/jobs", tags=["Vagas"])


@router.post(
    "/extract",
    response_model=JobExtractionResponse,
    summary="Extrai a descrição de uma vaga a partir da URL",
    responses={
        400: {"model": ErrorResponse, "description": "URL inválida"},
        422: {
            "model": ErrorResponse,
            "description": "Site bloqueou a leitura, exige login ou não tem a vaga no HTML",
        },
    },
)
async def extract_job(
    payload: JobExtractionRequest,
    scraper: JobScraper = Depends(get_job_scraper),
) -> JobExtractionResponse:
    """
    Busca a página da vaga e devolve título, empresa e descrição em texto.
    Usa os dados estruturados `schema.org/JobPosting` quando existem e, se não,
    o texto visível da página. Em caso de falha (`JOB_URL_UNREADABLE`), o
    usuário deve colar a descrição manualmente.
    """
    job = await scraper.extract(str(payload.url))
    return JobExtractionResponse(**job.model_dump(), char_count=len(job.text))
