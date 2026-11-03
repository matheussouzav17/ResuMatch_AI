"""
Exceções de domínio e handlers globais.

A camada de serviço lança exceções de domínio (sem conhecer HTTP); aqui elas
são traduzidas em respostas JSON com o código HTTP adequado e um formato de
erro único que o frontend pode tratar sempre do mesmo jeito:

    {"error": {"code": "RATE_LIMITED", "message": "...", "details": ...}}
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ResuMatchError(Exception):
    """Exceção base da aplicação."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, retry_after: int | None = None, details: object = None):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.details = details


class InvalidInputError(ResuMatchError):
    """Entrada rejeitada pela API do Claude (ex.: payload grande demais)."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_INPUT"


class AIRateLimitError(ResuMatchError):
    """Limite de requisições da Anthropic atingido."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMITED"


class AIServiceUnavailableError(ResuMatchError):
    """Falha de conexão, timeout ou instabilidade da API do Claude."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "AI_UNAVAILABLE"


class AIConfigurationError(ResuMatchError):
    """Chave inválida, sem permissão ou modelo inexistente (erro do servidor, não do usuário)."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "AI_CONFIGURATION_ERROR"


class AIResponseError(ResuMatchError):
    """O modelo respondeu, mas a resposta não pôde ser usada (truncada, recusada, inválida)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "AI_INVALID_RESPONSE"


def _error_body(code: str, message: str, details: object = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    """Registra os handlers globais na aplicação."""

    @app.exception_handler(ResuMatchError)
    async def _handle_domain_error(_: Request, exc: ResuMatchError) -> JSONResponse:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Payload inválido -> 400 com a lista de campos problemáticos.
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"] if part != "body"),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_body("VALIDATION_ERROR", "Dados de entrada inválidos.", details),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Nunca vaza stack trace para o cliente; o detalhe fica no log.
        logger.exception("Erro inesperado: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "Erro interno inesperado. Tente novamente."),
        )
