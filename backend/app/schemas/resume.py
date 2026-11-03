"""
Schemas Pydantic: contrato de entrada e saída da API.

Há dois grupos:
- Request/Response HTTP (o que o frontend envia e recebe).
- `AIOptimizationResult`: o formato estruturado que o Claude é obrigado a
  devolver (Structured Outputs). Ele é reaproveitado dentro da resposta HTTP.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Requisição
# ---------------------------------------------------------------------------
class OutputLanguage(str, Enum):
    PT_BR = "pt-BR"
    EN = "en"
    ES = "es"


class OptimizeRequest(BaseModel):
    """Corpo de POST /api/v1/resume/optimize."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "master_resume": "Matheus Souza\nDesenvolvedor Python...\nExperiência: ...",
                "job_description": "Vaga: Desenvolvedor Backend Pleno\nRequisitos: Python, FastAPI, Docker...",
                "language": "pt-BR",
                "include_cover_letter": True,
            }
        },
    )

    master_resume: str = Field(
        ...,
        min_length=200,
        max_length=30_000,
        description="Currículo mestre completo, em texto puro.",
    )
    job_description: str = Field(
        ...,
        min_length=100,
        max_length=20_000,
        description="Descrição completa da vaga.",
    )
    language: OutputLanguage = Field(
        OutputLanguage.PT_BR, description="Idioma do currículo adaptado e da carta."
    )
    include_cover_letter: bool = Field(True, description="Gerar carta de apresentação.")

    @field_validator("master_resume", "job_description")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("O campo não pode estar vazio.")
        return value


# ---------------------------------------------------------------------------
# Saída estruturada do Claude
# (Sem restrições numéricas como ge/le: o schema é enviado ao modelo e a
#  validação de faixa é feita depois, no serviço.)
# ---------------------------------------------------------------------------
class KeywordCategory(str, Enum):
    HARD_SKILL = "hard_skill"
    SOFT_SKILL = "soft_skill"
    TOOL = "tool"
    CERTIFICATION = "certification"
    DOMAIN = "domain"


class KeywordImportance(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class Keyword(BaseModel):
    term: str = Field(description="Palavra-chave exatamente como aparece na vaga.")
    category: KeywordCategory
    importance: KeywordImportance
    present_in_resume: bool = Field(
        description="True somente se o currículo mestre comprova esta competência."
    )
    evidence: str | None = Field(
        description="Trecho do currículo mestre que comprova a competência, ou null."
    )


class JobAnalysis(BaseModel):
    job_title: str
    seniority: str = Field(description="Ex.: estágio, júnior, pleno, sênior, não informado.")
    keywords: list[Keyword]


class MatchAnalysis(BaseModel):
    score: int = Field(description="Aderência de 0 a 100 entre currículo e vaga.")
    strengths: list[str] = Field(description="Pontos do candidato que atendem à vaga.")
    gaps: list[str] = Field(description="Requisitos da vaga sem evidência no currículo.")


class Experience(BaseModel):
    role: str
    company: str
    period: str
    bullets: list[str] = Field(description="Conquistas reescritas com verbos de ação e palavras-chave.")


class Education(BaseModel):
    degree: str
    institution: str
    period: str


class AdaptedResume(BaseModel):
    full_name: str
    headline: str = Field(description="Título profissional alinhado à vaga.")
    contact: list[str] = Field(description="Contatos copiados do currículo mestre.")
    professional_summary: str
    skills: list[str]
    experiences: list[Experience]
    education: list[Education]
    certifications: list[str]
    languages: list[str]


class AIOptimizationResult(BaseModel):
    """Formato exato que o Claude deve devolver."""

    job_analysis: JobAnalysis
    match: MatchAnalysis
    adapted_resume: AdaptedResume
    cover_letter: str | None = Field(description="Carta de apresentação, ou null se não solicitada.")
    suggestions: list[str] = Field(
        description="Dicas para o candidato (ex.: lacunas a estudar). Nunca inventar dados."
    )


# ---------------------------------------------------------------------------
# Resposta HTTP
# ---------------------------------------------------------------------------
class UsageMetadata(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    processing_time_ms: int


class OptimizeResponse(AIOptimizationResult):
    """Resposta de POST /api/v1/resume/optimize: resultado da IA + metadados."""

    keyword_coverage: float = Field(
        description="Percentual (0-100) de palavras-chave da vaga presentes no currículo."
    )
    metadata: UsageMetadata


class HealthResponse(BaseModel):
    status: str
    version: str
    model: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    """Formato padrão de erro (documentado no OpenAPI)."""

    error: ErrorDetail
