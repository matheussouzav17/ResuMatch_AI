# ResuMatch AI

Aplicação full-stack que adapta currículos e cartas de apresentação para passar pelos filtros **ATS** (Applicant Tracking Systems), usando a API do **Claude** (Anthropic).

O candidato envia seus documentos base uma vez (currículo mestre e carta padrão, em PDF, DOCX, TXT ou texto colado), cola a vaga ou só o link dela, e recebe:

- **Análise da vaga:** palavras-chave obrigatórias e desejáveis, score de aderência, lacunas e sugestões, com o trecho do currículo que comprova cada competência.
- **Currículo otimizado** para ATS, com os termos exatos da vaga.
- **Carta personalizada** a partir da carta padrão, mantendo o tom do candidato.
- **Checagem de fidelidade:** o prompt proíbe inventar cargos, datas ou experiências, e o backend confere automaticamente se empresas, instituições e anos do resultado existem no currículo mestre.

## Stack

| Camada | Tecnologias |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2, SDK `anthropic` (Structured Outputs), pypdf, python-docx, httpx, BeautifulSoup |
| Frontend | HTML semântico, Tailwind CSS, JavaScript puro (ES Modules) |
| Testes | pytest (sem chamadas reais à IA) |

## Como rodar

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # e preencha ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Acesse <http://localhost:8000/app/> (interface) ou <http://localhost:8000/docs> (Swagger).

Detalhes em [backend/README.md](backend/README.md) e [frontend/README.md](frontend/README.md).

# ResuMatch AI: Backend

API em FastAPI que recebe os **documentos base** do candidato (currículo mestre e carta de apresentação padrão, em PDF, DOCX, TXT ou texto colado) e uma **vaga** (texto ou link), envia ao Claude (Anthropic) com engenharia de prompt focada em ATS e devolve um JSON estruturado com análise de palavras-chave, score de aderência, currículo otimizado, carta personalizada e uma checagem automática de fidelidade.

## Estrutura

```
backend/
├── app/
│   ├── main.py                     # Cria o app, CORS, lifespan (serviços), rotas e handlers
│   ├── api/
│   │   ├── routes.py               # Registra os grupos de rotas
│   │   ├── dependencies.py         # Injeção de dependências (serviços criados no startup)
│   │   └── endpoints/
│   │       ├── system.py           # GET /health
│   │       ├── resume.py           # POST /api/v1/resume/optimize (JSON) e /optimize/upload (multipart)
│   │       ├── documents.py        # POST /api/v1/documents/extract (UploadFile -> texto)
│   │       └── jobs.py             # POST /api/v1/jobs/extract (URL da vaga -> texto)
│   ├── core/
│   │   ├── config.py               # Configurações via .env (pydantic-settings)
│   │   └── exceptions.py           # Exceções de domínio -> códigos HTTP + formato de erro único
│   ├── schemas/
│   │   ├── resume.py               # Requisição/resposta da otimização e saída estruturada da IA
│   │   └── documents.py            # Documentos e vagas extraídos
│   └── services/
│       ├── optimization_service.py # Orquestra: resolve a vaga -> IA -> pós-processamento
│       ├── claude_service.py       # Única camada que conhece a SDK da Anthropic
│       ├── prompts.py              # System prompt (fidelidade + ATS) e prompt do usuário
│       ├── document_parser.py      # PDF (pypdf), DOCX (python-docx) e TXT -> texto
│       ├── job_scraper.py          # Link da vaga -> texto (JSON-LD JobPosting ou HTML), com proteção SSRF
│       └── fidelity.py             # Checagem determinística: empresas, instituições e anos existem no currículo mestre?
├── tests/                          # pytest (sem chamar a API real da Anthropic)
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```

