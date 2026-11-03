# ResuMatch AI: Backend

API em FastAPI que recebe um **currículo mestre** e uma **descrição de vaga**, envia ao Claude (Anthropic) com engenharia de prompt focada em ATS e devolve um JSON estruturado com análise de palavras-chave, score de aderência, currículo adaptado e carta de apresentação.

## Estrutura

```
resumatch-backend/
├── app/
│   ├── main.py                  # Cria o app, CORS, lifespan, registra rotas e handlers
│   ├── api/
│   │   └── routes.py            # Controllers: /health e /api/v1/resume/optimize
│   ├── core/
│   │   ├── config.py            # Configurações via .env (python-dotenv + pydantic-settings)
│   │   └── exceptions.py        # Exceções de domínio -> códigos HTTP + formato de erro único
│   ├── schemas/
│   │   └── resume.py            # Models Pydantic de requisição, resposta e saída da IA
│   └── services/
│       ├── claude_service.py    # Única camada que conhece a SDK da Anthropic
│       └── prompts.py           # System prompt (anti-alucinação + ATS) e prompt do usuário
├── .env.example
├── .gitignore
└── requirements.txt
```

**Fluxo:** `routes.py` valida o payload (Pydantic) → `claude_service.py` chama o Claude com *Structured Outputs* (a resposta é validada contra o schema `AIOptimizationResult`) → erros da SDK viram exceções de domínio → `exceptions.py` converte em HTTP.

## Como rodar localmente (Windows / PowerShell)

Pré-requisito: Python 3.11 ou superior.

```powershell
cd resumatch-backend

# 1. Ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Linux/macOS: source .venv/bin/activate

# 2. Dependências
pip install -r requirements.txt

# 3. Chave da API
copy .env.example .env            # Linux/macOS: cp .env.example .env
```

Abra o `.env` e troque `ANTHROPIC_API_KEY=sk-ant-...` pela sua chave, criada em <https://console.anthropic.com/settings/keys> (é preciso ter créditos na conta). O `.env` está no `.gitignore`, então a chave nunca vai para o GitHub.

```powershell
# 4. Subir o servidor
uvicorn app.main:app --reload --port 8000
```

- Documentação interativa (Swagger): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

> Se o PowerShell bloquear o `Activate.ps1`, rode uma vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | (obrigatória) | Chave da API da Anthropic |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Modelo do Claude |
| `CLAUDE_EFFORT` | `medium` | Esforço de raciocínio: `low`, `medium`, `high`, `xhigh`, `max` |
| `CLAUDE_MAX_TOKENS` | `16000` | Limite de tokens da resposta |
| `CLAUDE_TIMEOUT_SECONDS` | `180` | Timeout por chamada |
| `CLAUDE_MAX_RETRIES` | `2` | Retentativas automáticas da SDK (429, 5xx, rede) |
| `CORS_ORIGINS` | `http://localhost:5500,...` | Origens do frontend, separadas por vírgula |
| `ENVIRONMENT` | `development` | Em `production`, `/docs` é desativado |

## Contrato da API

### `POST /api/v1/resume/optimize`

**Requisição**

```json
{
  "master_resume": "texto do currículo (200 a 30.000 caracteres)",
  "job_description": "texto da vaga (100 a 20.000 caracteres)",
  "language": "pt-BR",
  "include_cover_letter": true
}
```

`language` aceita `pt-BR`, `en` ou `es`.

**Resposta 200**

```json
{
  "job_analysis": {
    "job_title": "Desenvolvedor Backend Pleno",
    "seniority": "pleno",
    "keywords": [
      {
        "term": "FastAPI",
        "category": "tool",
        "importance": "required",
        "present_in_resume": true,
        "evidence": "Desenvolvi APIs REST com FastAPI..."
      }
    ]
  },
  "match": { "score": 78, "strengths": ["..."], "gaps": ["Kubernetes"] },
  "adapted_resume": {
    "full_name": "...",
    "headline": "...",
    "contact": ["email@exemplo.com", "linkedin.com/in/..."],
    "professional_summary": "...",
    "skills": ["Python", "FastAPI"],
    "experiences": [
      { "role": "...", "company": "...", "period": "...", "bullets": ["..."] }
    ],
    "education": [{ "degree": "...", "institution": "...", "period": "..." }],
    "certifications": [],
    "languages": []
  },
  "cover_letter": "texto ou null",
  "suggestions": ["..."],
  "keyword_coverage": 66.7,
  "metadata": {
    "model": "claude-opus-5-5",
    "input_tokens": 3120,
    "output_tokens": 2480,
    "processing_time_ms": 41250
  }
}
```

`category`: `hard_skill`, `soft_skill`, `tool`, `certification`, `domain`. `importance`: `required`, `preferred`. `keyword_coverage` é calculado no backend (não pelo modelo).

**Erros:** sempre no formato

```json
{ "error": { "code": "RATE_LIMITED", "message": "mensagem amigável", "details": null } }
```

| HTTP | `code` | Quando |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Campos ausentes, curtos/longos demais ou extras (`details` lista os campos) |
| 400 | `INVALID_INPUT` | A API do Claude rejeitou o conteúdo |
| 429 | `RATE_LIMITED` | Limite da Anthropic (header `Retry-After` incluído) |
| 500 | `AI_CONFIGURATION_ERROR` | Chave inválida, sem permissão ou modelo inexistente |
| 500 | `INTERNAL_ERROR` | Erro inesperado |
| 502 | `AI_INVALID_RESPONSE` | Resposta cortada, recusada ou fora do schema |
| 503 | `AI_UNAVAILABLE` | Timeout, falha de conexão ou API sobrecarregada |

### `GET /health`

```json
{ "status": "ok", "version": "1.0.0", "model": "claude-opus-5-5" }
```

## Decisões de projeto

- **Fidelidade aos dados:** o system prompt proíbe inventar métricas, cargos, datas ou tecnologias; requisitos sem evidência vão para `gaps`, nunca para o currículo. Cada palavra-chave marcada como presente traz o trecho do currículo que a comprova (`evidence`), o que permite auditar a IA.
- **Structured Outputs:** a resposta do Claude é forçada a seguir o schema Pydantic, então o frontend nunca recebe JSON quebrado.
- **Proteção contra prompt injection:** currículo e vaga vão entre tags XML e o prompt instrui o modelo a tratá-los como dados.
- **Fallback de recusa:** em modelos compatíveis, a requisição usa o fallback automático do servidor da Anthropic caso um classificador de segurança recuse o conteúdo.
- **Cliente único:** o `AsyncAnthropic` é criado uma vez no startup (lifespan) e reaproveita conexões.
- **Tempo de resposta:** uma otimização completa costuma levar de 30 s a 1 min. No frontend, mostre um estado de carregamento e não use timeout curto no `fetch`.

## Exemplo com `curl`

```bash
curl -X POST http://localhost:8000/api/v1/resume/optimize \
  -H "Content-Type: application/json" \
  -d '{"master_resume": "...", "job_description": "...", "language": "pt-BR", "include_cover_letter": true}'
```
