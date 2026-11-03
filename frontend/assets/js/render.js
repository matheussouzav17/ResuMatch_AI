/**
 * Renderização dos resultados (funções puras: recebem dados, devolvem HTML/texto).
 *
 * Todo texto vindo da API passa por `escapeHtml` antes de entrar no HTML.
 */
import { escapeHtml as e, formatDuration, formatNumber } from './utils.js';

/* ------------------------------------------------------------------ rótulos */

/** Títulos das seções do currículo no idioma em que ele foi gerado. */
const DOC_LABELS = {
  'pt-BR': {
    summary: 'Resumo profissional', skills: 'Habilidades', experience: 'Experiência profissional',
    education: 'Formação acadêmica', certifications: 'Certificações', languages: 'Idiomas',
  },
  en: {
    summary: 'Professional summary', skills: 'Skills', experience: 'Professional experience',
    education: 'Education', certifications: 'Certifications', languages: 'Languages',
  },
  es: {
    summary: 'Resumen profesional', skills: 'Habilidades', experience: 'Experiencia profesional',
    education: 'Formación académica', certifications: 'Certificaciones', languages: 'Idiomas',
  },
};

const CATEGORY_LABELS = {
  hard_skill: 'Hard skill',
  soft_skill: 'Soft skill',
  tool: 'Ferramenta',
  certification: 'Certificação',
  domain: 'Domínio',
};

const labelsFor = (lang) => DOC_LABELS[lang] ?? DOC_LABELS['pt-BR'];

/* ------------------------------------------------------------------ ícones */

const ICONS = {
  copy: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
  download: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v12m0 0-4-4m4 4 4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>',
  print: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="7"/></svg>',
  check: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M20 6 9 17l-5-5"/></svg>',
  cross: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  spark: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.9 5.8L20 9.7l-5 3.9 1.8 6.4L12 16.3 7.2 20l1.8-6.4-5-3.9 6.1-1.9z"/></svg>',
  warn: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>',
};

/** Botão de ação com `data-action`, tratado por delegação de eventos em main.js. */
const actionButton = (action, icon, label) =>
  `<button type="button" class="btn-ghost" data-action="${action}" data-label="${e(label)}">${ICONS[icon]}<span>${e(label)}</span></button>`;

/* ------------------------------------------------------------------ resumo */

/** Faixa de cor e rótulo para o score de aderência. */
function scoreBand(score) {
  if (score >= 75) return { color: '#10b981', text: 'Alta aderência', tone: 'text-emerald-600' };
  if (score >= 50) return { color: '#f59e0b', text: 'Aderência média', tone: 'text-amber-600' };
  return { color: '#f43f5e', text: 'Baixa aderência', tone: 'text-rose-600' };
}

/** Três cards no topo: score, cobertura de palavras-chave e a vaga. */
export function renderSummaryCards(data) {
  const score = Math.max(0, Math.min(100, Math.round(data.match?.score ?? 0)));
  const band = scoreBand(score);
  const keywords = data.job_analysis?.keywords ?? [];
  const present = keywords.filter((k) => k.present_in_resume).length;
  const coverage = Math.round(data.keyword_coverage ?? 0);
  const missingRequired = keywords.filter((k) => !k.present_in_resume && k.importance === 'required').length;

  // Anel SVG: circunferência de r=34 ≈ 213.6. O offset final é aplicado depois (animação).
  const C = 2 * Math.PI * 34;

  return `
    <article class="flex items-center gap-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <div class="relative h-20 w-20 shrink-0">
        <svg class="score-ring h-20 w-20 -rotate-90" viewBox="0 0 80 80" aria-hidden="true">
          <circle cx="40" cy="40" r="34" fill="none" stroke="#e2e8f0" stroke-width="8"/>
          <circle cx="40" cy="40" r="34" fill="none" stroke="${band.color}" stroke-width="8" stroke-linecap="round"
            stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${C.toFixed(1)}" data-target-offset="${(C * (1 - score / 100)).toFixed(1)}"/>
        </svg>
        <span class="absolute inset-0 grid place-items-center text-xl font-bold text-slate-900">${score}</span>
      </div>
      <div>
        <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Score de aderência</p>
        <p class="mt-1 text-lg font-bold ${band.tone}">${band.text}</p>
        <p class="mt-0.5 text-xs text-slate-500">${data.match?.strengths?.length ?? 0} pontos fortes · ${data.match?.gaps?.length ?? 0} lacunas</p>
      </div>
    </article>

    <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Cobertura de palavras-chave</p>
      <p class="mt-2 flex items-baseline gap-1.5"><span class="text-3xl font-bold text-slate-900">${coverage}%</span>
        <span class="text-sm text-slate-500">${present} de ${keywords.length}</span></p>
      <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div class="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500 transition-all duration-1000" style="width:0" data-target-width="${coverage}%"></div>
      </div>
      <p class="mt-2 text-xs text-slate-500">${missingRequired ? `${missingRequired} obrigatória(s) sem evidência` : 'Todas as obrigatórias comprovadas'}</p>
    </article>

    <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Vaga analisada</p>
      <p class="mt-2 line-clamp-2 text-lg font-bold leading-snug text-slate-900">${e(data.job_analysis?.job_title || 'Vaga')}</p>
      <span class="mt-2 inline-flex items-center rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold capitalize text-brand-700">${e(data.job_analysis?.seniority || 'não informado')}</span>
    </article>`;
}

