from app.api.dependencies import get_optimization_service
from app.main import app
from app.schemas.documents import ExtractedJob, JobSource
from app.schemas.resume import (
    AdaptedResume, AIOptimizationResult, Education, Experience, JobAnalysis, Keyword,
    MatchAnalysis, UsageMetadata,
)
from app.services.claude_service import AIGeneration
from app.services.fidelity import check_fidelity
from app.services.optimization_service import ResumeOptimizationService
from tests.conftest import JOB_DESCRIPTION, MASTER_RESUME


def adapted_resume(company="Empresa Alfa", period="2022 - 2025", institution="Universidade Federal Beta"):
    return AdaptedResume(
        full_name="Matheus Souza", headline="Desenvolvedor Backend", contact=["matheus@email.com"],
        professional_summary="...", skills=["Python", "FastAPI"],
        experiences=[Experience(role="Desenvolvedor Backend", company=company, period=period, bullets=["..."])],
        education=[Education(degree="Bacharelado", institution=institution, period="2018 - 2021")],
        certifications=[], languages=[],
    )


class FakeAI:
    def __init__(self, resume: AdaptedResume | None = None):
        self.calls = []
        self.resume = resume or adapted_resume()

    async def generate(self, request):
        self.calls.append(request)
        result = AIOptimizationResult(
            job_analysis=JobAnalysis(job_title="Dev Backend", seniority="pleno", keywords=[
                Keyword(term="Python", category="hard_skill", importance="required", present_in_resume=True, evidence="Python"),
                Keyword(term="Kubernetes", category="tool", importance="required", present_in_resume=False, evidence=None),
            ]),
            match=MatchAnalysis(score=70, strengths=["Python"], gaps=["Kubernetes"]),
            adapted_resume=self.resume,
            cover_letter="Carta" if request.include_cover_letter else None,
            suggestions=[],
        )
        return AIGeneration(result, UsageMetadata(model="fake", input_tokens=1, output_tokens=1, processing_time_ms=1))


class FakeScraper:
    def __init__(self):
        self.urls = []

    async def extract(self, url):
        self.urls.append(url)
        return ExtractedJob(url=url, final_url=url, title="Dev", company=None, text=JOB_DESCRIPTION,
                            source=JobSource.STRUCTURED_DATA)


def use_fakes(ai=None, scraper=None):
    ai, scraper = ai or FakeAI(), scraper or FakeScraper()
    service = ResumeOptimizationService(ai, scraper)
    app.dependency_overrides[get_optimization_service] = lambda: service
    return ai, scraper


def test_optimize_with_text_and_cover_letter_template(client):
    ai, scraper = use_fakes()
    response = client.post("/api/v1/resume/optimize", json={
        "master_resume": MASTER_RESUME, "job_description": JOB_DESCRIPTION,
        "cover_letter_template": "Prezados, sou apaixonado por backend.",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["keyword_coverage"] == 50.0
    assert body["fidelity_warnings"] == []
    assert body["job_origin"] == {"type": "text", "url": None, "source": None}
    assert ai.calls[0].cover_letter_template == "Prezados, sou apaixonado por backend."
    assert scraper.urls == []


def test_optimize_with_url_only(client):
    ai, scraper = use_fakes()
    response = client.post("/api/v1/resume/optimize", json={
        "master_resume": MASTER_RESUME, "job_url": "https://vagas.exemplo.com/123",
    })
    assert response.status_code == 200, response.text
    assert scraper.urls == ["https://vagas.exemplo.com/123"]
    assert ai.calls[0].job_description == JOB_DESCRIPTION
    assert response.json()["job_origin"]["source"] == "structured_data"


def test_requires_job_text_or_url(client):
    use_fakes()
    response = client.post("/api/v1/resume/optimize", json={"master_resume": MASTER_RESUME, "job_description": "  "})
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] is None


def test_upload_endpoint_with_files(client):
    ai, _ = use_fakes()
    response = client.post(
        "/api/v1/resume/optimize/upload",
        data={"job_description": JOB_DESCRIPTION, "include_cover_letter": "false", "language": "en"},
        files={
            "master_resume_file": ("cv.txt", MASTER_RESUME.encode()),
            "cover_letter_file": ("carta.txt", "Prezados, esta é a minha carta de apresentação padrão.".encode()),
        },
    )
    assert response.status_code == 200, response.text
    assert ai.calls[0].master_resume.startswith("Matheus Souza")
    assert ai.calls[0].language.value == "en"
    assert response.json()["cover_letter"] is None


def test_upload_endpoint_validation(client):
    use_fakes()
    response = client.post("/api/v1/resume/optimize/upload", data={"job_description": JOB_DESCRIPTION})
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "master_resume"


def test_fidelity_flags_invented_company_and_year():
    resume = adapted_resume(company="Google", period="2019 - 2025", institution="MIT")
    warnings = check_fidelity(resume, MASTER_RESUME)
    assert any("Google" in w for w in warnings)
    assert any("2019" in w for w in warnings)
    assert any("MIT" in w for w in warnings)


def test_fidelity_tolerates_accents_and_case():
    resume = adapted_resume(company="EMPRESA ALFA", institution="Universidade Federal Beta")
    assert check_fidelity(resume, MASTER_RESUME) == []
