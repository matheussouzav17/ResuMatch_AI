/**
 * Campo dinâmico da vaga: "Colar texto" ou "Link da vaga".
 *
 * No modo link, o backend busca a página e devolve a descrição, que é
 * colocada no campo de texto para revisão. Se o site bloquear a leitura
 * (muito comum: LinkedIn, páginas que exigem login ou feitas só com
 * JavaScript), o card mostra o motivo e oferece voltar para "Colar texto".
 */
import { ApiError, extractJob } from './api.js';
import { hostOf } from './render.js';
import { $ } from './utils.js';
import { setButtonBusy, setFieldError } from './ui.js';

const PLACEHOLDERS = {
  text: 'Ex.: Desenvolvedor Backend Pleno. Requisitos: Python, FastAPI, Docker, PostgreSQL…',
  url: 'A descrição importada pelo link aparece aqui para você revisar antes de gerar.',
};
const SOURCE_LABELS = {
  structured_data: 'dados estruturados da vaga',
  page_text: 'texto da página (revise se veio algo a mais)',
};

/** Aceita "empresa.com/vaga" sem protocolo; devolve null se não for um link válido. */
export function normalizeUrl(raw) {
  const value = raw.trim();
  if (!value) return null;
  try {
    const url = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`);
    return url.hostname.includes('.') ? url.href : null;
  } catch {
    return null;
  }
}

export class JobInput {
  /**
   * @param {object} opts
   * @param {HTMLTextAreaElement} opts.textarea  campo da descrição
   * @param {HTMLElement} opts.textError         erro do campo de descrição
   * @param {(mode: string) => void} opts.onModeChange
   * @param {() => void} opts.onTextChange
   */
  constructor({ textarea, textError, onModeChange, onTextChange }) {
    Object.assign(this, { textarea, textError, onModeChange, onTextChange });
    this.urlRow = $('#job-url-row');
    this.urlInput = $('#job-url');
    this.urlError = $('#job-url-error');
    this.importBtn = $('#import-job-btn');
    this.failedBox = $('#job-import-failed');
    this.okLine = $('#job-import-ok');
    this.modeButtons = [...document.querySelectorAll('[data-job-mode]')];
    this.mode = 'text';
    this.importedUrl = null; // link de onde veio o texto atual (vai no payload como referência)
    this.controller = null;
    this.#bind();
  }

  get isBusy() {
    return Boolean(this.controller);
  }

  setMode(mode, { focus = false } = {}) {
    this.mode = mode;
    this.modeButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.jobMode === mode)));
    this.urlRow.classList.toggle('hidden', mode !== 'url');
    this.textarea.placeholder = PLACEHOLDERS[mode];
    if (mode === 'text') this.#hideFeedback();
    if (focus) (mode === 'url' ? this.urlInput : this.textarea).focus();
    this.onModeChange(mode);
  }

  clear() {
    this.controller?.abort();
    this.textarea.value = '';
    this.urlInput.value = '';
    this.importedUrl = null;
    this.#hideFeedback();
    setFieldError(this.urlInput, this.urlError, null);
    this.onTextChange();
  }

  /** Valida o link (modo URL). Devolve a mensagem de erro ou null. */
  validateUrl() {
    if (!this.urlInput.value.trim()) return 'Cole o link da vaga ou troque para "Colar texto".';
    if (!normalizeUrl(this.urlInput.value)) return 'Link inválido. Use o endereço completo, ex.: https://site.com/vaga/123';
    return null;
  }

  /** O texto atual já corresponde ao link digitado? */
  get hasImportedCurrentUrl() {
    return Boolean(this.importedUrl) && this.importedUrl === normalizeUrl(this.urlInput.value) && Boolean(this.textarea.value.trim());
  }

  /**
   * Importa a vaga do link. Devolve true em caso de sucesso.
   * Erros ficam visíveis no próprio card (não no painel global).
   */
  async importFromUrl() {
    const invalid = this.validateUrl();
    setFieldError(this.urlInput, this.urlError, invalid);
    if (invalid) {
      this.urlInput.focus();
      return false;
    }
    const url = normalizeUrl(this.urlInput.value);
    this.urlInput.value = url;
    this.#hideFeedback();

    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    setButtonBusy(this.importBtn, true, 'Importando…');

    try {
      const job = await extractJob(url, controller.signal);
      this.textarea.value = job.text;
      this.importedUrl = url;
      setFieldError(this.textarea, this.textError, null);
      this.onTextChange();

      const what = [job.title, job.company].filter(Boolean).join(' · ') || 'Vaga importada';
      $('.job-import-summary', this.okLine).textContent =
        `${what}, de ${hostOf(job.final_url) ?? hostOf(url)} via ${SOURCE_LABELS[job.source] ?? job.source}.`;
      this.okLine.classList.replace('hidden', 'flex');
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.code === 'CANCELLED') return false;
      const message = error instanceof ApiError ? error.message : 'Erro inesperado ao importar a vaga.';
      if (error instanceof ApiError && error.code === 'VALIDATION_ERROR') {
        setFieldError(this.urlInput, this.urlError, 'Link inválido. Confira o endereço.');
      } else {
        $('.job-import-message', this.failedBox).textContent = message;
        this.failedBox.classList.remove('hidden');
      }
      console.error('[ResuMatch] import', error);
      return false;
    } finally {
      if (this.controller === controller) this.controller = null;
      setButtonBusy(this.importBtn, false);
    }
  }

  #hideFeedback() {
    this.failedBox.classList.add('hidden');
    this.okLine.classList.replace('flex', 'hidden');
  }

  #bind() {
    this.modeButtons.forEach((b) => b.addEventListener('click', () => this.setMode(b.dataset.jobMode, { focus: true })));
    this.importBtn.addEventListener('click', () => this.importFromUrl());
    this.urlInput.addEventListener('keydown', (ev) => {
      // Enter no campo de link importa (em vez de enviar o formulário inteiro).
      if (ev.key === 'Enter' && !ev.ctrlKey && !ev.metaKey) {
        ev.preventDefault();
        this.importFromUrl();
      }
    });
    this.urlInput.addEventListener('input', () => {
      if (this.urlInput.hasAttribute('aria-invalid')) setFieldError(this.urlInput, this.urlError, null);
    });
    $('#job-switch-to-text').addEventListener('click', () => this.setMode('text', { focus: true }));
  }
}
