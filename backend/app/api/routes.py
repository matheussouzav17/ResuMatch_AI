"""
Rotas HTTP (camada de controller).

As rotas só recebem a requisição validada, chamam o serviço e devolvem a
resposta. Nenhuma regra de negócio ou chamada à SDK fica aqui.
"""

from fastapi import APIRouter, Depends, Request, status

from app.core.config import Settings, get_settings
from app.schemas.resume import (
    ErrorResponse,
    HealthResponse,
    OptimizeRequest,
    OptimizeResponse,
)
from app.services.claude_service import ClaudeResumeService

router = APIRouter()


def get_resume_service(request: Request) -> ClaudeResumeService:
    """Injeção de dependência: devolve o serviço criado no startup (lifespan)."""
    return request.app.state.resume_service


@router.get("/health", response_model=HealthResponse, tags=["Sistema"])
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Verifica se a API está no ar (não consome a API do Claude)."""
    return HealthResponse(status="ok", version=settings.app_version, model=settings.claude_model)


@router.post(
    "/api/v1/resume/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    tags=["Currículo"],
    summary="Adapta o currículo mestre para uma vaga (otimização ATS)",
    responses={
        400: {"model": ErrorResponse, "description": "Payload inválido"},
        429: {"model": ErrorResponse, "description": "Limite de requisições da IA"},
        500: {"model": ErrorResponse, "description": "Erro interno ou de configuração"},
        502: {"model": ErrorResponse, "description": "Resposta inválida da IA"},
        503: {"model": ErrorResponse, "description": "IA indisponível"},
    },
)
async def optimize_resume(
    payload: OptimizeRequest,
    service: ClaudeResumeService = Depends(get_resume_service),
) -> OptimizeResponse:
    """
    Recebe o currículo mestre e a descrição da vaga e devolve:
    análise de palavras-chave, score de aderência, currículo adaptado,
    carta de apresentação (opcional) e sugestões.
    """
    return await service.optimize_resume(payload)
