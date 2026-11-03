"""
Serviço de IA: única camada que conhece a SDK da Anthropic.

Responsabilidades:
- Criar e reaproveitar o cliente assíncrono da Anthropic.
- Enviar currículo + carta padrão + vaga ao Claude com Structured Outputs,
  garantindo que a resposta siga exatamente o schema `AIOptimizationResult`.
- Traduzir erros da SDK em exceções de domínio (o mapeamento para HTTP fica em
  `app/core/exceptions.py`).
"""

import logging
import time
from dataclasses import dataclass

import anthropic

from app.core.config import Settings
from app.core.exceptions import (
    AIConfigurationError,
    AIRateLimitError,
    AIResponseError,
    AIServiceUnavailableError,
    InvalidInputError,
)
from app.schemas.resume import AIOptimizationResult, ResolvedOptimizeInput, UsageMetadata
from app.services.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

# Modelos que aceitam o fallback automático do servidor quando um classificador
# de segurança recusa a requisição (stop_reason == "refusal").
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


@dataclass(frozen=True, slots=True)
class AIGeneration:
    """Resultado bruto da IA + métricas de uso."""

    result: AIOptimizationResult
    usage: UsageMetadata


class ClaudeResumeService:
    """Orquestra a otimização de currículos via API do Claude."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # O cliente já faz retry automático (com backoff) em 408/409/429/5xx e
        # falhas de conexão; `max_retries` controla quantas tentativas.
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.claude_timeout_seconds,
            max_retries=settings.claude_max_retries,
        )

    async def close(self) -> None:
        """Fecha o pool de conexões HTTP (chamado no shutdown da aplicação)."""
        await self._client.close()

    async def generate(self, request: ResolvedOptimizeInput) -> AIGeneration:
        """Envia currículo, carta padrão e vaga ao Claude e devolve o resultado estruturado."""
        settings = self._settings
        started = time.perf_counter()

        user_prompt = build_user_prompt(
            master_resume=request.master_resume,
            job_description=request.job_description,
            language=request.language.value,
            include_cover_letter=request.include_cover_letter,
            cover_letter_template=request.cover_letter_template,
        )

        # Fallback automático só é enviado para modelos que o suportam.
        extra: dict = {}
        if settings.claude_model in _FALLBACK_MODELS:
            extra = {"betas": [_FALLBACK_BETA], "fallbacks": "default"}

        try:
            response = await self._client.beta.messages.parse(
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                # Raciocínio adaptativo + nível de esforço configurável.
                thinking={"type": "adaptive"},
                output_config={"effort": settings.claude_effort},
                # Structured Outputs: a resposta é validada contra o schema Pydantic.
                output_format=AIOptimizationResult,
                **extra,
            )

        # A ordem importa: classes mais específicas primeiro.
        except anthropic.RateLimitError as exc:
            retry_after = _parse_retry_after(exc)
            logger.warning("Rate limit da Anthropic atingido (retry-after=%s)", retry_after)
            raise AIRateLimitError(
                "Muitas requisições para a IA no momento. Aguarde alguns segundos e tente novamente.",
                retry_after=retry_after,
            ) from exc

        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            logger.error("Falha de autenticação na Anthropic: %s", exc.message)
            raise AIConfigurationError(
                "O serviço de IA está mal configurado (chave de API inválida ou sem permissão)."
            ) from exc

        except anthropic.NotFoundError as exc:
            logger.error("Modelo ou endpoint não encontrado: %s", exc.message)
            raise AIConfigurationError(
                f"Modelo '{settings.claude_model}' não encontrado. Verifique CLAUDE_MODEL."
            ) from exc

        except (anthropic.BadRequestError, anthropic.RequestTooLargeError) as exc:
            logger.warning("Requisição rejeitada pela Anthropic: %s", exc.message)
            raise InvalidInputError(
                "A IA rejeitou a requisição. Verifique o tamanho e o conteúdo dos textos enviados.",
                details=exc.message,
            ) from exc

        except anthropic.APITimeoutError as exc:
            logger.error("Timeout ao chamar a Anthropic")
            raise AIServiceUnavailableError(
                "A IA demorou demais para responder. Tente novamente."
            ) from exc

        except anthropic.APIConnectionError as exc:
            logger.error("Erro de conexão com a Anthropic: %s", exc)
            raise AIServiceUnavailableError(
                "Não foi possível conectar ao serviço de IA. Tente novamente em instantes."
            ) from exc

        except anthropic.APIStatusError as exc:
            # 5xx (incluindo 529 "overloaded") e demais códigos não tratados acima.
            logger.error("Erro da API da Anthropic (%s): %s", exc.status_code, exc.message)
            if exc.status_code >= 500:
                raise AIServiceUnavailableError(
                    "O serviço de IA está instável no momento. Tente novamente em instantes."
                ) from exc
            raise AIResponseError("Erro inesperado retornado pelo serviço de IA.") from exc

        except anthropic.APIResponseValidationError as exc:
            logger.error("Resposta da IA fora do schema esperado: %s", exc)
            raise AIResponseError("A IA retornou dados em formato inesperado. Tente novamente.") from exc

        # --- Validação do resultado ---
        if response.stop_reason == "refusal":
            raise AIResponseError(
                "A IA recusou processar este conteúdo. Revise os textos enviados."
            )
        if response.stop_reason == "max_tokens":
            raise AIResponseError(
                "A resposta da IA foi cortada por exceder o limite de tamanho. "
                "Tente um currículo ou vaga mais curtos, ou aumente CLAUDE_MAX_TOKENS."
            )

        result = response.parsed_output
        if result is None:
            raise AIResponseError("A IA não retornou um resultado estruturado. Tente novamente.")

        # Pós-processamento determinístico (não depende do modelo).
        result.match.score = max(0, min(100, result.match.score))
        if not request.include_cover_letter:
            result.cover_letter = None

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "Currículo otimizado em %dms (modelo=%s, in=%d, out=%d tokens)",
            elapsed_ms,
            response.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        return AIGeneration(
            result=result,
            usage=UsageMetadata(
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                processing_time_ms=elapsed_ms,
            ),
        )


def _parse_retry_after(exc: anthropic.APIStatusError) -> int:
    """Lê o header Retry-After da Anthropic (padrão: 30s)."""
    try:
        return max(1, int(float(exc.response.headers.get("retry-after", "30"))))
    except (TypeError, ValueError):
        return 30
