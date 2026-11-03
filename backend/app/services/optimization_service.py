"""
Orquestrador do caso de uso "otimizar currículo para uma vaga".

Junta as peças sem que uma conheça a outra:
1. Resolve a vaga: usa o texto enviado ou extrai do link (`JobScraper`).
2. Gera o conteúdo com a IA (`ClaudeResumeService`).
3. Pós-processa de forma determinística: cobertura de palavras-chave e
   checagem de fidelidade contra o currículo mestre.
"""

import logging

from app.schemas.resume import (
    AIOptimizationResult,
    JobOrigin,
    OptimizeRequest,
    OptimizeResponse,
    ResolvedOptimizeInput,
)
from app.services.claude_service import ClaudeResumeService
from app.services.fidelity import check_fidelity
from app.services.job_scraper import JobScraper

logger = logging.getLogger(__name__)


class ResumeOptimizationService:
    def __init__(self, ai: ClaudeResumeService, scraper: JobScraper) -> None:
        self._ai = ai
        self._scraper = scraper

    async def optimize(self, request: OptimizeRequest) -> OptimizeResponse:
        job_url = str(request.job_url) if request.job_url else None

        if request.job_description:
            job_text = request.job_description
            origin = JobOrigin(type="url" if job_url else "text", url=job_url)
        else:
            extracted = await self._scraper.extract(job_url)
            job_text = extracted.text
            origin = JobOrigin(type="url", url=job_url, source=extracted.source)

        generation = await self._ai.generate(
            ResolvedOptimizeInput(
                master_resume=request.master_resume,
                cover_letter_template=request.cover_letter_template,
                job_description=job_text,
                language=request.language,
                include_cover_letter=request.include_cover_letter,
            )
        )
        result = generation.result

        warnings = check_fidelity(result.adapted_resume, request.master_resume)
        if warnings:
            logger.warning("Checagem de fidelidade gerou %d alerta(s)", len(warnings))

        return OptimizeResponse(
            **result.model_dump(),
            keyword_coverage=keyword_coverage(result),
            fidelity_warnings=warnings,
            job_origin=origin,
            metadata=generation.usage,
        )


def keyword_coverage(result: AIOptimizationResult) -> float:
    """Percentual de palavras-chave da vaga comprovadas pelo currículo."""
    keywords = result.job_analysis.keywords
    if not keywords:
        return 0.0
    present = sum(1 for kw in keywords if kw.present_in_resume)
    return round(present / len(keywords) * 100, 1)
