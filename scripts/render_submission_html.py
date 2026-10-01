#!/usr/bin/env python3
"""Render the HTML-only final-report source as a polished analytical document."""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/NDATrace_Final_Report_HTML.md"
TARGET = ROOT / "reports/NDATrace_Final_Report.html"


def inline(value: str) -> str:
    value = html.escape(value, quote=False)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\[([^]]+)]\(([^)]+)\)", r'<a href="\2">\1</a>', value)
    return value


def prose_word_count(markdown: str) -> int:
    """Count report prose only: exclude headings, tables, figures/captions, refs and audit appendix."""
    body = markdown.split("<!-- report-body-start -->", 1)[1].split("<!-- report-body-end -->", 1)[0]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        excluded = (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("|")
            or stripped.startswith("![")
            or (stripped.startswith("*") and stripped.endswith("*"))
            or stripped.startswith("<!--")
        )
        if excluded:
            if current:
                paragraphs.append(" ".join(current))
                current.clear()
        else:
            current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    plain = re.sub(r"[`*_\[\]()]", " ", " ".join(paragraphs))
    return len(re.findall(r"\b[\w$%+.-]+\b", plain))


def render(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    table: list[list[str]] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_table() -> None:
        if not table:
            return
        header, *rows = table
        rows = [row for row in rows if not all(set(cell) <= {"-", ":"} for cell in row)]
        table_class = "metrics" if header and header[0] == "Metric" else ""
        output.append(f'<div class="table-wrap"><table class="{table_class}"><thead><tr>')
        output.extend(f"<th>{inline(cell)}</th>" for cell in header)
        output.append("</tr></thead><tbody>")
        for row in rows:
            group = len(row) > 1 and all(not cell for cell in row[1:])
            output.append('<tr class="group-row">' if group else "<tr>")
            output.extend(f"<td>{inline(cell)}</td>" for cell in row)
            output.append("</tr>")
        output.append("</tbody></table></div>")
        table.clear()

    def flush_list() -> None:
        if list_items:
            output.append('<ul class="limitations">')
            output.extend(f"<li>{inline(item)}</li>" for item in list_items)
            output.append("</ul>")
            list_items.clear()

    for line in lines:
        if line.startswith("|"):
            flush_paragraph()
            flush_list()
            table.append([cell.strip() for cell in line.strip("|").split("|")])
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            flush_paragraph()
            flush_table()
            list_items.append(stripped[2:])
            continue
        flush_table()
        flush_list()
        if not stripped:
            flush_paragraph()
        elif stripped == "<!-- pagebreak -->":
            flush_paragraph()
            output.append('<div class="page-break" aria-hidden="true"></div>')
        elif stripped.startswith("<!--") and stripped.endswith("-->"):
            flush_paragraph()
        elif line.startswith("### "):
            flush_paragraph()
            output.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            flush_paragraph()
            output.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            flush_paragraph()
            output.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("!["):
            flush_paragraph()
            match = re.match(r"!\[([^]]*)]\(([^)]+)\)", line)
            if match:
                alt, path = match.groups()
                output.append(f'<figure><img src="{html.escape(path)}" alt="{html.escape(alt)}"></figure>')
        elif line.startswith("*") and line.endswith("*"):
            flush_paragraph()
            value = inline(line.strip("*"))
            if not any(tag.startswith("<h") for tag in output[-1:]):
                output.append(f'<p class="caption">{value}</p>')
            else:
                output.append(f'<p class="byline">{value}</p>')
        else:
            paragraph.append(stripped)
    flush_paragraph()
    flush_table()
    flush_list()
    return "\n".join(output)


CSS = """
:root {
  --navy: #19324d;
  --blue: #3568ac;
  --teal: #138a83;
  --amber: #c57a2d;
  --ink: #18243a;
  --muted: #5c6b82;
  --line: #d9e0e8;
  --paper: #ffffff;
  --canvas: #edf1f5;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--ink);
  background: var(--canvas);
  font-family: Arial, Helvetica, sans-serif;
  font-size: 15px;
  line-height: 1.55;
}
main {
  width: min(960px, calc(100% - 32px));
  margin: 32px auto;
  padding: 64px 76px;
  background: var(--paper);
  box-shadow: 0 12px 40px rgba(25, 50, 77, .12);
}
h1 {
  max-width: 820px;
  margin: 0 0 8px;
  color: var(--navy);
  font-size: clamp(30px, 4vw, 46px);
  line-height: 1.08;
  letter-spacing: -.025em;
}
h2 {
  margin: 34px 0 10px;
  padding-top: 6px;
  color: var(--navy);
  font-size: 22px;
  line-height: 1.25;
  break-after: avoid;
}
h3 {
  margin: 22px 0 8px;
  color: var(--navy);
  font-size: 16px;
  line-height: 1.3;
  break-after: avoid;
}
p { margin: 0 0 14px; }
.byline {
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  font-size: 14px;
}
.word-count {
  margin: -14px 0 28px;
  color: var(--muted);
  font-size: 12px;
}
.caption {
  margin: -4px 0 22px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.45;
}
figure {
  margin: 22px 0 10px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fbfcfd;
  break-inside: avoid;
}
figure img { display: block; width: 100%; height: auto; }
.table-wrap {
  margin: 18px 0 24px;
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 7px;
  break-inside: avoid;
}
table { width: 100%; border-collapse: collapse; font-size: 13px; line-height: 1.35; }
th, td { padding: 9px 10px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); vertical-align: top; }
th:last-child, td:last-child { border-right: 0; }
tbody tr:last-child td { border-bottom: 0; }
th { color: var(--navy); background: #eef3f8; text-align: left; font-size: 12px; letter-spacing: .02em; }
tbody tr:nth-child(even) { background: #fafbfd; }
.group-row td { background: #e7eef6; color: var(--navy); font-weight: 700; }
.metrics th:not(:first-child), .metrics td:not(:first-child) { text-align: right; font-variant-numeric: tabular-nums; }
strong { color: var(--navy); }
.limitations { margin: 8px 0 0; padding-left: 22px; }
.limitations li { margin: 0 0 7px; }
code { padding: .12em .3em; border-radius: 3px; background: #eef3f8; font-size: .88em; overflow-wrap: anywhere; }
a { color: var(--blue); }
.page-break { height: 1px; margin: 0; }
@media (max-width: 700px) {
  main { width: 100%; margin: 0; padding: 34px 22px; box-shadow: none; }
  body { background: var(--paper); }
  table { min-width: 620px; }
}
@media print {
  @page { size: A4; margin: 16mm 17mm; }
  body { background: #fff; font-size: 10pt; line-height: 1.42; }
  main { width: auto; margin: 0; padding: 0; box-shadow: none; }
  h1 { font-size: 24pt; }
  h2 { font-size: 14pt; margin-top: 20pt; }
  h3 { font-size: 11pt; margin-top: 14pt; }
  .page-break { break-before: page; }
  figure, .table-wrap { break-inside: avoid; }
  .limitations { font-size: 8.5pt; line-height: 1.28; }
  .limitations li { margin-bottom: 2px; }
  a { color: inherit; text-decoration: none; }
}
"""


def main() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    count = prose_word_count(markdown)
    body = render(markdown)
    body = body.replace(
        '</p>\n<h2>1. Problem and business significance</h2>',
        f'</p>\n<p class="word-count">Word count: {count:,} words (main prose only; headings, tables, captions, references and audit notes excluded).</p>\n<h2>1. Problem and business significance</h2>',
        1,
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="author" content="Ubaidulla Asmitha">
  <title>NDATrace - Does Additional AI Complexity Earn Its Place?</title>
  <style>{CSS}</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""
    TARGET.write_text(document, encoding="utf-8")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
