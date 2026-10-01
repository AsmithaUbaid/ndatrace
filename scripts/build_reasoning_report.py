#!/usr/bin/env python3
"""Publish the fresh, directly editable HTML source as the final report."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/NDATrace_Reasoning_Report_Source.html"
OUTPUT = ROOT / "reports/NDATrace_Final_Report.html"

content = SOURCE.read_text(encoding="utf-8")
if content.count('<section id="s') != 8:
    raise SystemExit("Expected exactly eight numbered report sections")
OUTPUT.write_text(content, encoding="utf-8")
print(f"Wrote {OUTPUT} from fresh authoritative source")
