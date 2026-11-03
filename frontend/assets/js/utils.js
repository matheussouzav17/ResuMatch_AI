/**
 * Utilitários genéricos (sem dependência de DOM específico do app).
 */

/** Escapa texto vindo da API antes de interpolar em HTML (evita XSS). */
export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

/** Atalho para querySelector. */
export const $ = (selector, root = document) => root.querySelector(selector);

/** Debounce simples (usado para salvar o currículo enquanto o usuário digita). */
export function debounce(fn, wait = 400) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

/** Formata números no padrão brasileiro (1.234). */
export const formatNumber = (n) => new Intl.NumberFormat('pt-BR').format(n ?? 0);

/** 41250 ms -> "41 s"; 75000 ms -> "1 min 15 s". */
export function formatDuration(ms) {
  const total = Math.round((ms ?? 0) / 1000);
  if (total < 60) return `${total} s`;
  const min = Math.floor(total / 60);
  const sec = total % 60;
  return sec ? `${min} min ${sec} s` : `${min} min`;
}

/**
 * Copia texto para a área de transferência.
 * Usa a Clipboard API e cai para execCommand em contextos sem permissão.
 */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const helper = document.createElement('textarea');
    helper.value = text;
    helper.setAttribute('readonly', '');
    helper.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
    document.body.appendChild(helper);
    helper.select();
    const ok = document.execCommand('copy');
    helper.remove();
    return ok;
  }
}

/** Gera o download de um arquivo .txt no navegador. */
export function downloadText(filename, text) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** "Desenvolvedor Backend Pleno" -> "desenvolvedor-backend-pleno" (para nomes de arquivo). */
export function slugify(text) {
  return String(text ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'documento';
}
