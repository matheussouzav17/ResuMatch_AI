/**
 * Camada de comunicação com o backend (FastAPI).
 *
 * Toda falha vira um `ApiError` com `code`, `message` e `details`, no mesmo
 * formato que o backend usa ({"error": {code, message, details}}). Assim a
 * interface trata erros de rede, timeout e erros da API de um jeito só.
 */
import { CONFIG } from './config.js';

export class ApiError extends Error {
  /**
   * @param {string} code      Código estável (ex.: RATE_LIMITED, NETWORK_ERROR)
   * @param {string} message   Mensagem amigável para exibir
   * @param {object} [extra]
   * @param {number} [extra.status]      Status HTTP, se houver
   * @param {unknown} [extra.details]    Detalhes (ex.: campos inválidos)
   * @param {number} [extra.retryAfter]  Segundos sugeridos pelo header Retry-After
   */
  constructor(code, message, { status = 0, details = null, retryAfter = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
    this.retryAfter = retryAfter;
  }
}

/** Junta o sinal do usuário (cancelar) com um timeout de segurança. */
function withTimeout(userSignal, ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new DOMException('timeout', 'TimeoutError')), ms);
  const onUserAbort = () => controller.abort(new DOMException('cancelado', 'AbortError'));
  userSignal?.addEventListener('abort', onUserAbort, { once: true });
  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timer);
      userSignal?.removeEventListener('abort', onUserAbort);
    },
  };
}

/** Lê o corpo de erro padrão do backend, com fallback se não for JSON. */
async function parseErrorResponse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    /* corpo vazio ou não JSON */
  }
  const err = body?.error;
  const retryAfter = Number(response.headers.get('Retry-After')) || null;
  return new ApiError(
    err?.code || `HTTP_${response.status}`,
    err?.message || `O servidor respondeu com erro ${response.status}.`,
    { status: response.status, details: err?.details ?? null, retryAfter },
  );
}

/**
 * fetch com tratamento unificado de erros.
 * `body` pode ser um objeto (enviado como JSON) ou um FormData (multipart:
 * o navegador define o Content-Type com o boundary sozinho).
 */
async function request(path, { method = 'GET', body, signal, timeoutMs = 10_000, timeoutMessage } = {}) {
  const { signal: merged, cleanup } = withTimeout(signal, timeoutMs);
  const isForm = body instanceof FormData;
  try {
    const response = await fetch(`${CONFIG.API_BASE_URL}${path}`, {
      method,
      headers: body && !isForm ? { 'Content-Type': 'application/json' } : undefined,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
      signal: merged,
    });
    if (!response.ok) throw await parseErrorResponse(response);
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const reason = merged.reason;
    if (reason?.name === 'AbortError') {
      throw new ApiError('CANCELLED', 'Operação cancelada.');
    }
    if (reason?.name === 'TimeoutError') {
      throw new ApiError('TIMEOUT', timeoutMessage ?? 'O servidor demorou mais que o esperado para responder. Tente novamente.');
    }
    // TypeError do fetch = servidor fora do ar, CORS bloqueado ou sem rede.
    throw new ApiError(
      'NETWORK_ERROR',
      `Não foi possível conectar ao backend em ${CONFIG.API_BASE_URL}. Confira se o servidor está rodando (uvicorn app.main:app --reload).`,
    );
  } finally {
    cleanup();
  }
}

/**
 * POST /api/v1/resume/optimize
 * @param {{
 *   master_resume: string,
 *   cover_letter_template?: string|null,
 *   job_description?: string|null,
 *   job_url?: string|null,
 *   language: string,
 *   include_cover_letter: boolean,
 * }} payload
 * @param {AbortSignal} [signal]
 */
export function optimizeResume(payload, signal) {
  return request(CONFIG.ENDPOINTS.optimize, {
    method: 'POST',
    body: payload,
    signal,
    timeoutMs: CONFIG.REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A IA demorou mais que o esperado para responder. Tente novamente.',
  });
}

/**
 * POST /api/v1/documents/extract (multipart): PDF, DOCX ou TXT -> texto.
 * @param {File} file
 * @returns {Promise<{filename: string, file_type: string, text: string, page_count: number|null, char_count: number}>}
 */
export function extractDocument(file, signal) {
  const form = new FormData();
  form.append('file', file);
  return request(CONFIG.ENDPOINTS.extractDocument, { method: 'POST', body: form, signal, timeoutMs: 60_000 });
}

/**
 * POST /api/v1/jobs/extract: link da vaga -> título, empresa e descrição.
 * @param {string} url
 * @returns {Promise<{url: string, final_url: string, title: string|null, company: string|null, text: string, source: string, char_count: number}>}
 */
export function extractJob(url, signal) {
  return request(CONFIG.ENDPOINTS.extractJob, {
    method: 'POST',
    body: { url },
    signal,
    timeoutMs: 45_000,
    timeoutMessage: 'O site da vaga demorou demais para responder. Cole o texto do anúncio.',
  });
}

/** GET /health (não consome créditos da IA). */
export function checkHealth() {
  return request(CONFIG.ENDPOINTS.health, { timeoutMs: 5_000 });
}