/** Linha de metadados: origem da vaga, modelo, tempo e tokens (texto puro, vai em textContent). */
export function renderMeta(meta, origin) {
  if (!meta) return '';
  const tokens = (meta.input_tokens ?? 0) + (meta.output_tokens ?? 0);
  const parts = [meta.model, formatDuration(meta.processing_time_ms), `${formatNumber(tokens)} tokens`];
  const host = hostOf(origin?.url);
  if (host) parts.unshift(`Vaga de ${host}`);
  return parts.join(' · ');
}

/** "https://www.empresa.gupy.io/jobs/1" -> "empresa.gupy.io" (ou null). */
export function hostOf(url) {
  try {
    return url ? new URL(url).hostname.replace(/^www\./, '') : null;
  } catch {
    return null;
  }
}

/** Alertas da checagem automática de fidelidade (backend compara com o currículo mestre). */
function fidelityNotice(warnings) {
  if (!Array.isArray(warnings)) return ''; // resultado salvo por uma versão anterior da API
  if (!warnings.length) {
    return `
      <div class="mb-8 flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/60 px-4 py-3 text-sm text-emerald-800">
        <span class="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-100 text-emerald-600">${ICONS.check}</span>
        <span><strong class="font-semibold">Checagem de fidelidade OK.</strong> Empresas, instituições e anos do currículo otimizado batem com o seu currículo mestre.</span>
      </div>`;
  }
  return `
    <div class="mb-8 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="note">
      <p class="flex items-center gap-2 font-semibold">${ICONS.warn} Revise antes de enviar: possíveis dados fora do currículo mestre</p>
      <ul class="mt-2 list-disc space-y-1 pl-6 text-amber-800">${warnings.map((w) => `<li>${e(w)}</li>`).join('')}</ul>
    </div>`;
}

/* ------------------------------------------------------------------ aba 1: análise */

function keywordItem(k) {
  const ok = k.present_in_resume;
  const importance = k.importance === 'required'
    ? '<span class="rounded-md bg-slate-900 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">Obrigatória</span>'
    : '<span class="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Desejável</span>';
  const evidence = ok && k.evidence
    ? `<p class="mt-1.5 border-l-2 border-emerald-200 pl-2.5 text-xs italic leading-relaxed text-slate-500">“${e(k.evidence)}”</p>`
    : !ok ? '<p class="mt-1 text-xs text-amber-700">Sem evidência no seu currículo mestre</p>' : '';

  return `
    <li class="keyword-item rounded-xl border ${ok ? 'border-slate-200 bg-white' : 'border-amber-200 bg-amber-50/50'} p-3" data-present="${ok}">
      <div class="flex items-start gap-2.5">
        <span class="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full ${ok ? 'bg-emerald-100 text-emerald-600' : 'bg-amber-100 text-amber-600'}">${ok ? ICONS.check : ICONS.cross}</span>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="font-semibold text-slate-900">${e(k.term)}</span>
            ${importance}
            <span class="text-[11px] font-medium text-slate-400">${e(CATEGORY_LABELS[k.category] ?? k.category)}</span>
          </div>
          ${evidence}
        </div>
      </div>
    </li>`;
}

