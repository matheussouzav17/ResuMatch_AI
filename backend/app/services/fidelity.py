"""
Checagem determinística de fidelidade.

O system prompt já proíbe inventar dados, mas um modelo de linguagem não dá
garantia absoluta. Esta etapa confere, sem IA, se os fatos "duros" do
currículo adaptado (empresas, instituições de ensino e anos) existem no
currículo mestre. Qualquer divergência vira um alerta para o usuário revisar
antes de enviar o currículo.
"""

import re
import unicodedata

from app.schemas.resume import AdaptedResume

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_PLACEHOLDERS = {"", "-", "n/a", "na", "não informado", "nao informado", "not informed", "no informado"}


def _normalize(text: str) -> str:
    """Minúsculas, sem acentos e sem pontuação, para comparar com tolerância."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return f" {text.strip()} "


def _mentioned(value: str, source: str) -> bool:
    """`value` aparece no texto-fonte (comparação normalizada por palavras inteiras)."""
    needle = _normalize(value)
    return needle.strip() == "" or needle in source


def check_fidelity(resume: AdaptedResume, master_resume: str) -> list[str]:
    """Devolve alertas para fatos do currículo adaptado ausentes do currículo mestre."""
    source = _normalize(master_resume)
    source_years = set(_YEAR.findall(master_resume))
    warnings: list[str] = []

    def check_years(period: str, where: str) -> None:
        unknown = sorted(set(_YEAR.findall(period)) - source_years)
        if unknown:
            warnings.append(f"{where}: ano(s) {', '.join(unknown)} não aparece(m) no currículo mestre.")

    for exp in resume.experiences:
        label = f"Experiência '{exp.role}' em '{exp.company}'"
        if exp.company.strip().lower() not in _PLACEHOLDERS and not _mentioned(exp.company, source):
            warnings.append(f"{label}: a empresa não foi encontrada no currículo mestre.")
        check_years(exp.period, label)

    for edu in resume.education:
        label = f"Formação '{edu.degree}'"
        if edu.institution.strip().lower() not in _PLACEHOLDERS and not _mentioned(edu.institution, source):
            warnings.append(f"{label}: a instituição '{edu.institution}' não foi encontrada no currículo mestre.")
        check_years(edu.period, label)

    return warnings
