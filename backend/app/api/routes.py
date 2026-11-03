"""
Registro das rotas HTTP (camada de controller).

Cada grupo de rotas fica em `app/api/endpoints/`. As rotas só recebem a
requisição validada, chamam o serviço e devolvem a resposta: nenhuma regra de
negócio ou chamada a SDK externa fica nelas.
"""

from fastapi import APIRouter

from app.api.endpoints import documents, jobs, resume, system

router = APIRouter()
router.include_router(system.router)
router.include_router(resume.router)
router.include_router(documents.router)
router.include_router(jobs.router)
