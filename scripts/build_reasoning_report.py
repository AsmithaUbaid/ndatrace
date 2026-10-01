#!/usr/bin/env python3
"""Build the single self-contained NDATrace final HTML.

The source keeps readable SVG file references. Publication replaces each image
with the SVG markup itself, injects verified word counts, and leaves no display
dependency on the repository or a web server.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/NDATrace_Reasoning_Report_Source.html"
OUTPUT = ROOT / "reports/NDATrace_Final_Report.html"


def words(text: str) -> list[str]:
    return re.findall(r"\b(?:\d{1,3}(?:,\d{3})+|[\w][\w’'\-]*)\b", text)


class Counter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.numbered_depth = 0
        self.narrative: list[str] = []
        self.main: list[str] = []
        self.document: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        data = dict(attrs)
        self.stack.append((tag, data))
        if tag == "section" and data.get("id", "").startswith("s"):
            self.numbered_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "section" and self.numbered_depth:
            self.numbered_depth -= 1
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        tags = [tag for tag, _ in self.stack]
        if "style" in tags or "script" in tags or "svg" in tags or "Word counts:" in data:
            return
        self.document.append(data)
        if self.numbered_depth:
            self.main.append(data)
        if any(tag == "p" and "analysis" in attrs.get("class", "").split() for tag, attrs in self.stack):
            self.narrative.append(data)


def inline_svgs(content: str) -> str:
    pattern = re.compile(r'<img src="(reasoning-assets/[^"]+\.svg)" alt="([^"]*)">')

    def replace(match: re.Match[str]) -> str:
        relative, alt = match.groups()
        path = SOURCE.parent / relative
        svg = path.read_text(encoding="utf-8").strip()
        if not svg.startswith("<svg"):
            raise ValueError(f"Expected SVG root in {path}")
        return svg.replace("<svg ", f'<svg role="img" aria-label="{html.escape(alt, quote=True)}" ', 1)

    published, replacements = pattern.subn(replace, content)
    if replacements != 9:
        raise SystemExit(f"Expected to inline 9 SVG figures, found {replacements}")
    return published


def main() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    if content.count('<section id="s') != 8:
        raise SystemExit("Expected exactly eight numbered report sections")
    if content.count("{{NARRATIVE_WORD_COUNT}}") != 1:
        raise SystemExit("Missing narrative word-count placeholder")

    published = inline_svgs(content)
    counter = Counter()
    counter.feed(published)
    counts = {
        "NARRATIVE_WORD_COUNT": len(words(" ".join(counter.narrative))),
        "MAIN_WORD_COUNT": len(words(" ".join(counter.main))),
        "DOCUMENT_WORD_COUNT": len(words(" ".join(counter.document))),
    }
    for key, value in counts.items():
        published = published.replace("{{" + key + "}}", f"{value:,}")
    if "{{" in published or "reasoning-assets/" in published:
        raise SystemExit("Unresolved publication placeholder or local figure dependency")
    OUTPUT.write_text(published, encoding="utf-8")
    print(f"Wrote self-contained {OUTPUT}")
    print("Word counts:", counts)


if __name__ == "__main__":
    main()
