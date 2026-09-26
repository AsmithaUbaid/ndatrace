#!/usr/bin/env python3
"""E13 Stage A: audit DEV and build DEV_ARCH_v1 (150 cases, 50/50/50). Local, deterministic, zero model calls.

DEV audit finding: document-level disjointness from historical DEV exposure is INFEASIBLE (58/61 DEV docs were touched by the historical 150-case
seed-42 sample; union with the golden-battery docs = 60/61). Selection is therefore CASE-level disjoint from every case in (a) the historical 150-case
seed-42 stratified sample and (b) every data/golden/*.json case. It is performance-agnostic: no model output, difficulty, or evidence property is read.
Reconstruction-v2 (E00-E12C) never touched DEV.
"""
import glob, json, random, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.run_oracle_experiment import stratified_sample  # noqa: E402
from pipeline.parser import parse_contractnli_file  # noqa: E402

SEED = 1400  # fresh: prior seeds 42, 99, 123, 300, 500, 700, 900, 1100, 1200, 1300
TARGET, CAP = 50, 2
OUT = REPO / "experiments/E13_gpt_context_architecture"


def main():
    dev = json.load(open(REPO / "data/contractnli/dev.json")); docs = {d["id"]: d for d in dev["documents"]}
    hyp = {k: v["hypothesis"] for k, v in dev["labels"].items()}
    ann = {(d["id"], h): a["choice"] for d in dev["documents"] for h, a in d["annotation_sets"][0]["annotations"].items()}
    ds = parse_contractnli_file(REPO / "data/contractnli/dev.json")
    s150 = {(int(d.id if hasattr(d, "id") else d.doc_id), a.hypothesis_id) for d, a in stratified_sample(ds, 150, 42)}
    golden, gsrc = set(), {}
    for f in sorted(glob.glob(str(REPO / "data/golden/*.json"))):
        for c in json.load(open(f)):
            if str(c.get("doc_id", "")).isdigit() and "hypothesis_id" in c:  # synthetic-doc cases are not DEV documents
                golden.add((int(c["doc_id"]), c["hypothesis_id"])); gsrc[Path(f).name] = gsrc.get(Path(f).name, 0) + 1
    used = s150 | golden
    lab = lambda keys: dict(Counter(ann[k] for k in keys))
    s150_docs, g_docs = {k[0] for k in s150}, {k[0] for k in golden}
    audit = {"dev_docs": len(docs), "dev_cases": len(ann), "dev_label_counts": lab(ann),
             "reconstruction_v2_E00_E12C_dev_usage": "none (E04 rule baseline, E06 retrieval, E07-E12C all ran on TRAIN; E07/E04 text mentioning DEV describes historical T-series prior art)",
             "historical_150_case_seed42_sample": {"cases": len(s150), "docs": len(s150_docs), "labels": lab(s150)},
             "historical_golden_battery_cases": {"unique_cases": len(golden), "docs": len(g_docs), "by_file": gsrc, "labels": lab(golden)},
             "historical_full_dev_use": "full 1,037-case rule baseline (B02) and 614 E/C-case retrieval experiments (T020-T023) touched every DEV document; deterministic/free but shaped the OLD retrieval config",
             "docs_touched_by_sample_or_golden": len(s150_docs | g_docs), "docs_untouched_by_sample_or_golden": len(set(docs) - s150_docs - g_docs),
             "doc_level_disjoint_pool_labels": lab([k for k in ann if k[0] not in s150_docs | g_docs]),
             "case_level_disjoint_pool_labels": lab([k for k in ann if k not in used]),
             "doc_level_disjointness_feasible": False, "case_level_disjoint_balanced_150_feasible": all(lab([k for k in ann if k not in used]).get(c, 0) >= TARGET for c in ("Entailment", "Contradiction", "NotMentioned"))}
    pool = defaultdict(lambda: defaultdict(list))
    for (d, h), c in ann.items():
        if (d, h) not in used: pool[c][d].append(h)
    rng, chosen = random.Random(SEED), []
    for cls in ("Entailment", "Contradiction", "NotMentioned"):
        ids = sorted(pool[cls]); rng.shuffle(ids); n = 0
        for d in ids:
            for h in sorted(pool[cls][d])[:CAP]:
                if n < TARGET: chosen.append((d, h, cls)); n += 1
        assert n == TARGET, f"cap {CAP}/doc/class cannot reach {TARGET} for {cls} (got {n})"
    chosen.sort(key=lambda c: (c[2], c[0], c[1]))
    recs = [{"case_id": f"dev::{d}::{h}", "split": "dev", "document_id": d, "hypothesis_id": h, "hypothesis_text": hyp[h], "gold_label": cls} for d, h, cls in chosen]
    sel = {(r["document_id"], r["hypothesis_id"]) for r in recs}; assert not (sel & used) and len(sel) == 150
    seld = {r["document_id"] for r in recs}
    rem_keys = [k for k in ann if k not in used and k not in sel]
    man = {"manifest_id": "DEV_ARCH_v1", "purpose": "E13 GPT full-context vs RAG architecture validation (DEV = Role B)", "source_split": "dev", "seed": SEED,
           "target_per_class": TARGET, "max_cases_per_doc_per_class": CAP,
           "sampling_algorithm": f"Pool = DEV cases not in the historical 150-case seed-42 sample and not in any data/golden case (case-level exclusion; document-level exclusion infeasible). Per class: sort doc ids, shuffle with random.Random({SEED}), take <= {CAP} cases/doc until {TARGET}. Sorted by (class, doc, hyp). Performance-agnostic; no hard-case enrichment.",
           "total_cases": 150, "per_class_case_counts": dict(Counter(r["gold_label"] for r in recs)), "total_unique_documents": len(seld), "selected_document_ids": sorted(seld),
           "documents_also_touched_by_historical_sample_or_golden": len(seld & (s150_docs | g_docs)),
           "verified_case_disjoint_from_historical_150_sample": True, "verified_case_disjoint_from_golden_battery": True,
           "remaining_never_used_dev_cases_after_selection": {"total": len(rem_keys), "labels": lab(rem_keys)},
           "dev_docs_touched_by_DEV_ARCH_v1": len(seld), "cases": recs}
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "results").mkdir(exist_ok=True)
    json.dump(man, open(OUT / "DEV_ARCH_v1.json", "w"), indent=2); json.dump({"audit": audit, "manifest_summary": {k: v for k, v in man.items() if k != "cases"}}, open(OUT / "results/dev_audit.json", "w"), indent=2)
    print(json.dumps(audit, indent=1)); print({k: v for k, v in man.items() if k not in ("cases", "selected_document_ids", "sampling_algorithm")})


if __name__ == "__main__":
    main()