**Fluxo:** a rota valida o payload (Pydantic) → `optimization_service.py` resolve a vaga (texto enviado ou extraído do link) → `claude_service.py` chama o Claude com *Structured Outputs* (resposta validada contra `AIOptimizationResult`) → `fidelity.py` confere os fatos do currículo gerado contra o currículo mestre → erros viram exceções de domínio → `exceptions.py` converte em HTTP.

## Como rodar localmente (Windows / PowerShell)

Pré-requisito: Python 3.11 ou superior.

```powershell
cd backend

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
- Interface web: <http://localhost:8000/app/>

### Testes

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Os testes usam um serviço de IA falso (`app.dependency_overrides`) e `httpx.MockTransport` para as páginas de vagas, então não gastam créditos nem acessam a internet.

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
| `MAX_UPLOAD_MB` | `5` | Tamanho máximo de cada arquivo enviado |
| `JOB_FETCH_TIMEOUT_SECONDS` | `15` | Timeout ao buscar a página da vaga |
| `JOB_FETCH_MAX_MB` | `3` | Tamanho máximo lido da página da vaga |
| `JOB_FETCH_ALLOW_PRIVATE_HOSTS` | `false` | Libera URLs da rede interna (só para testes locais) |
| `CORS_ORIGINS` | `http://localhost:5500,...` | Origens do frontend, separadas por vírgula |
| `ENVIRONMENT` | `development` | Em `production`, `/docs` é desativado |

## Contrato da API

### `POST /api/v1/resume/optimize`

**Requisição (JSON)**

```json
{
  "master_resume": "texto do currículo (200 a 30.000 caracteres)",
  "cover_letter_template": "carta padrão (opcional, até 10.000 caracteres)",
  "job_description": "texto da vaga (100 a 20.000 caracteres)",
  "job_url": "https://empresa.gupy.io/jobs/123 (opcional)",
  "language": "pt-BR",
  "include_cover_letter": true
}
```

Envie `job_description` **ou** `job_url`. Só com o link, o backend extrai a vaga antes de chamar a IA. Com os dois, o texto tem prioridade e o link fica como referência (`job_origin`). `language` aceita `pt-BR`, `en` ou `es`.

### `POST /api/v1/resume/optimize/upload` (multipart/form-data)

Mesmo resultado, aceitando os documentos como arquivo: `master_resume_file` **ou** `master_resume`, `cover_letter_file` **ou** `cover_letter_template`, `job_description` **ou** `job_url`, `language`, `include_cover_letter`. Dá para testar direto no Swagger.

