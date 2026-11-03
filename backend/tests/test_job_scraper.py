import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import JobExtractionError
from app.schemas.documents import JobSource
from app.services.job_scraper import JobScraper

DESCRIPTION_HTML = (
    "<p>Buscamos <strong>Desenvolvedor Backend</strong> para o time de pagamentos.</p>"
    "<ul><li>Python e FastAPI</li><li>Docker e PostgreSQL</li><li>Kubernetes (desejável)</li></ul>"
)

JSON_LD_PAGE = f"""<html><head><title>Vaga</title>
<script type="application/ld+json">{json.dumps({
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "Organization", "name": "Site"},
        {"@type": "JobPosting", "title": "Desenvolvedor Backend Pleno",
         "hiringOrganization": {"@type": "Organization", "name": "Empresa Alfa"},
         "description": DESCRIPTION_HTML},
    ],
})}</script></head><body><nav>Menu</nav><p>Outro conteúdo</p></body></html>"""

PLAIN_PAGE = """<html><head><meta property="og:title" content="Analista de Dados"></head><body>
<header>Login | Cadastre-se</header>
<main><h1>Analista de Dados</h1><p>Requisitos: <b>SQL</b>, Python, Power BI e comunicação.</p>
<p>Atividades: construir dashboards, modelar dados e apoiar as áreas de negócio com análises.</p></main>
<footer>Política de cookies</footer><script>var x = 1;</script></body></html>"""


def run(scraper: JobScraper, url: str):
    async def go():
        try:
            return await scraper.extract(url)
        finally:
            await scraper.close()

    return asyncio.run(go())


def make_scraper(handler, **overrides) -> JobScraper:
    settings = Settings(anthropic_api_key="sk-ant-test", job_fetch_allow_private_hosts=True, **overrides)
    return JobScraper(settings, transport=httpx.MockTransport(handler))


def html_response(body: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=body, headers={"content-type": "text/html; charset=utf-8"})


def test_prefers_json_ld():
    job = run(make_scraper(lambda req: html_response(JSON_LD_PAGE)), "https://vagas.exemplo.com/1")
    assert job.source is JobSource.STRUCTURED_DATA
    assert job.title == "Desenvolvedor Backend Pleno"
    assert job.company == "Empresa Alfa"
    assert "- Python e FastAPI" in job.text
    assert "Buscamos Desenvolvedor Backend para o time" in job.text  # inline <strong> na mesma linha
    assert "Menu" not in job.text


def test_falls_back_to_page_text():
    job = run(make_scraper(lambda req: html_response(PLAIN_PAGE)), "https://vagas.exemplo.com/2")
    assert job.source is JobSource.PAGE_TEXT
    assert job.title == "Analista de Dados"
    assert "Requisitos: SQL, Python" in job.text
    for noise in ("Login", "cookies", "var x"):
        assert noise not in job.text


def test_follows_redirects():
    def handler(request: httpx.Request):
        if request.url.path == "/curto":
            return httpx.Response(302, headers={"location": "/vaga"})
        return html_response(JSON_LD_PAGE)

    job = run(make_scraper(handler), "https://vagas.exemplo.com/curto")
    assert job.final_url == "https://vagas.exemplo.com/vaga"


@pytest.mark.parametrize("status, fragment", [(403, "bloqueia"), (999, "bloqueia"), (404, "não foi encontrada")])
def test_http_errors_ask_user_to_paste(status, fragment):
    with pytest.raises(JobExtractionError) as exc:
        run(make_scraper(lambda req: html_response("", status)), "https://vagas.exemplo.com/x")
    assert fragment in exc.value.message
    assert "cole" in exc.value.message


def test_javascript_only_page():
    page = '<html><body><div id="root"></div><script>render()</script></body></html>'
    with pytest.raises(JobExtractionError, match="JavaScript"):
        run(make_scraper(lambda req: html_response(page)), "https://vagas.exemplo.com/spa")


def test_rejects_non_html():
    def handler(request):
        return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})

    with pytest.raises(JobExtractionError, match="não é HTML"):
        run(make_scraper(handler), "https://vagas.exemplo.com/vaga.pdf")


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data", "http://localhost/x"]
)
def test_blocks_internal_addresses(url):
    settings = Settings(anthropic_api_key="sk-ant-test")  # proteção ligada (padrão)
    scraper = JobScraper(settings, transport=httpx.MockTransport(lambda req: html_response(JSON_LD_PAGE)))
    with pytest.raises(JobExtractionError, match="não é permitido"):
        run(scraper, url)


def test_blocks_redirect_to_internal_address():
    settings = Settings(anthropic_api_key="sk-ant-test")
    scraper = JobScraper(
        settings,
        transport=httpx.MockTransport(
            lambda req: httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
        ),
    )
    # 93.184.215.14 é público: passa na 1ª checagem, mas o redirect para loopback é barrado.
    with pytest.raises(JobExtractionError, match="não é permitido"):
        run(scraper, "http://93.184.215.14/vaga")


def test_rejects_custom_port():
    settings = Settings(anthropic_api_key="sk-ant-test")
    scraper = JobScraper(settings, transport=httpx.MockTransport(lambda req: html_response(JSON_LD_PAGE)))
    with pytest.raises(JobExtractionError, match="porta"):
        run(scraper, "http://93.184.215.14:8080/x")
