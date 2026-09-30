#!/usr/bin/env python3
"""E12C Stage A: inspect the TRAIN pool and build TRAIN_GPT_PROMPT_CONFIRM_v1 (document-disjoint from ALL FOUR prior manifests
TRAIN_PROMPT_v1, TRAIN_ARCH_v1, TRAIN_ORACLE_v1 and TRAIN_GPT_PROMPT_v1). Local, deterministic, zero model calls.

Selection is performance-agnostic: same algorithm as TRAIN_PROMPT_v1/TRAIN_ARCH_v1 (per class: group
by document, shuffle documents with random.Random(seed), <=2 cases/doc/class, until 50). It never
reads model outputs, evidence quality, exception language, or difficulty. Only the seed and exclusion set differ.
"""
import json, random, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED = 1300  # unused so far: 42, 99, 123, 300, 500, 700, 1200 (manifests), 900 (bootstrap), 1100 (superseded E12B draft, never used for a model call)
TARGET, MAX_PER_DOC = 50, 2
E12B = REPO / "experiments/E12C_gpt_prompt_confirmation"
OUT = E12B / "TRAIN_GPT_PROMPT_CONFIRM_v1.json"
SRC = {"TRAIN_PROMPT_v1": REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1.json",
       "TRAIN_ARCH_v1": REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json",
       "TRAIN_ORACLE_v1": REPO / "experiments/E01_oracle/TRAIN_ORACLE_v1.json",
       "TRAIN_GPT_PROMPT_v1": REPO / "experiments/E12B_gpt_prompt_optimization/TRAIN_GPT_PROMPT_v1.json"}


def main():
    train = json.load(open(REPO / "data/contractnli/train.json"))
    hyp = {k: v["hypothesis"] for k, v in train["labels"].items()}
    docs = {d["id"]: d for d in train["documents"]}
    mf = {k: json.load(open(p))["cases"] for k, p in SRC.items()}
    dset = {k: {c["document_id"] for c in v} for k, v in mf.items()}
    P, A, O, G = dset["TRAIN_PROMPT_v1"], dset["TRAIN_ARCH_v1"], dset["TRAIN_ORACLE_v1"], dset["TRAIN_GPT_PROMPT_v1"]
    used = P | A | O | G
    untouched = set(docs) - used
    pool_labels = Counter(a["choice"] for i in untouched
                          for a in docs[i]["annotation_sets"][0]["annotations"].values())
    insp = {"total_train_docs": len(docs),
            "total_train_cases": sum(len(d["annotation_sets"][0]["annotations"]) for d in docs.values()),
            "docs_TRAIN_PROMPT_v1": len(P), "docs_TRAIN_ARCH_v1": len(A), "overlap_PROMPT_ARCH_docs": len(P & A),
            "overlap_PROMPT_ORACLE_docs": len(P & O), "overlap_ARCH_ORACLE_docs": len(A & O), "union_of_four_prior_manifests_docs": len(used), "untouched_docs": len(untouched),
            "untouched_label_distribution_cases": dict(pool_labels),
            "docs_TRAIN_ORACLE_v1": len(O), "docs_TRAIN_GPT_PROMPT_v1": len(G), "overlap_GPT_with_any_earlier": len(G & (P | A | O))}

    by_cls = defaultdict(lambda: defaultdict(list))
    for i in sorted(untouched):
        for h, a in docs[i]["annotation_sets"][0]["annotations"].items():
            by_cls[a["choice"]][i].append(h)
    rng, chosen = random.Random(SEED), []
    for cls in ("Entailment", "Contradiction", "NotMentioned"):
        ids = sorted(by_cls[cls]); rng.shuffle(ids); n = 0
        for i in ids:
            for h in sorted(by_cls[cls][i])[:MAX_PER_DOC]:
                if n < TARGET: chosen.append((i, h, cls)); n += 1
    chosen.sort(key=lambda c: (c[2], c[0], c[1]))
    recs = [{"case_id": f"train::{i}::{h}", "split": "train", "document_id": i, "hypothesis_id": h,
             "hypothesis_text": hyp[h], "gold_label": cls} for i, h, cls in chosen]
    new_docs = {r["document_id"] for r in recs}
    assert not (new_docs & used), "document disjointness violated"
    assert not ({r["case_id"] for r in recs} & {c["case_id"] for k in SRC for c in mf[k]})
    man = {"manifest_id": "TRAIN_GPT_PROMPT_CONFIRM_v1", "purpose": "E12C GPT-P0 vs GPT-P3 confirmation; document-disjoint from TRAIN_PROMPT_v1, TRAIN_ARCH_v1, TRAIN_ORACLE_v1 and TRAIN_GPT_PROMPT_v1",
           "source_split": "train", "seed": SEED, "target_per_class": TARGET, "max_cases_per_doc_per_class": MAX_PER_DOC,
           "sampling_algorithm": f"Identical to TRAIN_PROMPT_v1/TRAIN_ARCH_v1 except the candidate pool is restricted to documents used by NONE of the four prior manifests (document-level exclusion, by construction). Per class: sort untouched doc ids, shuffle with random.Random({SEED}), take <=2 cases/doc until 50. Sorted by (class, doc, hyp). Performance-agnostic: no model output, difficulty, or evidence property is read.",
           "total_cases": len(recs), "per_class_case_counts": dict(Counter(r["gold_label"] for r in recs)),
           "total_unique_documents": len(new_docs), "selected_document_ids": sorted(new_docs),
           "verified_document_disjoint_from_TRAIN_PROMPT_v1": True, "verified_document_disjoint_from_TRAIN_ARCH_v1": True, "verified_document_disjoint_from_TRAIN_GPT_PROMPT_v1": True,
           "verified_document_disjoint_from_TRAIN_ORACLE_v1": True, "cases": recs}
    json.dump(man, open(OUT, "w"), indent=2)
    json.dump({"inspection": insp, "manifest_summary": {k: v for k, v in man.items() if k != "cases"}},
              open(E12B / "results/manifest_inspection.json", "w"), indent=2)
    print(json.dumps(insp, indent=1)); print({k: v for k, v in man.items() if k not in ("cases", "selected_document_ids", "sampling_algorithm")})


if __name__ == "__main__":
    main()
