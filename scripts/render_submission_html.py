#!/usr/bin/env python3
"""Render the editable final-report Markdown source as a polished HTML document."""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/NDATrace_Final_Report.md"
TARGET = ROOT / "reports/NDATrace_Final_Report.html"


def inline(value: str) -> str:
    value = html.escape(value, quote=False)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\[([^]]+)]\(([^)]+)\)", r'<a href="\2">\1</a>', value)
    return value


def render(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    table: list[list[str]] = []

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_table() -> None:
        if not table:
            return
        header, *rows = table
        rows = [row for row in rows if not all(set(cell) <= {"-", ":"} for cell in row)]
        output.append("<div class=\"table-wrap\"><table><thead><tr>")
        output.extend(f"<th>{inline(cell)}</th>" for cell in header)
        output.append("</tr></thead><tbody>")
        for row in rows:
            output.append("<tr>")
            output.extend(f"<td>{inline(cell)}</td>" for cell in row)
            output.append("</tr>")
        output.append("</tbody></table></div>")
        table.clear()

    for line in lines:
        if line.startswith("|"):
            flush_paragraph()
            table.append([cell.strip() for cell in line.strip("|").split("|")])
            continue
        flush_table()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
        elif stripped == "<!-- pagebreak -->":
            flush_paragraph()
            output.append('<div class="page-break" aria-hidden="true"></div>')
        elif line.startswith("# "):
            flush_paragraph()
            output.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            flush_paragraph()
            output.append(f"<h2>{inline(line[3:])}</h2>")
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
p { margin: 0 0 14px; }
.byline {
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  font-size: 14px;
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
  .page-break { break-before: page; }
  figure, .table-wrap { break-inside: avoid; }
  a { color: inherit; text-decoration: none; }
}
"""


def main() -> None:
    body = render(SOURCE.read_text(encoding="utf-8"))
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
