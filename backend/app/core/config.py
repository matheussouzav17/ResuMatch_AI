"""
Configuração central da aplicação.

Todas as configurações vêm de variáveis de ambiente (carregadas do arquivo
`.env` via python-dotenv). Nenhum segredo fica escrito no código.
"""

from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Carrega o .env para o ambiente do processo antes de ler as configurações.
load_dotenv()


class Settings(BaseSettings):
    """Configurações tipadas e validadas na inicialização do servidor."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Aplicação ---
    app_name: str = "ResuMatch AI API"
    app_version: str = "1.0.0"
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    # --- Anthropic / Claude ---
    anthropic_api_key: SecretStr = Field(..., description="Chave da API da Anthropic")
    claude_model: str = "claude-opus-5-5"
    claude_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    claude_max_tokens: int = Field(16000, ge=1024, le=64000)
    claude_timeout_seconds: float = Field(180.0, gt=0)
    claude_max_retries: int = Field(2, ge=0, le=5)

    # --- CORS ---
    # Aceita uma string separada por vírgulas no .env.
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    @field_validator("anthropic_api_key")
    @classmethod
    def _key_not_placeholder(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().strip()
        if not raw or raw == "sk-ant-...":
            raise ValueError(
                "ANTHROPIC_API_KEY não configurada. Copie .env.example para .env e preencha a chave."
            )
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância única (singleton) das configurações."""
    return Settings()
