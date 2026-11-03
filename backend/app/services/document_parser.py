"""
Leitura de documentos enviados pelo usuário (currículo mestre e carta padrão).

Formatos aceitos: PDF (com texto selecionável), DOCX e TXT. O tipo é decidido
pela extensão e confirmado pela assinatura do arquivo (magic bytes), então um
`.exe` renomeado para `.pdf` é recusado.

A leitura de PDF/DOCX é síncrona e pode levar alguns décimos de segundo, por
isso roda numa thread separada para não travar o event loop do FastAPI.
"""

import io
import logging
import re
import zipfile
from pathlib import PurePath

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import DocumentParsingError, FileTooLargeError, UnsupportedFileTypeError
from app.schemas.documents import DocumentType, ExtractedDocument

logger = logging.getLogger(__name__)

_EXTENSIONS = {".pdf": DocumentType.PDF, ".docx": DocumentType.DOCX, ".txt": DocumentType.TXT}
_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"  # DOCX é um ZIP
_TEXT_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")  # Bloco de Notas antigo salva em cp1252
_MIN_TEXT_CHARS = 30  # menos que isso = provavelmente PDF escaneado (imagem)


class DocumentParser:
    """Converte PDF, DOCX ou TXT em texto puro."""

    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max_bytes

    async def parse_upload(self, upload: UploadFile) -> ExtractedDocument:
        """Valida e lê um `UploadFile` do FastAPI."""
        filename = PurePath(upload.filename or "documento").name
        doc_type = self._detect_type(filename)
        content = await self._read_limited(upload, filename)
        return await run_in_threadpool(self.parse_bytes, content, filename, doc_type)

    def parse_bytes(self, content: bytes, filename: str, doc_type: DocumentType) -> ExtractedDocument:
        """Extrai o texto de um arquivo já carregado em memória."""
        if not content:
            raise DocumentParsingError(f"O arquivo '{filename}' está vazio.")

        pages: int | None = None
        if doc_type is DocumentType.PDF:
            text, pages = self._parse_pdf(content, filename)
        elif doc_type is DocumentType.DOCX:
            text = self._parse_docx(content, filename)
        else:
            text = self._parse_txt(content, filename)

        text = normalize_text(text)
        if len(text) < _MIN_TEXT_CHARS:
            hint = (
                " Se for um PDF escaneado (imagem), exporte-o de novo com texto selecionável "
                "ou cole o conteúdo manualmente."
                if doc_type is DocumentType.PDF
                else " Cole o conteúdo manualmente."
            )
            raise DocumentParsingError(f"Não encontramos texto legível em '{filename}'.{hint}")

        logger.info("Documento lido: %s (%s, %d caracteres)", filename, doc_type.value, len(text))
        return ExtractedDocument(filename=filename, file_type=doc_type, text=text, page_count=pages)

    # ------------------------------------------------------------------ validação

    @staticmethod
    def _detect_type(filename: str) -> DocumentType:
        suffix = PurePath(filename).suffix.lower()
        if suffix not in _EXTENSIONS:
            hint = " Arquivos .doc antigos: salve como .docx no Word." if suffix == ".doc" else ""
            raise UnsupportedFileTypeError(
                f"Formato '{suffix or 'sem extensão'}' não suportado. Envie PDF, DOCX ou TXT.{hint}"
            )
        return _EXTENSIONS[suffix]

    async def _read_limited(self, upload: UploadFile, filename: str) -> bytes:
        """Lê o arquivo em blocos e aborta assim que passar do limite."""
        chunks: list[bytes] = []
        total = 0
        while chunk := await upload.read(64 * 1024):
            total += len(chunk)
            if total > self._max_bytes:
                limit_mb = self._max_bytes / (1024 * 1024)
                raise FileTooLargeError(f"'{filename}' passa do limite de {limit_mb:g} MB.")
            chunks.append(chunk)
        return b"".join(chunks)

    # ------------------------------------------------------------------ parsers

    @staticmethod
    def _parse_pdf(content: bytes, filename: str) -> tuple[str, int]:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        if not content.startswith(_PDF_MAGIC):
            raise UnsupportedFileTypeError(f"'{filename}' não é um PDF válido.")
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                # PDFs com senha vazia (só restrição de cópia) ainda podem ser lidos.
                if not reader.decrypt(""):
                    raise DocumentParsingError(
                        f"'{filename}' está protegido por senha. Remova a senha ou cole o texto."
                    )
            pages = [page.extract_text() or "" for page in reader.pages]
        except DocumentParsingError:
            raise
        except (PdfReadError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Falha ao ler PDF %s: %s", filename, exc)
            raise DocumentParsingError(
                f"Não foi possível ler '{filename}'. O PDF pode estar corrompido."
            ) from exc
        return "\n\n".join(pages), len(pages)

    @staticmethod
    def _parse_docx(content: bytes, filename: str) -> str:
        from docx import Document

        if not content.startswith(_ZIP_MAGIC):
            raise UnsupportedFileTypeError(f"'{filename}' não é um DOCX válido.")
        try:
            document = Document(io.BytesIO(content))
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            logger.warning("Falha ao ler DOCX %s: %s", filename, exc)
            raise DocumentParsingError(
                f"Não foi possível ler '{filename}'. O arquivo pode estar corrompido."
            ) from exc

        lines = [p.text for p in document.paragraphs]
        # Muitos currículos usam tabelas para layout em colunas.
        for table in document.tables:
            for row in table.rows:
                cells = []
                for cell in row.cells:
                    if cell.text.strip() and cell.text not in cells:  # células mescladas se repetem
                        cells.append(cell.text)
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)

    @staticmethod
    def _parse_txt(content: bytes, filename: str) -> str:
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):  # BOM de UTF-16
            return content.decode("utf-16", errors="replace")
        if b"\x00" in content[:1024]:
            raise UnsupportedFileTypeError(f"'{filename}' não parece ser um arquivo de texto.")
        for encoding in _TEXT_ENCODINGS:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise DocumentParsingError(f"Não foi possível identificar a codificação de '{filename}'.")


def normalize_text(text: str) -> str:
    """Remove espaços sobrando e linhas em branco repetidas, preservando parágrafos."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[^\S\n]+", " ", text)  # espaços/tabs múltiplos -> 1 espaço
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
