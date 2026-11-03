/**
 * Controle de estados visuais: loading, erros, abas, toast e status da API.
 * Não faz chamadas de rede nem conhece o formato da resposta.
 */
import { $ } from './utils.js';

/* ------------------------------------------------------------------ toast */

let toastTimer;
export function showToast(message, ms = 2400) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.remove('opacity-0', 'translate-y-4');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add('opacity-0', 'translate-y-4'), ms);
}

/* ------------------------------------------------------------------ feedback "Copiado!" */

const COPIED_ICON = '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M20 6 9 17l-5-5"/></svg>';

/** Troca o botão para "Copiado!" por 2 s e depois restaura o conteúdo original. */
export function flashCopied(button) {
  if (button.dataset.busy) return;
  button.dataset.busy = '1';
  const original = button.innerHTML;
  button.classList.add('is-copied');
  button.innerHTML = `${COPIED_ICON}<span>Copiado!</span>`;
  setTimeout(() => {
    button.innerHTML = original;
    button.classList.remove('is-copied');
    delete button.dataset.busy;
  }, 2000);
}

/* ------------------------------------------------------------------ loading */

const LOADING_STEPS = [
  'Analisando a descrição da vaga…',
  'Extraindo palavras-chave e requisitos…',
  'Cruzando requisitos com o seu currículo…',
  'Reescrevendo experiências com foco em ATS…',
  'Personalizando a carta de apresentação…',
  'Revisando fidelidade aos seus dados…',
  'Quase lá, finalizando o resultado…',
];

let loadingTimers = [];

