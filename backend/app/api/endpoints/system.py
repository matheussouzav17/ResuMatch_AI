"""Rotas de sistema (não consomem a API do Claude)."""

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.resume import HealthResponse

router = APIRouter(tags=["Sistema"])


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Verifica se a API está no ar."""
    return HealthResponse(status="ok", version=settings.app_version, model=settings.claude_model)
