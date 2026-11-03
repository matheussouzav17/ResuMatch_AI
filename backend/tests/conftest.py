"""
Fixtures compartilhadas. Nenhum teste chama a API real da Anthropic: o
serviço de IA é trocado por um fake via `app.dependency_overrides`.
"""

import os

# Precisa existir antes de importar a aplicação (Settings valida na criação).
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")

import pytest
from fastapi.testclient import TestClient

from app.main import app

MASTER_RESUME = """\
Matheus Souza
matheus@email.com | linkedin.com/in/matheus

Resumo: Desenvolvedor Python com experiência em APIs REST.

Experiência
Desenvolvedor Backend - Empresa Alfa (2022 - 2025)
- Criei APIs com FastAPI e PostgreSQL.
- Automatizei deploys com Docker.

Formação
Bacharelado em Ciência da Computação - Universidade Federal Beta (2018 - 2021)
"""

JOB_DESCRIPTION = (
    "Vaga: Desenvolvedor Backend Pleno. Requisitos: Python, FastAPI, Docker, PostgreSQL, "
    "Kubernetes. Diferenciais: AWS e mensageria."
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
