"""
Extração da descrição de uma vaga a partir do link do anúncio.

Estratégia, da mais confiável para a menos confiável:
1. Dados estruturados `schema.org/JobPosting` (JSON-LD). A maioria dos sites de
   vagas (Gupy, Greenhouse, Lever, Indeed, sites de carreira) publica esse
   bloco para o Google for Jobs, com título, empresa e descrição completos.
2. Texto visível da página, sem menus, rodapés, scripts e formulários.

Limitações conhecidas (e tratadas com mensagens claras para o usuário colar o
texto manualmente): sites que exigem login (LinkedIn logado), bloqueiam robôs
(403/429/999) ou montam a página só com JavaScript.

Segurança (SSRF): o backend faz requisições para URLs enviadas pelo usuário,
então só aceita http/https em portas padrão e recusa qualquer host que resolva
para IP privado, loopback ou link-local (ex.: 127.0.0.1, 10.x, 169.254.169.254),
inclusive depois de redirecionamentos.
"""

import asyncio
import ipaddress
import json
import logging
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.core.config import Settings
from app.core.exceptions import JobExtractionError
from app.schemas.documents import ExtractedJob, JobSource
from app.schemas.resume import JOB_MAX, JOB_MIN
from app.services.document_parser import normalize_text

logger = logging.getLogger(__name__)

