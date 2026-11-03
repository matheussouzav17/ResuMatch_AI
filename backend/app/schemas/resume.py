"""
Schemas Pydantic: contrato de entrada e saída da API.

Há dois grupos:
- Request/Response HTTP (o que o frontend envia e recebe).
- `AIOptimizationResult`: o formato estruturado que o Claude é obrigado a
  devolver (Structured Outputs). Ele é reaproveitado dentro da resposta HTTP.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.documents import JobSource

# Limites de tamanho (espelhados no frontend em assets/js/config.js).
RESUME_MIN, RESUME_MAX = 200, 30_000
JOB_MIN, JOB_MAX = 100, 20_000
COVER_LETTER_MAX = 10_000


# ---------------------------------------------------------------------------
# Requisição
# ---------------------------------------------------------------------------
class OutputLanguage(str, Enum):
    PT_BR = "pt-BR"
    EN = "en"
    ES = "es"


class OptimizeRequest(BaseModel):
    """
    Corpo de POST /api/v1/resume/optimize.

    A vaga pode vir como texto (`job_description`) ou como link (`job_url`).
    Se os dois forem enviados, o texto tem prioridade e o link fica só como
    referência de origem (é o que o frontend faz depois de importar e o
    usuário revisar a vaga).
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "master_resume": "Matheus Souza\nDesenvolvedor Python...\nExperiência: ...",
                "cover_letter_template": "Prezados, meu nome é Matheus...",
                "job_description": "Vaga: Desenvolvedor Backend Pleno\nRequisitos: Python, FastAPI, Docker...",
                "job_url": None,
                "language": "pt-BR",
                "include_cover_letter": True,
            }
        },
    )

    master_resume: str = Field(
        ...,
        min_length=RESUME_MIN,
        max_length=RESUME_MAX,
        description="Currículo mestre completo, em texto puro. Fonte de verdade da IA.",
    )
    cover_letter_template: str | None = Field(
        None,
        max_length=COVER_LETTER_MAX,
        description="Carta de apresentação padrão do candidato (opcional): referência de tom e estilo.",
    )
    job_description: str | None = Field(
        None,
        min_length=JOB_MIN,
        max_length=JOB_MAX,
        description="Descrição completa da vaga. Obrigatória se `job_url` não for enviado.",
    )
    job_url: HttpUrl | None = Field(
        None,
        description="Link público da vaga. Usado quando `job_description` não é enviado.",
    )
    language: OutputLanguage = Field(
        OutputLanguage.PT_BR, description="Idioma do currículo adaptado e da carta."
    )
    include_cover_letter: bool = Field(True, description="Gerar carta de apresentação.")

    @field_validator("master_resume")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("O campo não pode estar vazio.")
        return value

    @field_validator("cover_letter_template", "job_description", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        """Campo opcional enviado vazio ("" ou só espaços) é tratado como ausente."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _require_job_source(self) -> "OptimizeRequest":
        if self.job_description is None and self.job_url is None:
            raise ValueError("Envie a descrição da vaga (job_description) ou o link (job_url).")
        return self


class ResolvedOptimizeInput(BaseModel):
    """Entrada já resolvida (vaga em texto), pronta para o serviço de IA."""

    master_resume: str
    cover_letter_template: str | None
    job_description: str
    language: OutputLanguage
    include_cover_letter: bool


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


class JobOrigin(BaseModel):
    """De onde veio a descrição da vaga usada na geração."""

    type: Literal["text", "url"]
    url: str | None = None
    source: JobSource | None = Field(None, description="Como o texto foi extraído, quando veio de URL.")


class OptimizeResponse(AIOptimizationResult):
    """Resposta de POST /api/v1/resume/optimize: resultado da IA + metadados."""

    keyword_coverage: float = Field(
        description="Percentual (0-100) de palavras-chave da vaga presentes no currículo."
    )
    fidelity_warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Alertas da checagem automática de fidelidade: empresas, instituições ou anos "
            "do currículo adaptado que não foram encontrados no currículo mestre."
        ),
    )
    job_origin: JobOrigin
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
