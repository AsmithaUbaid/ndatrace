"""
PDF text extraction (WBS T034 support) - lets the review UI accept an
uploaded NDA PDF, not just pasted text. Extracts plain text only; the
rest of the pipeline (retriever/classifier/agent) never needs to know
whether the text originally came from a PDF or a textarea.

Deliberately does not attempt OCR - the ContractNLI-style NDAs this
project targets are born-digital text, not scanned images. A PDF with no
extractable text layer raises a clear error rather than silently
returning an empty document.
"""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfExtractionError(Exception):
    """Raised when a PDF can't be read or has no extractable text."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
    except PdfReadError as e:
        raise PdfExtractionError(f"Could not read PDF: {e}") from e

    if reader.is_encrypted:
        raise PdfExtractionError("This PDF is password-protected - upload an unprotected file.")

    pages_text = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(t for t in pages_text if t)

    if not text:
        raise PdfExtractionError(
            "No extractable text found in this PDF - it may be a scanned image, which needs OCR "
            "(not supported). Try pasting the text directly instead."
        )
    return text
