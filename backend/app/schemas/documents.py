"""
Schemas das rotas de extração de texto: documentos enviados (PDF/DOCX/TXT)
e vagas importadas por URL.

Essas rotas existem para o usuário revisar o texto extraído antes de gastar
créditos de IA: o frontend mostra o resultado num campo editável.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class ExtractedDocument(BaseModel):
    """Resultado interno do parser de documentos."""

    filename: str
    file_type: DocumentType
    text: str
    page_count: int | None = None


class DocumentExtractionResponse(ExtractedDocument):
    """Resposta de POST /api/v1/documents/extract."""

    char_count: int = Field(description="Quantidade de caracteres do texto extraído.")


class JobSource(str, Enum):
    STRUCTURED_DATA = "structured_data"  # JSON-LD schema.org/JobPosting (mais confiável)
    PAGE_TEXT = "page_text"  # texto visível da página (pode conter ruído)


class JobExtractionRequest(BaseModel):
    """Corpo de POST /api/v1/jobs/extract."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"url": "https://empresa.gupy.io/jobs/123456"}},
    )

    url: HttpUrl = Field(description="Link público do anúncio da vaga (http ou https).")


class ExtractedJob(BaseModel):
    """Vaga extraída de uma página web."""

    url: str = Field(description="URL informada pelo usuário.")
    final_url: str = Field(description="URL final, depois de redirecionamentos.")
    title: str | None = None
    company: str | None = None
    text: str = Field(description="Descrição da vaga em texto puro.")
    source: JobSource


class JobExtractionResponse(ExtractedJob):
    """Resposta de POST /api/v1/jobs/extract."""

    char_count: int