```bash
curl -X POST http://localhost:8000/api/v1/resume/optimize/upload \
  -F "master_resume_file=@curriculo.pdf" \
  -F "cover_letter_file=@carta.docx" \
  -F "job_url=https://empresa.gupy.io/jobs/123"
```

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
  "fidelity_warnings": [],
  "job_origin": { "type": "url", "url": "https://...", "source": "structured_data" },
  "metadata": {
    "model": "claude-opus-5-5",
    "input_tokens": 3120,
    "output_tokens": 2480,
    "processing_time_ms": 41250
  }
}
```

`category`: `hard_skill`, `soft_skill`, `tool`, `certification`, `domain`. `importance`: `required`, `preferred`. `keyword_coverage` e `fidelity_warnings` são calculados no backend (não pelo modelo). `fidelity_warnings` lista empresas, instituições ou anos do currículo otimizado que não aparecem no currículo mestre.

### `POST /api/v1/documents/extract` (multipart)

Campo `file` com PDF, DOCX ou TXT (até `MAX_UPLOAD_MB`). Não chama a IA nem guarda o arquivo.

```json
{ "filename": "curriculo.pdf", "file_type": "pdf", "text": "...", "page_count": 2, "char_count": 4210 }
```

### `POST /api/v1/jobs/extract`

```json
{ "url": "https://empresa.gupy.io/jobs/123" }
```

```json
{
  "url": "...", "final_url": "...", "title": "Desenvolvedor Backend Pleno", "company": "Empresa",
  "text": "...", "source": "structured_data", "char_count": 3120
}
```

`source` é `structured_data` (bloco `schema.org/JobPosting`, usado pelo Google for Jobs e presente na maioria dos sites de vagas) ou `page_text` (texto visível da página, pode ter ruído).

**Erros:** sempre no formato

```json
{ "error": { "code": "RATE_LIMITED", "message": "mensagem amigável", "details": null } }
```

| HTTP | `code` | Quando |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Campos ausentes, curtos/longos demais ou extras (`details` lista os campos) |
| 400 | `INVALID_INPUT` | A API do Claude rejeitou o conteúdo |
| 413 | `FILE_TOO_LARGE` | Arquivo acima de `MAX_UPLOAD_MB` |
| 415 | `UNSUPPORTED_FILE_TYPE` | Extensão diferente de PDF/DOCX/TXT ou conteúdo que não bate com a extensão |
| 422 | `DOCUMENT_UNREADABLE` | Arquivo corrompido, com senha ou sem texto (PDF escaneado) |
| 422 | `JOB_URL_UNREADABLE` | Site bloqueou a leitura (403/429), exige login, vaga não encontrada ou montada só com JavaScript. A mensagem orienta a colar o texto |
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

- **Fidelidade aos dados (em duas camadas):** o system prompt trata o currículo mestre como fonte de verdade absoluta e proíbe inventar, promover ou estender cargos, empresas, datas, formações, métricas ou tecnologias; requisitos sem evidência vão para `gaps`, nunca para o currículo. Cada palavra-chave marcada como presente traz o trecho que a comprova (`evidence`). Depois, `fidelity.py` confere sem IA se empresas, instituições e anos do resultado existem no currículo mestre e devolve alertas em `fidelity_warnings`.
- **Carta padrão:** quando enviada, a IA preserva o tom, a estrutura e as motivações do candidato e personaliza para a vaga. Fatos profissionais da carta só entram se também estiverem no currículo mestre.
- **Leitura de documentos:** o tipo é validado pela extensão e pela assinatura do arquivo (um `.exe` renomeado para `.pdf` é recusado), o upload é lido em blocos com limite de tamanho e o parsing roda em thread separada para não travar o event loop.
- **Vaga por link com proteção SSRF:** só `http/https` em portas padrão, e qualquer host que resolva para IP privado, loopback ou link-local (ex.: `169.254.169.254`) é recusado, inclusive após redirecionamentos. Falhas nunca derrubam o fluxo: a mensagem orienta o usuário a colar o texto.
- **Structured Outputs:** a resposta do Claude é forçada a seguir o schema Pydantic, então o frontend nunca recebe JSON quebrado.
- **Proteção contra prompt injection:** currículo, carta e vaga vão entre tags XML e o prompt instrui o modelo a tratá-los como dados.
- **Fallback de recusa:** em modelos compatíveis, a requisição usa o fallback automático do servidor da Anthropic caso um classificador de segurança recuse o conteúdo.
- **Clientes únicos:** o `AsyncAnthropic` e o `httpx.AsyncClient` do scraper são criados uma vez no startup (lifespan) e reaproveitam conexões.
- **Tempo de resposta:** uma otimização completa costuma levar de 30 s a 1 min. No frontend, mostre um estado de carregamento e não use timeout curto no `fetch`.

## Exemplo com `curl`

```bash
curl -X POST http://localhost:8000/api/v1/resume/optimize \
  -H "Content-Type: application/json" \
  -d '{"master_resume": "...", "job_description": "...", "language": "pt-BR", "include_cover_letter": true}'
