#!/usr/bin/env python3
"""E17: frozen deterministic rule baseline on ALL 2,091 TEST cases. No tuning, no API cost."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e17_common as C
from pipeline.rule_baseline import RULES, classify_with_span

def main():
    F = C.load_frozen(); out = C.E17 / "results/run_E17_rule_full_test.jsonl"; assert not out.exists(), "output exists; refusing to overwrite"
    t0 = time.perf_counter(); rows = []
    for c in F["all"]:
        text = F["ctx"](c); t1 = time.perf_counter(); label, span = classify_with_span(c["hypothesis_id"], text)
        rows.append({"case_id": c["case_id"], "document_id": c["document_id"], "hypothesis_id": c["hypothesis_id"], "gold_label": c["gold_label"], "predicted_label": label, "evidence_span": list(span) if span else None,
                     "has_rule": c["hypothesis_id"] in RULES, "matched": span is not None, "latency_ms": (time.perf_counter() - t1) * 1000, "lower_len_equal": len(text.lower()) == len(text)})
    wall = time.perf_counter() - t0
    with open(out, "x") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    json.dump({"cases": len(rows), "wall_seconds": wall, "api_cost_usd": 0.0, "hypotheses_with_rules": len(RULES)}, open(C.E17 / "results/run_E17_rule_wall.json", "w"), indent=1)
    print(f"rule baseline done: {len(rows)} cases in {wall:.2f}s")

if __name__ == "__main__":
    main()
