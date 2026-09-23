"""
Unit tests for pipeline/pdf_extractor.py.

Builds real, minimal-but-valid PDF byte strings by hand (raw PDF syntax)
rather than depending on a PDF-generation library (reportlab isn't a
project dependency) - pypdf parses these correctly, verified directly.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfWriter

from pipeline.pdf_extractor import PdfExtractionError, extract_text_from_pdf


def make_pdf_with_text(text: str) -> bytes:
    """A minimal single-page PDF containing exactly `text` as extractable content."""
    content = f"BT /F1 12 Tf 50 100 Td ({text}) Tj ET".encode()
    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 200 200] /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"5 0 obj\n<< /Length %d >>\nstream\n%s\nendstream\nendobj\n" % (len(content), content),
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for o in objs:
        offsets.append(len(pdf))
        pdf += o
    xref_start = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objs) + 1)
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref_start)
    return pdf


def make_blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_extracts_real_text():
    pdf_bytes = make_pdf_with_text("Hello NDA World")
    assert extract_text_from_pdf(pdf_bytes) == "Hello NDA World"


def test_blank_page_raises_no_text_error():
    with pytest.raises(PdfExtractionError, match="No extractable text"):
        extract_text_from_pdf(make_blank_pdf())


def test_garbage_bytes_raise_extraction_error():
    with pytest.raises(PdfExtractionError, match="Could not read PDF"):
        extract_text_from_pdf(b"this is not a pdf at all")


def test_multi_page_text_joined_with_blank_line():
    pdf_bytes = make_pdf_with_text("Clause one")
    text = extract_text_from_pdf(pdf_bytes)
    assert "Clause one" in text
