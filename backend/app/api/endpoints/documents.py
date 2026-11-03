"""Extração de texto de documentos enviados (currículo mestre e carta padrão)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_document_parser
from app.schemas.documents import DocumentExtractionResponse
from app.schemas.resume import ErrorResponse
from app.services.document_parser import DocumentParser

router = APIRouter(prefix="/api/v1/documents", tags=["Documentos"])


@router.post(
    "/extract",
    response_model=DocumentExtractionResponse,
    summary="Extrai o texto de um PDF, DOCX ou TXT",
    responses={
        400: {"model": ErrorResponse, "description": "Nenhum arquivo enviado"},
        413: {"model": ErrorResponse, "description": "Arquivo acima do limite (MAX_UPLOAD_MB)"},
        415: {"model": ErrorResponse, "description": "Formato não suportado"},
        422: {"model": ErrorResponse, "description": "Arquivo corrompido, com senha ou sem texto"},
    },
)
async def extract_document(
    file: Annotated[UploadFile, File(description="Currículo ou carta em PDF, DOCX ou TXT.")],
    parser: DocumentParser = Depends(get_document_parser),
) -> DocumentExtractionResponse:
    """
    Lê o arquivo e devolve o texto puro. Não chama a IA nem guarda o arquivo:
    o frontend mostra o texto num campo editável para o usuário revisar.
    """
    document = await parser.parse_upload(file)
    return DocumentExtractionResponse(**document.model_dump(), char_count=len(document.text))
