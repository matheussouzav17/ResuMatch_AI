import io

import pytest
from docx import Document

from app.core.exceptions import DocumentParsingError, UnsupportedFileTypeError
from app.schemas.documents import DocumentType
from app.services.document_parser import DocumentParser, normalize_text

parser = DocumentParser(max_bytes=1024 * 1024)
TEXT = "Matheus Souza - Desenvolvedor Python com experiência em FastAPI"


def make_pdf(text: str) -> bytes:
    """PDF mínimo de uma página com texto selecionável (sem dependências extras)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref))
    return out.getvalue()


def make_docx(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Skills"
    table.rows[0].cells[1].text = "Docker, PostgreSQL"
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_pdf():
    result = parser.parse_bytes(make_pdf(TEXT), "cv.pdf", DocumentType.PDF)
    assert "Desenvolvedor Python" in result.text
    assert result.page_count == 1


def test_docx_includes_tables():
    result = parser.parse_bytes(make_docx(TEXT), "cv.docx", DocumentType.DOCX)
    assert TEXT in result.text
    assert "Skills | Docker, PostgreSQL" in result.text


def test_txt_windows_encoding():
    result = parser.parse_bytes(TEXT.encode("cp1252"), "cv.txt", DocumentType.TXT)
    assert result.text == TEXT


def test_renamed_file_is_rejected():
    with pytest.raises(UnsupportedFileTypeError):
        parser.parse_bytes(b"MZ\x90\x00 executable", "cv.pdf", DocumentType.PDF)


def test_pdf_without_text():
    with pytest.raises(DocumentParsingError):
        parser.parse_bytes(make_pdf(""), "scan.pdf", DocumentType.PDF)


def test_normalize_text():
    assert normalize_text("  a\t\tb \r\n\r\n\r\n\r\nc ") == "a b\n\nc"


def test_upload_endpoint(client):
    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("curriculo.docx", make_docx(TEXT), "application/octet-stream")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["file_type"] == "docx" and body["char_count"] == len(body["text"])


def test_upload_rejects_unknown_extension(client):
    response = client.post("/api/v1/documents/extract", files={"file": ("foto.png", b"\x89PNG")})
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_upload_size_limit(client):
    original = client.app.state.document_parser
    client.app.state.document_parser = DocumentParser(max_bytes=10)
    try:
        response = client.post("/api/v1/documents/extract", files={"file": ("cv.txt", b"x" * 100)})
    finally:
        client.app.state.document_parser = original
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"

