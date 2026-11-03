/**
 * Ponto de entrada: liga o formulário, a API e a renderização.
 *
 * Fluxo: validar campos -> (importar vaga pelo link, se preciso) ->
 *        setLoading -> optimizeResume() -> renderResults()
 *        (ou showError em caso de falha).
 */
import { CONFIG } from './config.js';
import { ApiError, checkHealth, optimizeResume } from './api.js';
import { storage } from './storage.js';
import { $, copyText, downloadText, slugify } from './utils.js';
import { DocumentField } from './documents.js';
import { JobInput } from './job-input.js';
import {
  renderAnalysisPanel, renderLetterPanel, renderMeta, renderResumePanel,
  renderSummaryCards, resumeToPlainText,
} from './render.js';
import {
  flashCopied, hideError, initTabs, setApiStatus, setFieldError, setLoading,
  showError, showToast,
} from './ui.js';

/* ------------------------------------------------------------------ referências */

const form = $('#optimize-form');
const fields = {
  resume: { input: $('#master-resume'), error: $('#resume-error'), count: $('#resume-count'), limits: CONFIG.LIMITS.resume },
  letter: { input: $('#cover-letter-template'), error: $('#letter-error'), count: $('#letter-count'), limits: CONFIG.LIMITS.letter },
  job: { input: $('#job-description'), error: $('#job-error'), count: $('#job-count'), limits: CONFIG.LIMITS.job },
};
const languageSelect = $('#language');
const letterToggle = $('#include-cover-letter');

/** Estado da aplicação (fonte única da verdade para as ações de copiar/baixar). */
const state = {
  result: null,      // última resposta da API
  language: 'pt-BR', // idioma em que o resultado foi gerado
  controller: null,  // AbortController da requisição em andamento
};

const tabs = initTabs();

/* ------------------------------------------------------------------ validação */

const MESSAGES = {
  resume: {
    empty: 'Cole seu currículo mestre para continuar.',
    short: (n, min) => `Currículo curto demais: ${n} de ${min} caracteres mínimos.`,
    long: (max) => `O currículo passou do limite de ${max.toLocaleString('pt-BR')} caracteres.`,
  },
  letter: {
    empty: null, // opcional
    short: () => null,
    long: (max) => `A carta padrão passou do limite de ${max.toLocaleString('pt-BR')} caracteres.`,
  },
  job: {
    empty: 'Cole a descrição da vaga para continuar.',
    short: (n, min) => `Descrição curta demais: ${n} de ${min} caracteres mínimos. Cole o anúncio completo.`,
    long: (max) => `A descrição passou do limite de ${max.toLocaleString('pt-BR')} caracteres.`,
  },
};

/** Valida um campo e retorna a mensagem de erro (ou null). */
function validateField(key) {
  const { input, limits } = fields[key];
  const length = input.value.trim().length;
  const msg = MESSAGES[key];
  if (!length) return msg.empty;
  if (key === 'letter' && !letterToggle.checked) return null; // carta desligada: não é enviada
  if (length < limits.min) return msg.short(length, limits.min);
  if (length > limits.max) return msg.long(limits.max);
  return null;
}

/** Atualiza o contador de caracteres (verde quando atinge o mínimo). */
function updateCounter(key) {
  const { input, count, limits } = fields[key];
  const length = input.value.trim().length;
  count.textContent = length.toLocaleString('pt-BR');
  const ok = length > 0 && length >= limits.min && length <= limits.max;
  count.parentElement.classList.toggle('text-emerald-600', ok);
  count.parentElement.classList.toggle('text-slate-400', !ok);
}

/* ------------------------------------------------------------------ persistência */

/** Documentos base: upload + texto, salvos no navegador. */
const documents = {
  resume: new DocumentField({
    key: 'resume', card: $('[data-doc="resume"]'), textarea: fields.resume.input, errorEl: fields.resume.error,
    savedPill: $('#resume-saved'), textKey: CONFIG.STORAGE_KEYS.resume, fileKey: CONFIG.STORAGE_KEYS.resumeFile,
    onChange: handleFieldChange,
  }),
  letter: new DocumentField({
    key: 'letter', card: $('[data-doc="letter"]'), textarea: fields.letter.input, errorEl: fields.letter.error,
    savedPill: $('#letter-saved'), textKey: CONFIG.STORAGE_KEYS.letter, fileKey: CONFIG.STORAGE_KEYS.letterFile,
    onChange: handleFieldChange,
  }),
};

const job = new JobInput({
  textarea: fields.job.input,
  textError: fields.job.error,
  onModeChange: savePrefs,
  onTextChange: () => handleFieldChange('job'),
});