export function setLoading(isLoading, { includeLetter = true } = {}) {
  const button = $('#submit-btn');
  const panel = $('#loading-panel');
  button.disabled = isLoading;
  button.setAttribute('aria-busy', String(isLoading));
  $('.btn-spinner', button).classList.toggle('hidden', !isLoading);
  $('.btn-icon', button).classList.toggle('hidden', isLoading);
  $('.btn-label', button).textContent = isLoading ? 'Gerando…' : 'Gerar Currículo Otimizado';
  panel.classList.toggle('hidden', !isLoading);

  loadingTimers.forEach(clearInterval);
  loadingTimers = [];
  if (!isLoading) return;

  // Mensagens de progresso (ilustrativas: a API não envia progresso real).
  const steps = includeLetter ? LOADING_STEPS : LOADING_STEPS.filter((s) => !s.includes('carta'));
  let step = 0;
  const stepEl = $('#loading-step');
  const elapsedEl = $('#loading-elapsed');
  stepEl.textContent = steps[0];
  elapsedEl.textContent = '0s';

  const start = Date.now();
  loadingTimers.push(
    setInterval(() => {
      step = Math.min(step + 1, steps.length - 1);
      stepEl.textContent = steps[step];
    }, 7000),
    setInterval(() => {
      elapsedEl.textContent = `${Math.floor((Date.now() - start) / 1000)}s`;
    }, 1000),
  );
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ------------------------------------------------------------------ erros */

/** Títulos amigáveis por código de erro (backend + erros do próprio cliente). */
const ERROR_TITLES = {
  VALIDATION_ERROR: 'Confira os dados enviados',
  INVALID_INPUT: 'O conteúdo não foi aceito pela IA',
  RATE_LIMITED: 'Muitas requisições em sequência',
  AI_CONFIGURATION_ERROR: 'Problema de configuração no servidor',
  AI_INVALID_RESPONSE: 'A IA não devolveu um resultado válido',
  AI_UNAVAILABLE: 'A IA está indisponível no momento',
  JOB_URL_UNREADABLE: 'Não foi possível ler a vaga pelo link',
  UNSUPPORTED_FILE_TYPE: 'Formato de arquivo não suportado',
  FILE_TOO_LARGE: 'Arquivo grande demais',
  DOCUMENT_UNREADABLE: 'Não foi possível ler o arquivo',
  INTERNAL_ERROR: 'Erro interno no servidor',
  NETWORK_ERROR: 'Backend fora do ar',
  TIMEOUT: 'Tempo de resposta esgotado',
};

/** Dicas extras que ajudam o usuário a resolver sozinho. */
const ERROR_HINTS = {
  AI_CONFIGURATION_ERROR: 'Verifique a ANTHROPIC_API_KEY e o CLAUDE_MODEL no arquivo .env do backend.',
  AI_INVALID_RESPONSE: 'Isso costuma ser pontual. Tente gerar novamente.',
  JOB_URL_UNREADABLE: 'Use a opção "Colar texto" e cole o anúncio manualmente.',
};

const FIELD_NAMES = {
  master_resume: 'Currículo mestre',
  cover_letter_template: 'Carta padrão',
  job_description: 'Descrição da vaga',
  job_url: 'Link da vaga',
  language: 'Idioma',
  include_cover_letter: 'Carta de apresentação',
};

export function showError(error) {
  const panel = $('#error-panel');
  $('#error-title').textContent = ERROR_TITLES[error.code] ?? 'Algo deu errado';

  let message = error.message;
  if (error.code === 'RATE_LIMITED' && error.retryAfter) message += ` Aguarde ${error.retryAfter} s.`;
  if (ERROR_HINTS[error.code]) message += ` ${ERROR_HINTS[error.code]}`;
  $('#error-message').textContent = message;

  // Erros de validação trazem a lista de campos em `details`.
  const list = $('#error-details');
  list.replaceChildren();
  if (Array.isArray(error.details)) {
    error.details.forEach((d) => {
      const li = document.createElement('li');
      li.textContent = d.field ? `${FIELD_NAMES[d.field] ?? d.field}: ${d.message}` : d.message;
      list.appendChild(li);
    });
  }

  panel.classList.remove('hidden');
  panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

export function hideError() {
  $('#error-panel').classList.add('hidden');
}

/* ------------------------------------------------------------------ validação de campo */

export function setFieldError(input, errorEl, message) {
  errorEl.textContent = message ?? '';
  if (message) input.setAttribute('aria-invalid', 'true');
  else input.removeAttribute('aria-invalid');
}

/* ------------------------------------------------------------------ botões com spinner */

/** Alterna ícone/spinner/rótulo de um botão no padrão .btn-icon/.btn-spinner/.btn-label. */
export function setButtonBusy(button, busy, busyLabel) {
  const label = $('.btn-label', button);
  if (busy) button.dataset.idleLabel ??= label.textContent;
  button.disabled = busy;
  button.setAttribute('aria-busy', String(busy));
  $('.btn-spinner', button).classList.toggle('hidden', !busy);
  $('.btn-icon', button).classList.toggle('hidden', busy);
  label.textContent = busy ? busyLabel : button.dataset.idleLabel ?? label.textContent;
}

/* ------------------------------------------------------------------ abas (padrão WAI-ARIA) */

export function initTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];

  const select = (tab, focus = false) => {
    tabs.forEach((t) => {
      const active = t === tab;
      t.setAttribute('aria-selected', String(active));
      t.tabIndex = active ? 0 : -1;
      document.getElementById(t.getAttribute('aria-controls')).classList.toggle('hidden', !active);
    });
    if (focus) tab.focus();
  };

  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(tab));
    // Setas esquerda/direita navegam entre as abas.
    tab.addEventListener('keydown', (ev) => {
      const dir = { ArrowRight: 1, ArrowLeft: -1 }[ev.key];
      if (!dir) return;
      ev.preventDefault();
      select(tabs[(i + dir + tabs.length) % tabs.length], true);
    });
  });

  return { select: (name) => select(tabs.find((t) => t.dataset.tab === name)) };
}

/* ------------------------------------------------------------------ status da API */

export function setApiStatus(state, text) {
  const el = $('#api-status');
  const dot = $('.status-dot', el);
  const colors = { online: 'bg-emerald-500', offline: 'bg-rose-500', checking: 'bg-slate-300' };
  dot.className = `status-dot h-2 w-2 rounded-full ${colors[state]}${state === 'online' ? ' shadow-[0_0_0_3px_rgb(16_185_129/0.2)]' : ''}`;
  $('.status-text', el).textContent = text;
}
