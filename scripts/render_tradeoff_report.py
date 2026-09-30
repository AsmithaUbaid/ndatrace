#!/usr/bin/env python3
"""Render the final Markdown report to a self-contained submission HTML file."""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/NDATrace_Final_Tradeoff_Report.md"
TARGET = SOURCE.with_suffix(".html")


def inline(text: str) -> str:
    value = html.escape(text)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    return value


def render(markdown: str) -> str:
    lines = markdown.splitlines()
    body: list[str] = []
    paragraph: list[str] = []
    table: list[list[str]] = []

    def flush_paragraph() -> None:
        if paragraph:
            body.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_table() -> None:
        if not table:
            return
        header, *rows = table
        body.append("<div class=table-wrap><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
        for row in rows[1:]:
            body.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
        body.append("</tbody></table></div>")
        table.clear()

    for line in lines:
        if line.startswith("|"):
            flush_paragraph()
            table.append([cell.strip() for cell in line.strip("|").split("|")])
            continue
        flush_table()
        if not line.strip():
            flush_paragraph()
        elif line.startswith("# "):
            flush_paragraph(); body.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            flush_paragraph(); body.append(f"<h2>{inline(line[3:])}</h2>")
        else:
            paragraph.append(line.strip())
    flush_paragraph(); flush_table()
    return "\n".join(body)


css = """body{margin:0;background:#faf9f7;color:#27272a;font:16px/1.65 Inter,system-ui,sans-serif}main{max-width:900px;margin:40px auto;padding:48px;background:white;border:1px solid #e4e4e7;border-radius:24px;box-shadow:0 18px 50px -40px #18181b}h1{font-size:2.35rem;line-height:1.15;margin:0 0 2rem}h2{font-size:1.35rem;margin:2.2rem 0 .8rem;color:#18181b}p{margin:.7rem 0}code{background:#f4f4f5;padding:.15rem .35rem;border-radius:5px}.table-wrap{overflow:auto;margin:1rem 0}table{width:100%;border-collapse:collapse;min-width:650px}th,td{padding:.7rem;border-bottom:1px solid #e4e4e7;text-align:left}th{background:#f4f4f5;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}@media(max-width:700px){main{margin:0;padding:28px 20px;border:0;border-radius:0}h1{font-size:1.9rem}}"""
TARGET.write_text(f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>NDATrace — Final Trade-off Report</title><style>{css}</style></head><body><main>{render(SOURCE.read_text())}</main></body></html>\n")
print(f"Wrote {TARGET}")
