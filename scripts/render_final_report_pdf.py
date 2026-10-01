#!/usr/bin/env python3
"""One-off renderer: reports/NDATrace_Final_Report.md -> a PDF.

Not part of the shipped app. Refuses to replace an existing report unless
``--force`` is supplied explicitly.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/NDATrace_Final_Report.md"
TARGET = SOURCE.with_suffix(".pdf")

styles = getSampleStyleSheet()
title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=20, leading=24, spaceAfter=4)
byline_style = ParagraphStyle("Byline", parent=styles["Normal"], fontSize=9.5, textColor=colors.HexColor("#52525b"), spaceAfter=16)
h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, leading=16, spaceBefore=16, spaceAfter=6,
                          textColor=colors.HexColor("#18181b"), keepWithNext=True)
body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.3, leading=15, spaceAfter=8, alignment=4)  # justify
caption_style = ParagraphStyle("Caption", parent=styles["Normal"], fontSize=8.8, leading=12,
                               textColor=colors.HexColor("#52525b"), spaceAfter=12)


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r'<link href="\2" color="#245a83">\1</link>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", text)
    return text


def build_story(markdown: str) -> list:
    story: list = []
    paragraph: list[str] = []
    table_rows: list[list[str]] = []
    byline_seen = False

    def flush_paragraph():
        if paragraph:
            story.append(Paragraph(inline(" ".join(paragraph)), body_style))
            paragraph.clear()

    def flush_table():
        if not table_rows:
            return
        header, *rows = table_rows
        rows = [r for r in rows if not all(set(c) <= {"-", ":"} for c in r)]
        data = [[Paragraph(f"<b>{inline(c)}</b>", body_style) for c in header]]
        for r in rows:
            data.append([Paragraph(inline(c), body_style) for c in r])
        n_cols = len(header)
        col_width = (LETTER[0] - 1.6 * inch) / n_cols
        t = Table(data, colWidths=[col_width] * n_cols, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f5")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d4d4d8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(KeepTogether([Spacer(1, 4), t, Spacer(1, 8)]))
        table_rows.clear()

    for line in markdown.splitlines():
        if line.startswith("|"):
            flush_paragraph()
            table_rows.append([c.strip() for c in line.strip("|").split("|")])
            continue
        flush_table()
        if not line.strip():
            flush_paragraph()
        elif line.startswith("# "):
            flush_paragraph()
            story.append(Paragraph(inline(line[2:]), title_style))
        elif line.startswith("!["):
            flush_paragraph()
            match = re.match(r"!\[[^]]*\]\(([^)]+)\)", line)
            if match:
                path = SOURCE.parent / match.group(1)
                figure = Image(str(path))
                scale = min((LETTER[0] - 1.6 * inch) / figure.imageWidth,
                            (3.0 * inch) / figure.imageHeight)
                figure.drawWidth *= scale
                figure.drawHeight *= scale
                story.append(figure)
        elif line.startswith("*") and line.endswith("*") and not line.startswith("**"):
            flush_paragraph()
            if not byline_seen:
                story.append(Paragraph(inline(line.strip("*")), byline_style))
                story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#d4d4d8")))
                story.append(Spacer(1, 6))
                byline_seen = True
            else:
                story.append(Paragraph(inline(line.strip("*")), caption_style))
        elif line.startswith("## "):
            flush_paragraph()
            story.append(Paragraph(inline(line[3:]), h2_style))
        else:
            paragraph.append(line.strip())
    flush_paragraph()
    flush_table()
    return story


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument("--force", action="store_true", help="allow replacing an existing output file")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing report: {output}. Use --output or pass --force intentionally.")
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output), pagesize=LETTER,
        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
        title="NDATrace — Evidence-Grounded NDA Requirement Review",
        author="Ubaidulla Asmitha",
    )
    story = build_story(SOURCE.read_text(encoding="utf-8"))
    def page_number(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#71717a"))
        canvas.drawRightString(LETTER[0] - 0.8 * inch, 0.5 * inch, f"NDATrace · {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