/** Atualiza contador e limpa o erro assim que o campo fica válido (sem "brigar" com quem digita). */
function handleFieldChange(key) {
  const { input, error } = fields[key];
  updateCounter(key);
  if (input.hasAttribute('aria-invalid') && !validateField(key)) setFieldError(input, error, null);
}

function savePrefs() {
  storage.set(CONFIG.STORAGE_KEYS.prefs, {
    language: languageSelect.value,
    includeCoverLetter: letterToggle.checked,
    jobMode: job.mode,
  });
}

/** Com a carta desligada, o card da carta padrão fica esmaecido (ela não será enviada). */
function syncLetterCard() {
  documents.letter.card.classList.toggle('opacity-60', !letterToggle.checked);
}

function restoreState() {
  const prefs = storage.get(CONFIG.STORAGE_KEYS.prefs, {});
  if (prefs.language) languageSelect.value = prefs.language;
  if (typeof prefs.includeCoverLetter === 'boolean') letterToggle.checked = prefs.includeCoverLetter;
  documents.resume.restore();
  documents.letter.restore();
  job.setMode(prefs.jobMode === 'url' ? 'url' : 'text');
  syncLetterCard();
  Object.keys(fields).forEach(updateCounter);

  // Reexibe o último resultado: uma geração custa créditos, não deve se perder num F5.
  const last = storage.get(CONFIG.STORAGE_KEYS.lastResult);
  if (last?.data) {
    renderResults(last.data, last.language, { scroll: false });
    showToast('Último resultado restaurado');
  }
}

/* ------------------------------------------------------------------ resultados */

function renderResults(data, language, { scroll = true } = {}) {
  state.result = data;
  state.language = language;

  $('#results-title').textContent = data.job_analysis?.job_title || 'Currículo otimizado';
  $('#results-meta').textContent = renderMeta(data.metadata, data.job_origin);
  $('#summary-cards').innerHTML = renderSummaryCards(data);
  $('#panel-analysis').innerHTML = renderAnalysisPanel(data);
  $('#panel-resume').innerHTML = renderResumePanel(data.adapted_resume, language);
  $('#panel-letter').innerHTML = renderLetterPanel(data.cover_letter);

  const section = $('#results');
  section.classList.remove('hidden');
  tabs.select('analysis');

  // Anima o anel do score e a barra de cobertura no próximo frame.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    section.querySelectorAll('[data-target-offset]').forEach((c) => c.setAttribute('stroke-dashoffset', c.dataset.targetOffset));
    section.querySelectorAll('[data-target-width]').forEach((b) => { b.style.width = b.dataset.targetWidth; });
  }));

  if (scroll) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ------------------------------------------------------------------ submit */

async function handleSubmit(event) {
  event?.preventDefault();
  if (state.controller || job.isBusy) return; // já existe uma operação em andamento
  if (documents.resume.isBusy || documents.letter.isBusy) {
    showToast('Aguarde a leitura do arquivo terminar');
    return;
  }

  hideError();
  if (!(await ensureJobText())) return;

  // Valida os campos e foca no primeiro com problema.
  let firstInvalid = null;
  for (const key of ['resume', 'letter', 'job']) {
    const message = validateField(key);
    setFieldError(fields[key].input, fields[key].error, message);
    if (message && !firstInvalid) firstInvalid = fields[key].input;
  }
  if (firstInvalid) {
    firstInvalid.focus();
    return;
  }

  const includeLetter = letterToggle.checked;
  const payload = {
    master_resume: documents.resume.value,
    cover_letter_template: includeLetter ? documents.letter.value || null : null,
    job_description: fields.job.input.value.trim(),
    // Referência de origem: o texto (já revisado) tem prioridade no backend.
    job_url: job.mode === 'url' && job.hasImportedCurrentUrl ? job.importedUrl : null,
    language: languageSelect.value,
    include_cover_letter: includeLetter,
  };

  state.controller = new AbortController();
  setLoading(true, { includeLetter });

  try {
    const data = await optimizeResume(payload, state.controller.signal);
    storage.set(CONFIG.STORAGE_KEYS.lastResult, { data, language: payload.language, savedAt: Date.now() });
    setLoading(false);
    renderResults(data, payload.language);
    showToast('Currículo otimizado com sucesso!');
  } catch (error) {
    setLoading(false);
    const apiError = error instanceof ApiError ? error : new ApiError('INTERNAL_ERROR', 'Erro inesperado na interface.');
    if (apiError.code === 'CANCELLED') showToast('Geração cancelada');
    else showError(apiError);
    console.error('[ResuMatch]', apiError);
  } finally {
    state.controller = null;
  }
}

