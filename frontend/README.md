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