function insightList(title, items, tone, icon) {
  const tones = {
    green: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    brand: 'bg-brand-50 text-brand-600',
  };
  const body = items?.length
    ? `<ul class="space-y-2.5">${items.map((t) => `
        <li class="flex gap-2.5 text-sm leading-relaxed text-slate-700">
          <span class="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md ${tones[tone]}">${ICONS[icon]}</span>
          <span>${e(t)}</span>
        </li>`).join('')}</ul>`
    : '<p class="text-sm text-slate-400">Nada a destacar.</p>';
  return `
    <div class="rounded-2xl border border-slate-200 p-5">
      <h4 class="mb-3 text-sm font-bold text-slate-900">${e(title)}</h4>
      ${body}
    </div>`;
}

export function renderAnalysisPanel(data) {
  // Obrigatórias primeiro; dentro de cada grupo, as ausentes antes (o que mais pede atenção).
  const keywords = [...(data.job_analysis?.keywords ?? [])].sort((a, b) =>
    (a.importance === 'required' ? 0 : 1) - (b.importance === 'required' ? 0 : 1)
    || Number(a.present_in_resume) - Number(b.present_in_resume));
  const present = keywords.filter((k) => k.present_in_resume).length;
  const missing = keywords.length - present;

  const filter = (value, label, count, active = false) => `
    <button type="button" class="keyword-filter rounded-full px-3 py-1 text-xs font-semibold transition
      ${active ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}"
      data-filter="${value}" aria-pressed="${active}">${label} <span class="opacity-60">${count}</span></button>`;

  return `
    ${fidelityNotice(data.fidelity_warnings)}
    <div class="grid gap-8 lg:grid-cols-5">
      <div class="lg:col-span-3">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 class="text-base font-bold text-slate-900">Palavras-chave da vaga</h3>
            <p class="text-xs text-slate-500">Cada termo comprovado traz o trecho do seu currículo que o sustenta.</p>
          </div>
          ${actionButton('copy-keywords', 'copy', 'Copiar termos')}
        </div>
        <div class="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filtrar palavras-chave">
          ${filter('all', 'Todas', keywords.length, true)}
          ${filter('true', 'Presentes', present)}
          ${filter('false', 'Ausentes', missing)}
        </div>
        <ul id="keyword-list" class="space-y-2">${keywords.map(keywordItem).join('')}</ul>
      </div>

      <div class="space-y-4 lg:col-span-2">
        ${insightList('Pontos fortes', data.match?.strengths, 'green', 'check')}
        ${insightList('Lacunas em relação à vaga', data.match?.gaps, 'amber', 'warn')}
        ${insightList('Sugestões', data.suggestions, 'brand', 'spark')}
      </div>
    </div>`;
}

/* ------------------------------------------------------------------ aba 2: currículo */

const toolbar = (buttons) =>
  `<div class="mb-6 flex flex-wrap justify-end gap-2 no-print">${buttons.join('')}</div>`;