_MAX_REDIRECTS = 5
_ALLOWED_PORTS = {None, 80, 443}
_HEADERS = {
    # Identificação de navegador comum: muitos sites recusam clientes HTTP "crus".
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0 Safari/537.36 ResuMatchAI/2.0"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
_NOISE_TAGS = [
    "script", "style", "noscript", "template", "svg", "canvas", "iframe",
    "nav", "header", "footer", "aside", "form", "button", "select",
]
_PASTE_HINT = "Abra a vaga no navegador, copie o texto do anúncio e cole no campo de descrição."


class JobScraper:
    """Busca uma página de vaga e devolve a descrição em texto puro."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            transport=transport,  # injetável nos testes (httpx.MockTransport)
            headers=_HEADERS,
            timeout=httpx.Timeout(settings.job_fetch_timeout_seconds, connect=8.0),
            # Redirecionamentos são seguidos manualmente para validar cada destino (SSRF).
            follow_redirects=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def extract(self, url: str) -> ExtractedJob:
        html, final_url, content_type = await self._fetch(url)

        if "html" in content_type:
            job = _from_json_ld(html) or _from_page_text(html)
        else:  # text/plain
            job = {"title": None, "company": None, "text": html, "source": JobSource.PAGE_TEXT}

        text = normalize_text(job["text"])
        if len(text) < JOB_MIN:
            raise JobExtractionError(
                "A página abriu, mas não encontramos a descrição da vaga nela. O site "
                "provavelmente carrega o conteúdo com JavaScript ou exige login. " + _PASTE_HINT,
                details={"url": url},
            )
        if len(text) > JOB_MAX:
            text = text[:JOB_MAX].rsplit("\n", 1)[0]

        logger.info("Vaga extraída de %s (%s, %d caracteres)", final_url, job["source"].value, len(text))
        return ExtractedJob(
            url=url,
            final_url=final_url,
            title=job["title"],
            company=job["company"],
            text=text,
            source=job["source"],
        )

    # ------------------------------------------------------------------ HTTP

    async def _fetch(self, url: str) -> tuple[str, str, str]:
        """GET com validação de SSRF a cada salto, limite de tamanho e erros amigáveis."""
        current = url
        for _ in range(_MAX_REDIRECTS + 1):
            await self._ensure_public_url(current)
            try:
                async with self._client.stream("GET", current) as response:
                    if response.is_redirect and "location" in response.headers:
                        current = urljoin(current, response.headers["location"])
                        continue
                    self._raise_for_status(response.status_code, url)
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type and not any(t in content_type for t in ("html", "text/plain")):
                        raise JobExtractionError(
                            "O link não aponta para uma página de vaga (o conteúdo não é HTML). "
                            + _PASTE_HINT,
                            details={"url": url, "content_type": content_type},
                        )
                    body = await self._read_limited(response)
                    encoding = response.encoding or "utf-8"
                    return body.decode(encoding, errors="replace"), current, content_type or "text/html"
            except httpx.TimeoutException as exc:
                raise JobExtractionError(
                    "O site da vaga demorou demais para responder. " + _PASTE_HINT,
                    details={"url": url},
                ) from exc
            except httpx.HTTPError as exc:
                logger.info("Falha ao acessar %s: %s", url, exc)
                raise JobExtractionError(
                    "Não foi possível acessar o link da vaga. Confira se o endereço está correto. "
                    + _PASTE_HINT,
                    details={"url": url},
                ) from exc
        raise JobExtractionError("O link redirecionou vezes demais. " + _PASTE_HINT, details={"url": url})

    @staticmethod
    def _raise_for_status(status_code: int, url: str) -> None:
        if status_code < 400:
            return
        if status_code in (401, 403, 429, 999):  # 999 = bloqueio de robôs do LinkedIn
            message = "Este site bloqueia a leitura automática de vagas (ou exige login). "
        elif status_code in (404, 410):
            message = "A vaga não foi encontrada no link informado (pode ter sido encerrada). "
        else:
            message = f"O site da vaga respondeu com erro {status_code}. "
        raise JobExtractionError(message + _PASTE_HINT, details={"url": url, "status": status_code})

    async def _read_limited(self, response: httpx.Response) -> bytes:
        limit = self._settings.job_fetch_max_bytes
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > limit:
                break  # páginas enormes: o começo basta para achar a vaga
            chunks.append(chunk)
        return b"".join(chunks)

    async def _ensure_public_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise JobExtractionError("Informe um link começando com http:// ou https://.", details={"url": url})
        if self._settings.job_fetch_allow_private_hosts:
            return  # modo de desenvolvimento/testes: sem restrição de host ou porta
        if parts.port not in _ALLOWED_PORTS:
            raise JobExtractionError("Links com porta personalizada não são aceitos.", details={"url": url})

        try:
            infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise JobExtractionError(
                f"O endereço '{parts.hostname}' não foi encontrado. Confira o link.",
                details={"url": url},
            ) from exc

        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                logger.warning("URL bloqueada (SSRF): %s -> %s", url, ip)
                raise JobExtractionError("Este endereço não é permitido.", details={"url": url})


# ---------------------------------------------------------------------- parsing


def _from_json_ld(html: str) -> dict | None:
    """Procura um bloco schema.org/JobPosting em <script type="application/ld+json">."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        posting = _find_job_posting(data)
        if not posting:
            continue

        description = _html_to_text(str(posting.get("description") or ""))
        extra = [
            f"{label}:\n{_html_to_text(str(posting[key]))}"
            for key, label in (
                ("qualifications", "Qualificações"),
                ("skills", "Competências"),
                ("responsibilities", "Responsabilidades"),
                ("experienceRequirements", "Experiência"),
            )
            if isinstance(posting.get(key), str) and posting[key].strip()
        ]
        org = posting.get("hiringOrganization")
        company = org.get("name") if isinstance(org, dict) else org if isinstance(org, str) else None
        title = posting.get("title")

        header = "\n".join(filter(None, [f"Vaga: {title}" if title else None, f"Empresa: {company}" if company else None]))
        text = "\n\n".join(filter(None, [header, description, *extra]))
        if len(text) >= JOB_MIN:
            return {"title": title, "company": company, "text": text, "source": JobSource.STRUCTURED_DATA}
    return None


def _find_job_posting(data: object) -> dict | None:
    """O JSON-LD pode vir como objeto, lista ou dentro de "@graph"."""
    if isinstance(data, list):
        return next((p for item in data if (p := _find_job_posting(item))), None)
    if isinstance(data, dict):
        kind = data.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "JobPosting" in kinds:
            return data
        if "@graph" in data:
            return _find_job_posting(data["@graph"])
    return None


def _from_page_text(html: str) -> dict:
    """Fallback: texto visível do conteúdo principal da página."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("meta", property="og:title") or soup.find("title")
    title = (title_tag.get("content") if title_tag.name == "meta" else title_tag.get_text()) if title_tag else None

    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
    return {
        "title": title.strip() if title else None,
        "company": None,
        "text": _visible_text(root),
        "source": JobSource.PAGE_TEXT,
    }


def _html_to_text(fragment: str) -> str:
    """A descrição do JSON-LD costuma vir em HTML (com <p>, <li>, entidades)."""
    return _visible_text(BeautifulSoup(fragment, "html.parser"))


_BLOCK_TAGS = [
    "p", "div", "section", "li", "ul", "ol", "tr", "table", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt", "blockquote", "pre",
]


def _visible_text(node) -> str:
    """
    Converte HTML em texto mantendo a estrutura: blocos viram quebras de linha,
    itens de lista viram "- item" e elementos inline (<strong>, <a>) continuam
    na mesma linha.
    """
    for li in node.find_all("li"):
        li.insert(0, "- ")
    for block in node.find_all(_BLOCK_TAGS):
        block.append("\n")
    return node.get_text()
