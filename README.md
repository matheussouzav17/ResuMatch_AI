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
