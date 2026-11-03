/**
 * Configuração central do frontend.
 *
 * API_BASE_URL:
 *  - Se a página for servida pelo próprio backend (http://localhost:8000/app/),
 *    usa a mesma origem, sem precisar de CORS.
 *  - Caso contrário (Live Server, outro servidor estático), aponta para o
 *    backend local na porta 8000.
 *  - Para apontar para outro endereço (ex.: deploy), defina
 *    `window.RESUMATCH_API_URL` antes de carregar os scripts.
 */
const DEFAULT_API = 'http://localhost:8000';

function resolveApiBase() {
  if (window.RESUMATCH_API_URL) return window.RESUMATCH_API_URL.replace(/\/+$/, '');
  const servedByBackend = location.protocol.startsWith('http') && location.port === '8000';
  return servedByBackend ? location.origin : DEFAULT_API;
}

export const CONFIG = Object.freeze({
  API_BASE_URL: resolveApiBase(),
  ENDPOINTS: Object.freeze({
    optimize: '/api/v1/resume/optimize',
    extractDocument: '/api/v1/documents/extract',
    extractJob: '/api/v1/jobs/extract',
    health: '/health',
  }),

  /** Limites espelhados do schema Pydantic (OptimizeRequest). */
  LIMITS: Object.freeze({
    resume: { min: 200, max: 30_000 },
    letter: { min: 0, max: 10_000 },
    job: { min: 100, max: 20_000 },
  }),

  /** Upload de documentos base (espelha MAX_UPLOAD_MB do backend). */
  UPLOAD: Object.freeze({
    maxBytes: 5 * 1024 * 1024,
    extensions: ['.pdf', '.docx', '.txt'],
  }),

  /** Chamadas de IA levam de 30 s a 1 min; o backend tem timeout de 180 s. */
  REQUEST_TIMEOUT_MS: 240_000,

  STORAGE_KEYS: Object.freeze({
    resume: 'resumatch:master-resume',
    letter: 'resumatch:cover-letter-template',
    resumeFile: 'resumatch:master-resume-file',
    letterFile: 'resumatch:cover-letter-file',
    prefs: 'resumatch:prefs',
    lastResult: 'resumatch:last-result',
  }),
});