export function renderResumePanel(resume, lang) {
  if (!resume) return '<p class="text-sm text-slate-500">Currículo não retornado pela API.</p>';
  const L = labelsFor(lang);
  const section = (title, html) => (html ? `<h3 class="doc-section-title">${e(title)}</h3>${html}` : '');

  const skills = resume.skills?.length
    ? `<div class="flex flex-wrap gap-1.5">${resume.skills.map((s) =>
        `<span class="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[13px] text-slate-700">${e(s)}</span>`).join('')}</div>`
    : '';

  const experiences = (resume.experiences ?? []).map((x) => `
    <div class="mb-5 last:mb-0">
      <div class="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between">
        <p class="font-semibold text-slate-900">${e(x.role)} <span class="font-normal text-slate-500">· ${e(x.company)}</span></p>
        <p class="shrink-0 text-xs font-medium text-slate-400">${e(x.period)}</p>
      </div>
      <ul class="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-slate-700 marker:text-brand-400">
        ${(x.bullets ?? []).map((b) => `<li>${e(b)}</li>`).join('')}
      </ul>
    </div>`).join('');

  const education = (resume.education ?? []).map((ed) => `
    <div class="mb-2 flex flex-col gap-0.5 text-sm sm:flex-row sm:items-baseline sm:justify-between">
      <p><span class="font-semibold text-slate-900">${e(ed.degree)}</span> <span class="text-slate-500">· ${e(ed.institution)}</span></p>
      <p class="shrink-0 text-xs font-medium text-slate-400">${e(ed.period)}</p>
    </div>`).join('');

  const simpleList = (items) => (items?.length
    ? `<ul class="list-disc space-y-1 pl-5 text-sm text-slate-700 marker:text-brand-400">${items.map((i) => `<li>${e(i)}</li>`).join('')}</ul>`
    : '');

  return `
    ${toolbar([
      actionButton('copy-resume', 'copy', 'Copiar currículo'),
      actionButton('download-resume', 'download', 'Baixar .txt'),
      actionButton('print', 'print', 'Imprimir / PDF'),
    ])}
    <article class="paper" id="resume-doc">
      <header class="text-center">
        <h2 class="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">${e(resume.full_name)}</h2>
        <p class="mt-1 text-base font-medium text-brand-700">${e(resume.headline)}</p>
        <p class="mt-2 text-xs text-slate-500">${(resume.contact ?? []).map(e).join('<span class="mx-2 text-slate-300">|</span>')}</p>
      </header>
      ${section(L.summary, resume.professional_summary ? `<p class="text-sm leading-relaxed text-slate-700">${e(resume.professional_summary)}</p>` : '')}
      ${section(L.skills, skills)}
      ${section(L.experience, experiences)}
      ${section(L.education, education)}
      ${section(L.certifications, simpleList(resume.certifications))}
      ${section(L.languages, simpleList(resume.languages))}
    </article>`;
}

/**
 * Versão em texto puro do currículo, pensada para colar em portais/ATS
 * (sem tabelas, sem colunas, títulos em caixa alta).
 */
export function resumeToPlainText(resume, lang) {
  if (!resume) return '';
  const L = labelsFor(lang);
  const out = [];
  const heading = (t) => out.push('', t.toUpperCase());

  out.push(resume.full_name, resume.headline);
  if (resume.contact?.length) out.push(resume.contact.join(' | '));

  if (resume.professional_summary) { heading(L.summary); out.push(resume.professional_summary); }
  if (resume.skills?.length) { heading(L.skills); out.push(resume.skills.join(' • ')); }
  if (resume.experiences?.length) {
    heading(L.experience);
    resume.experiences.forEach((x, i) => {
      if (i) out.push('');
      out.push(`${x.role} | ${x.company} | ${x.period}`);
      (x.bullets ?? []).forEach((b) => out.push(`• ${b}`));
    });
  }
  if (resume.education?.length) {
    heading(L.education);
    resume.education.forEach((ed) => out.push(`${ed.degree} | ${ed.institution} | ${ed.period}`));
  }
  if (resume.certifications?.length) { heading(L.certifications); resume.certifications.forEach((c) => out.push(`• ${c}`)); }
  if (resume.languages?.length) { heading(L.languages); resume.languages.forEach((l) => out.push(`• ${l}`)); }

  return out.filter((line) => line !== undefined && line !== null).join('\n').trim();
}

/* ------------------------------------------------------------------ aba 3: carta */

export function renderLetterPanel(letter) {
  if (!letter) {
    return `
      <div class="mx-auto max-w-md py-10 text-center">
        <span class="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 text-slate-400">
          <svg class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>
        </span>
        <h3 class="mt-4 font-semibold text-slate-900">Carta não gerada</h3>
        <p class="mt-1 text-sm text-slate-500">Ative “Gerar carta de apresentação” e gere novamente para recebê-la.</p>
      </div>`;
  }
  const paragraphs = letter.split(/\n{2,}/).map((p) =>
    `<p class="mb-4 whitespace-pre-line last:mb-0">${e(p.trim())}</p>`).join('');
  return `
    ${toolbar([
      actionButton('copy-letter', 'copy', 'Copiar carta'),
      actionButton('download-letter', 'download', 'Baixar .txt'),
      actionButton('print', 'print', 'Imprimir / PDF'),
    ])}
    <article class="paper text-[15px] leading-relaxed text-slate-700">${paragraphs}</article>`;
}
