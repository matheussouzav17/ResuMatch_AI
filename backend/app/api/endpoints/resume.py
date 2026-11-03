"""
Otimização de currículo (o caso de uso principal).

Duas formas de envio, com o mesmo resultado:
- `POST /api/v1/resume/optimize`: JSON com os textos (usado pelo frontend,
  que já extraiu e mostrou o texto dos arquivos para revisão).
- `POST /api/v1/resume/optimize/upload`: multipart/form-data, aceitando os
  documentos como arquivo (`UploadFile`) ou texto. Útil para integrações e
  para testar direto no Swagger.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.dependencies import get_document_parser, get_optimization_service
from app.schemas.resume import ErrorResponse, OptimizeRequest, OptimizeResponse, OutputLanguage
from app.services.document_parser import DocumentParser
from app.services.optimization_service import ResumeOptimizationService

router = APIRouter(prefix="/api/v1/resume", tags=["Currículo"])

_ERRORS = {
    400: {"model": ErrorResponse, "description": "Payload inválido"},
    422: {"model": ErrorResponse, "description": "Documento ou link da vaga ilegível"},
    429: {"model": ErrorResponse, "description": "Limite de requisições da IA"},
    500: {"model": ErrorResponse, "description": "Erro interno ou de configuração"},
    502: {"model": ErrorResponse, "description": "Resposta inválida da IA"},
    503: {"model": ErrorResponse, "description": "IA indisponível"},
}


@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Adapta o currículo mestre para uma vaga (JSON)",
    responses=_ERRORS,
)
async def optimize_resume(
    payload: OptimizeRequest,
    service: ResumeOptimizationService = Depends(get_optimization_service),
) -> OptimizeResponse:
    """
    Recebe o currículo mestre, a carta padrão (opcional) e a vaga (texto ou
    link) e devolve: análise de palavras-chave, score de aderência, currículo
    adaptado, carta personalizada, sugestões e alertas de fidelidade.
    """
    return await service.optimize(payload)


@router.post(
    "/optimize/upload",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Adapta o currículo mestre para uma vaga (upload de arquivos)",
    responses={
        **_ERRORS,
        413: {"model": ErrorResponse, "description": "Arquivo acima do limite"},
        415: {"model": ErrorResponse, "description": "Formato de arquivo não suportado"},
    },
)
async def optimize_resume_upload(
    master_resume_file: Annotated[
        UploadFile | None, File(description="Currículo mestre em PDF, DOCX ou TXT.")
    ] = None,
    master_resume: Annotated[
        str | None, Form(description="Currículo mestre em texto (alternativa ao arquivo).")
    ] = None,
    cover_letter_file: Annotated[
        UploadFile | None, File(description="Carta de apresentação padrão (opcional).")
    ] = None,
    cover_letter_template: Annotated[
        str | None, Form(description="Carta padrão em texto (alternativa ao arquivo).")
    ] = None,
    job_description: Annotated[str | None, Form(description="Descrição da vaga em texto.")] = None,
    job_url: Annotated[str | None, Form(description="Link da vaga (se não enviar o texto).")] = None,
    language: Annotated[OutputLanguage, Form()] = OutputLanguage.PT_BR,
    include_cover_letter: Annotated[bool, Form()] = True,
    parser: DocumentParser = Depends(get_document_parser),
    service: ResumeOptimizationService = Depends(get_optimization_service),
) -> OptimizeResponse:
    """Mesmo resultado de `/optimize`; arquivos têm prioridade sobre o texto do mesmo campo."""
    if _has_file(master_resume_file):
        master_resume = (await parser.parse_upload(master_resume_file)).text
    if _has_file(cover_letter_file):
        cover_letter_template = (await parser.parse_upload(cover_letter_file)).text

    try:
        payload = OptimizeRequest(
            master_resume=master_resume or "",
            cover_letter_template=cover_letter_template,
            job_description=job_description,
            job_url=job_url or None,
            language=language,
            include_cover_letter=include_cover_letter,
        )
    except ValidationError as exc:
        # Reaproveita o handler global: vira 400 VALIDATION_ERROR com a lista de campos.
        raise RequestValidationError(exc.errors()) from exc

    return await service.optimize(payload)


def _has_file(upload: UploadFile | None) -> bool:
    """Swagger e alguns clientes mandam o campo de arquivo vazio quando nada é selecionado."""
    return upload is not None and bool(upload.filename)