```
# ResuMatch AI: Frontend

Interface web do ResuMatch AI em **HTML5 semântico + Tailwind CSS (CDN) + JavaScript puro (ES Modules)**. Consome a API FastAPI do diretório `backend/`.

## Funcionalidades

- **Documentos base:** currículo mestre e carta de apresentação padrão (opcional), cada um por upload (PDF, DOCX ou TXT, clicando ou arrastando o arquivo para o card) ou texto colado. O texto extraído aparece num campo editável para revisão e fica salvo no navegador (`localStorage`) para as próximas vagas.
- **Vaga por texto ou link:** seletor "Colar texto" / "Link da vaga". No modo link, a vaga é importada pelo backend e o texto aparece para revisão; colar o link e clicar direto em "Gerar" também funciona (importa antes de gerar). Se o site bloquear a leitura, o card explica o motivo e oferece voltar para "Colar texto".
- Contadores e validação de tamanho mínimo/máximo em todos os campos, com validação de formato e tamanho do arquivo antes do envio.
- Escolha de idioma (pt-BR, en, es) e opção de gerar ou não a carta de apresentação.
- Spinners no upload de cada arquivo, no botão "Importar vaga" e na geração; estado de carregamento com skeleton screen, mensagens de progresso, cronômetro e botão **Cancelar** (`AbortController`).
- Resultado em três abas:
  1. **Análise da vaga:** checagem de fidelidade (alerta se a IA citou empresa, instituição ou ano que não está no currículo mestre), score de aderência, cobertura de palavras-chave, termos presentes/ausentes com o trecho do currículo que comprova cada um, pontos fortes, lacunas e sugestões.
  2. **Currículo otimizado:** formatado como documento, com copiar (texto puro pronto para ATS), baixar `.txt` e imprimir/salvar em PDF.
  3. **Carta personalizada:** baseada na sua carta padrão, com copiar, baixar e imprimir.
- Botões de copiar com feedback visual "Copiado!".
- Erros amigáveis para cada código da API (`VALIDATION_ERROR`, `RATE_LIMITED`, `AI_UNAVAILABLE`...), backend fora do ar e timeout.
- Indicador de status da API (`GET /health`) no cabeçalho, último resultado restaurado após recarregar a página, atalho `Ctrl + Enter`.
- Acessível: abas no padrão WAI-ARIA (navegação por setas), `aria-live` nos estados, foco no campo com erro, respeita `prefers-reduced-motion`.

## Como rodar

Com o backend rodando (`uvicorn app.main:app --reload` dentro de `backend/`), use uma das opções:

- **Pelo próprio backend (recomendado):** acesse <http://localhost:8000/app/>. O FastAPI serve esta pasta, então front e API ficam na mesma origem.
- **Live Server (VS Code):** clique com o botão direito em `index.html` → *Open with Live Server*. Em desenvolvimento, o backend libera CORS para qualquer porta de `localhost`.

> Não abra o `index.html` com duplo clique (`file://`): módulos ES e chamadas à API não funcionam assim. A página mostra um aviso nesse caso.

Para apontar para outro backend (ex.: deploy), defina antes dos scripts:

```html
<script>window.RESUMATCH_API_URL = 'https://sua-api.com';</script>
```

## Estrutura

```
frontend/
├── index.html              # Estrutura semântica + tema do Tailwind
└── assets/
    ├── css/styles.css      # Componentes (cards, botões, abas, skeleton) e estilos de impressão
    └── js/
        ├── main.js         # Ponto de entrada: eventos, validação, fluxo de geração
        ├── documents.js    # DocumentField: upload/arrastar, extração e persistência dos documentos base
        ├── job-input.js    # JobInput: modo texto/link, importação da vaga e fallback para colar
        ├── api.js          # fetch (JSON e multipart) + ApiError (rede, timeout, cancelamento, erros da API)
        ├── render.js       # Funções puras que geram o HTML dos resultados e o texto do currículo
        ├── ui.js           # Estados visuais: loading, erro, abas, toast, status da API
        ├── storage.js      # localStorage com tratamento de falhas
        ├── utils.js        # escapeHtml, copiar, download, formatação
        └── config.js       # URL da API, limites e chaves de armazenamento
```

Todo texto vindo da API passa por `escapeHtml` antes de ir para o HTML, evitando XSS.
