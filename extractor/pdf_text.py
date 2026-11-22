"""Read the text layer of a PDF."""
import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DocumentError(Exception):
    """The upload isn't a readable PDF, or it has no text to extract."""


MAX_PAGES = 20


def extract_text(pdf_bytes: bytes) -> str:
    if not pdf_bytes.startswith(b"%PDF"):
        raise DocumentError("File is not a PDF")
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = reader.pages[:MAX_PAGES]
        text = "\n\n".join((page.extract_text() or "").strip() for page in pages).strip()
    except PdfReadError as exc:
        raise DocumentError(f"Could not read PDF: {exc}") from exc
    if not text:
        raise DocumentError("PDF has no text layer (it may be a scan; run OCR first)")
    return text
