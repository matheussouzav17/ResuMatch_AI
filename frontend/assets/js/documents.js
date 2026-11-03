/**
 * Documentos base (currículo mestre e carta padrão): upload + texto.
 *
 * Cada card aceita um arquivo (clique ou arrastar e soltar) e também texto
 * colado. O arquivo é enviado ao backend só para extrair o texto, que cai no
 * campo editável: o usuário revisa o que a IA vai ler. Texto e nome do
 * arquivo ficam salvos no navegador (localStorage) para as próximas vagas.
 */
import { CONFIG } from './config.js';
import { ApiError, extractDocument } from './api.js';
import { storage } from './storage.js';
import { $, debounce, formatNumber } from './utils.js';
import { setFieldError, showToast } from './ui.js';

/** "12345 bytes" -> "12 KB" */
const formatSize = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`);

function describeFile(meta) {
  const parts = [meta.fileType?.toUpperCase()];
  if (meta.pages) parts.push(`${meta.pages} ${meta.pages === 1 ? 'página' : 'páginas'}`);
  parts.push(`${formatNumber(meta.chars)} caracteres extraídos`);
  return parts.filter(Boolean).join(' · ');
}

/** Validação no navegador, antes de gastar uma requisição. */
function validateFile(file) {
  const name = file.name.toLowerCase();
  const ext = name.slice(name.lastIndexOf('.'));
  if (!CONFIG.UPLOAD.extensions.includes(ext)) {
    const hint = ext === '.doc' ? ' Arquivos .doc antigos: salve como .docx no Word.' : '';
    return `Formato não suportado. Envie PDF, DOCX ou TXT.${hint}`;
  }
  if (file.size > CONFIG.UPLOAD.maxBytes) {
    return `O arquivo tem ${formatSize(file.size)}; o limite é ${formatSize(CONFIG.UPLOAD.maxBytes)}.`;
  }
  return null;
}

export class DocumentField {
  /**
   * @param {object} opts
   * @param {string} opts.key            'resume' | 'letter'
   * @param {HTMLElement} opts.card      section.doc-card
   * @param {HTMLTextAreaElement} opts.textarea
   * @param {HTMLElement} opts.errorEl
   * @param {HTMLElement} opts.savedPill
   * @param {string} opts.textKey        chave do localStorage para o texto
   * @param {string} opts.fileKey        chave do localStorage para os dados do arquivo
   * @param {(key: string) => void} opts.onChange  chamado quando o texto muda
   */
  constructor({ key, card, textarea, errorEl, savedPill, textKey, fileKey, onChange }) {
    Object.assign(this, { key, card, textarea, errorEl, savedPill, textKey, fileKey, onChange });
    this.dropzone = $('.dropzone', card);
    this.fileInput = $('input[type="file"]', card);
    this.controller = null;
    this.persist = debounce(() => this.#save(), 600);
    this.#bind();
  }

  get value() {
    return this.textarea.value.trim();
  }

  get isBusy() {
    return Boolean(this.controller);
  }

  restore() {
    this.textarea.value = storage.get(this.textKey, '');
    const meta = storage.get(this.fileKey);
    if (meta && this.textarea.value) this.#showFile(meta);
    this.onChange(this.key);
  }

  clear() {
    this.controller?.abort();
    this.textarea.value = '';
    storage.remove(this.textKey);
    storage.remove(this.fileKey);
    this.dropzone.dataset.state = 'idle';
    this.fileInput.value = '';
    setFieldError(this.textarea, this.errorEl, null);
    this.onChange(this.key);
  }

  /** Envia o arquivo ao backend e coloca o texto extraído no campo. */
  async load(file) {
    if (!file) return;
    setFieldError(this.textarea, this.errorEl, null);

    const invalid = validateFile(file);
    if (invalid) {
      setFieldError(this.textarea, this.errorEl, invalid);
      return;
    }

    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    const previousState = this.dropzone.dataset.state;
    this.dropzone.dataset.state = 'loading';
    $('.dropzone-loading .file-name', this.card).textContent = file.name;

    try {
      const doc = await extractDocument(file, controller.signal);
      this.textarea.value = doc.text;
      const meta = { name: doc.filename, fileType: doc.file_type, pages: doc.page_count, chars: doc.char_count };
      storage.set(this.fileKey, meta);
      this.#showFile(meta);
      this.#save();
      this.onChange(this.key);
      showToast(`Texto extraído de ${doc.filename}. Revise se quiser.`);
    } catch (error) {
      if (error instanceof ApiError && error.code === 'CANCELLED') return;
      this.dropzone.dataset.state = previousState === 'done' ? 'done' : 'idle';
      const message = error instanceof ApiError ? error.message : 'Não foi possível ler o arquivo.';
      setFieldError(this.textarea, this.errorEl, message);
      console.error('[ResuMatch] upload', error);
    } finally {
      if (this.controller === controller) this.controller = null;
      this.fileInput.value = ''; // permite reenviar o mesmo arquivo
    }
  }

  #showFile(meta) {
    $('.dropzone-done .file-name', this.card).textContent = meta.name;
    $('.dropzone-done .file-meta', this.card).textContent = describeFile(meta);
    this.dropzone.dataset.state = 'done';
  }

  #save() {
    storage.set(this.textKey, this.textarea.value);
    this.savedPill.classList.remove('opacity-0');
    setTimeout(() => this.savedPill.classList.add('opacity-0'), 1500);
  }

  #bind() {
    this.fileInput.addEventListener('change', () => this.load(this.fileInput.files[0]));

    this.textarea.addEventListener('input', () => {
      // Editou à mão depois do upload: o texto deixa de ser "o arquivo".
      if (this.dropzone.dataset.state === 'done' && !this.value) {
        this.dropzone.dataset.state = 'idle';
        storage.remove(this.fileKey);
      }
      this.persist();
      this.onChange(this.key);
    });

    // Arrastar e soltar em qualquer ponto do card.
    let depth = 0; // dragenter/dragleave disparam nos filhos; o contador evita "piscar"
    const hasFiles = (ev) => [...(ev.dataTransfer?.types ?? [])].includes('Files');
    this.card.addEventListener('dragenter', (ev) => {
      if (!hasFiles(ev)) return;
      ev.preventDefault();
      depth += 1;
      this.card.classList.add('is-dragover');
    });
    this.card.addEventListener('dragover', (ev) => {
      if (hasFiles(ev)) ev.preventDefault();
    });
    this.card.addEventListener('dragleave', () => {
      depth = Math.max(0, depth - 1);
      if (!depth) this.card.classList.remove('is-dragover');
    });
    this.card.addEventListener('drop', (ev) => {
      if (!hasFiles(ev)) return;
      ev.preventDefault();
      depth = 0;
      this.card.classList.remove('is-dragover');
      this.load(ev.dataTransfer.files[0]);
    });
  }
}