/**
 * No modo link, importa a vaga antes de gerar (se o usuário ainda não clicou
 * em "Importar"). Assim o usuário pode colar o link e ir direto em "Gerar".
 */
async function ensureJobText() {
  if (job.mode !== 'url' || job.hasImportedCurrentUrl) return true;
  if (!job.urlInput.value.trim() && fields.job.input.value.trim()) return true; // texto colado manualmente
  return job.importFromUrl();
}

/* ------------------------------------------------------------------ ações dos resultados */

/** Ações dos botões com data-action (delegação: os botões são recriados a cada resultado). */
const ACTIONS = {
  'copy-resume': (btn) => copyAndFlash(btn, resumeToPlainText(state.result.adapted_resume, state.language)),
  'copy-letter': (btn) => copyAndFlash(btn, state.result.cover_letter ?? ''),
  'copy-keywords': (btn) => copyAndFlash(btn, (state.result.job_analysis?.keywords ?? []).map((k) => k.term).join(', ')),
  'download-resume': () => downloadText(
    `curriculo-${slugify(state.result.job_analysis?.job_title)}.txt`,
    resumeToPlainText(state.result.adapted_resume, state.language),
  ),
  'download-letter': () => downloadText(
    `carta-${slugify(state.result.job_analysis?.job_title)}.txt`,
    state.result.cover_letter ?? '',
  ),
  print: () => window.print(),
};

async function copyAndFlash(button, text) {
  if (!text) return showToast('Nada para copiar');
  if (await copyText(text)) flashCopied(button);
  else showToast('Não foi possível copiar. Selecione o texto manualmente.');
}

/** Filtro Todas / Presentes / Ausentes da lista de palavras-chave. */
function applyKeywordFilter(button) {
  const value = button.dataset.filter;
  button.parentElement.querySelectorAll('.keyword-filter').forEach((b) => {
    const active = b === button;
    b.setAttribute('aria-pressed', String(active));
    b.classList.toggle('bg-slate-900', active);
    b.classList.toggle('text-white', active);
    b.classList.toggle('bg-slate-100', !active);
    b.classList.toggle('text-slate-600', !active);
  });
  document.querySelectorAll('#keyword-list .keyword-item').forEach((li) => {
    li.classList.toggle('hidden', value !== 'all' && li.dataset.present !== value);
  });
}

/* ------------------------------------------------------------------ status da API */

async function refreshApiStatus() {
  setApiStatus('checking', 'Verificando API…');
  try {
    const health = await checkHealth();
    setApiStatus('online', `API online · ${health.model}`);
  } catch {
    setApiStatus('offline', 'API offline');
  }
}

/* ------------------------------------------------------------------ eventos */

function bindEvents() {
  form.addEventListener('submit', handleSubmit);

  // Ctrl/Cmd + Enter envia de qualquer campo.
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) handleSubmit(ev);
  });

  // Os documentos base cuidam dos próprios eventos; aqui só a vaga digitada.
  fields.job.input.addEventListener('input', () => handleFieldChange('job'));

  document.querySelectorAll('[data-clear]').forEach((button) => {
    button.addEventListener('click', () => {
      const doc = documents[button.dataset.clear];
      if (!doc.value && doc.dropzone.dataset.state === 'idle') return;
      doc.clear();
      doc.textarea.focus();
      showToast(button.dataset.clear === 'resume' ? 'Currículo removido deste navegador' : 'Carta padrão removida deste navegador');
    });
  });

  $('#clear-job').addEventListener('click', () => {
    job.clear();
    (job.mode === 'url' ? job.urlInput : fields.job.input).focus();
  });

  // Soltar um arquivo fora dos cards não deve abrir o arquivo no navegador.
  ['dragover', 'drop'].forEach((type) => window.addEventListener(type, (ev) => {
    if (!ev.target.closest?.('.doc-card')) ev.preventDefault();
  }));

  letterToggle.addEventListener('change', () => {
    syncLetterCard();
    handleFieldChange('letter');
  });
  languageSelect.addEventListener('change', savePrefs);
  letterToggle.addEventListener('change', savePrefs);

  $('#cancel-btn').addEventListener('click', () => state.controller?.abort());
  $('#error-retry').addEventListener('click', handleSubmit);
  $('#error-dismiss').addEventListener('click', hideError);

  $('#results').addEventListener('click', (ev) => {
    const filterBtn = ev.target.closest('.keyword-filter');
    if (filterBtn) return applyKeywordFilter(filterBtn);
    const actionBtn = ev.target.closest('[data-action]');
    if (actionBtn && state.result) ACTIONS[actionBtn.dataset.action]?.(actionBtn);
  });
}

/* ------------------------------------------------------------------ init */

bindEvents();
restoreState();
refreshApiStatus();
