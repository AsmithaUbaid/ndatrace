#!/usr/bin/env python3
"""E18: offline figure generation from experiments/E18_business_course_synthesis/results/e18_analysis.json + existing artifacts. No model calls."""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
E18 = REPO / "experiments/E18_business_course_synthesis"; FIG = E18 / "figures"; FIG.mkdir(exist_ok=True, parents=True)
A = json.load(open(E18 / "results/e18_analysis.json"))
plt.rcParams.update({"figure.dpi": 130, "font.size": 9})

def save(fig, name): fig.tight_layout(); fig.savefig(FIG / name, bbox_inches="tight"); plt.close(fig)

# 1. Architecture ladder (matched-manifest results only; datasets/manifests distinguished in labels)
def fig_ladder():
    rows = [("Rule\n(full TEST, n=2091)", 0.5007, 0.1682), ("Full-context Qwen\n(Oracle-gold, TRAIN n=300)", None, 0.30), ("RAG GPT\n(DEV n=150)", 0.7533, None), ("Full-context GPT\n(DEV n=150)", 0.7733, None),
            ("Selective Agent A3\n(TRAIN n=150, rejected)", None, None), ("Full-context GPT\n(TEST n=2091, FINAL)", 0.7460, 0.7545)]
    joint = [r[1] for r in rows]; contra = [r[2] for r in rows]; labels = [r[0] for r in rows]
    fig, ax1 = plt.subplots(figsize=(9, 4.2)); x = range(len(rows)); w = 0.35
    b1 = ax1.bar([i - w / 2 for i in x], [j if j is not None else 0 for j in joint], width=w, label="Joint success", color="#2b6cb0")
    b2 = ax1.bar([i + w / 2 for i in x], [c if c is not None else 0 for c in contra], width=w, label="Contradiction recall", color="#d69e2e")
    for i, (j, c) in enumerate(zip(joint, contra)):
        if j is None: ax1.text(i - w / 2, 0.02, "n/a\n(diff.\nmanifest)", ha="center", fontsize=6, color="gray")
        if c is None: ax1.text(i + w / 2, 0.02, "n/a", ha="center", fontsize=6, color="gray")
    ax1.set_xticks(list(x)); ax1.set_xticklabels(labels, fontsize=7); ax1.set_ylim(0, 1.0); ax1.set_ylabel("Rate")
    ax1.legend(fontsize=8); ax1.set_title("Architecture ladder — every layer had to earn its complexity; several did not\n(bars from different manifests/samples are NOT directly comparable — see labels; final bar is the merged E17+E17B full-TEST result)")
    save(fig, "01_architecture_ladder.png")

# 0/2. Final full-TEST comparison (Rule vs Qwen vs GPT, identical n=2091) -- headline figure
def fig_final_test_comparison():
    e17 = json.load(open(REPO / "experiments/E17_final_test/results/final_metrics.json")); e17b = json.load(open(REPO / "experiments/E17B_full_test_completion/results/final_full_test_metrics.json"))
    systems = ["Rule", "Qwen ctx16k", "GPT-5-mini FULL"]
    metrics = {"Accuracy": [e17["rule_full_2091"]["accuracy"], e17["qwen_full_2091"]["accuracy"], e17b["full_gpt_2091"]["accuracy"]],
               "Macro-F1": [e17["rule_full_2091"]["macro_f1"], e17["qwen_full_2091"]["macro_f1"], e17b["full_gpt_2091"]["macro_f1"]],
               "Joint": [e17["rule_full_2091"]["joint"], e17["qwen_full_2091"]["joint"], e17b["full_gpt_2091"]["joint"]],
               "Contradiction\nrecall": [e17["rule_full_2091"]["recall"]["Contradiction"], e17["qwen_full_2091"]["recall"]["Contradiction"], e17b["full_gpt_2091"]["recall"]["Contradiction"]]}
    fig, ax = plt.subplots(figsize=(7.5, 4.3)); x = list(range(len(metrics))); w = 0.25
    for i, sysname in enumerate(systems):
        ax.bar([xi + (i - 1) * w for xi in x], [metrics[m][i] for m in metrics], width=w, label=sysname)
    ax.set_xticks(x); ax.set_xticklabels(list(metrics)); ax.set_ylim(0, 1); ax.set_ylabel("Rate"); ax.legend(fontsize=8)
    ax.set_title("Final TEST comparison — same 2,091 cases (Rule / local Qwen / hosted GPT-5-mini FULL)\nGPT materially outperforms both baselines; API cost: Rule $0, Qwen $0 (compute not monetized), GPT $4.23 total")
    save(fig, "00_final_test_comparison.png")

# 2. Oracle ceiling vs real systems
def fig_oracle():
    o = A["oracle_ceiling"]; names = ["Qwen\nOracle\n(gold evid.)", "Qwen\nFull-TEST\n(real, n=2091)", "GPT\nOracle\n(gold evid.)", "GPT\nFull-TEST\n(real, n=2091, FINAL)"]
    f1 = [o["oracle_gold_evidence_local_qwen"]["macro_f1"], 0.431, o["oracle_gold_evidence_gpt5mini"]["macro_f1"], o["real_context_full_gpt_TEST_FULL_n2091"]["macro_f1"]]
    fig, ax = plt.subplots(figsize=(6.5, 4)); ax.bar(names, f1, color=["#a0aec0", "#4a5568", "#f6ad55", "#dd6b20"]); ax.set_ylabel("Macro-F1"); ax.set_ylim(0, 1)
    ax.set_title("Oracle (gold-evidence) ceiling vs. real-context result (full TEST, n=2091)\nGPT closes most of the gap vs. Qwen but a meaningful gap to its own Oracle ceiling remains")
    for i, v in enumerate(f1): ax.text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=8)
    save(fig, "02_oracle_ceiling.png")

# 3. Quadratic agent token growth
def fig_token_growth():
    rows = A["quadratic_token_growth"]; T = [r["T"] for r in rows]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(T, [r["B*T"] for r in rows], "o-", label="B·T (repeated context)")
    ax.plot(T, [r["D*T(T-1)/2"] for r in rows], "s-", label="D·T(T-1)/2 (accumulated)")
    ax.plot(T, [r["total"] for r in rows], "^-", color="black", label="Total input tokens")
    ax.axvline(3, color="red", ls="--", lw=1, label="Configured cap (max_agent_steps=3)")
    ax.scatter([1], [1476 + 510], marker="*", s=160, color="green", zorder=5, label="Actual E11 behaviour\n(every case: FINAL at T=1)")
    ax.set_xlabel("Agent turn T"); ax.set_ylabel("Cumulative input tokens"); ax.legend(fontsize=7)
    ax.set_title("Agent token growth: Input(T) ≈ B·T + D·T(T-1)/2\nD is a config-derived approximation (no measured multi-step trace)")
    save(fig, "03_agent_token_growth.png")

# 4. Reliability vs turns
def fig_reliability():
    rc = A["reliability_compounding"]["candidates"]; fig, ax = plt.subplots(figsize=(6, 4))
    for name, rows in rc.items(): ax.plot([r["T"] for r in rows], [r["P_success"] for r in rows], "o-", label=name.replace("_", " "))
    ax.axvline(3, color="red", ls="--", lw=1); ax.set_xlabel("Dependent steps T"); ax.set_ylabel("P(run success) ≈ sᵀ (illustrative)")
    ax.set_ylim(0, 1.05); ax.legend(fontsize=6.5)
    ax.set_title("Illustrative compounding sensitivity — NOT measured agent reliability\ns = single-call joint-success rates used as scenario anchors, not per-step agent correctness\n(real E11 agent traces all stopped at step 1 — no multi-step data exists)")
    save(fig, "04_reliability_vs_turns.png")

# 5. FULL vs RAG token saving by document length
def fig_full_vs_rag():
    d = A["full_vs_rag_tokens"]["by_length_tercile"]; names = list(d); saving = [d[n]["token_saving"] for n in names]; pct = [d[n]["pct_saving"] * 100 for n in names]
    fig, ax1 = plt.subplots(figsize=(6, 4)); ax1.bar(names, saving, color="#38a169"); ax1.set_ylabel("Mean tokens saved (FULL - RAG)")
    ax2 = ax1.twinx(); ax2.plot(names, pct, "o-", color="#c53030"); ax2.set_ylabel("% saving", color="#c53030")
    ax1.set_title("RAG token savings grow with document length (DEV n=150)\n...but did not improve measured quality (FULL beat RAG on this DEV comparison)")
    save(fig, "05_full_vs_rag_tokens.png")

# 6. Quality vs raw cost
def fig_quality_vs_cost():
    e17 = json.load(open(REPO / "experiments/E17_final_test/results/final_metrics.json")); e17b = json.load(open(REPO / "experiments/E17B_full_test_completion/results/final_full_test_metrics.json"))
    pts = [("Rule\n(TEST 2091)", 0.0, e17["rule_full_2091"]["joint"]), ("Qwen local\n(TEST 2091)", 0.0, e17["qwen_full_2091"]["joint"]), ("GPT hosted\n(TEST 2091, FULL)", e17b["full_gpt_2091"]["ops"]["cost_per_case"], e17b["full_gpt_2091"]["joint"])]
    fig, ax = plt.subplots(figsize=(6, 4))
    for name, c, j in pts: ax.scatter([c], [j], s=140); ax.annotate(name + ("\n(API=$0; local compute not monetized)" if "Qwen" in name else ("\n(no inference)" if "Rule" in name else "")), (c, j), textcoords="offset points", xytext=(8, 4), fontsize=7)
    ax.set_xlabel("Measured API cost / case (USD)"); ax.set_ylabel("Joint success"); ax.set_xlim(-0.0003, 0.0026); ax.set_ylim(0, 1)
    ax.set_title("Quality vs. measured AI cost per case\nLocal $0 API cost is not $0 real economic cost (compute/time)")
    save(fig, "06_quality_vs_cost.png")

# 7. Cost-to-serve sensitivity
def fig_cost_sensitivity():
    s = A["cost_to_serve"]["sensitivity_per_1000_vs_p_safe"]; ps = s["p_axis"]; fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for name, ys in s["curves"].items(): ax.plot(ps, ys, label=name, lw=2 if "manual" in name else 1.5, ls="--" if "manual" in name else "-")
    for name, (p_val, jkey) in {"GPT (measured p, full TEST)": (A["cost_to_serve"]["p_safe_measured(=joint_success)"]["gpt_TEST_FULL_2091(primary)"], None), "Qwen (measured p)": (A["cost_to_serve"]["p_safe_measured(=joint_success)"]["qwen_TEST_full"], None)}.items():
        ax.axvline(p_val, ls=":", lw=1, color="gray")
    ax.set_xlabel("Safe success rate p"); ax.set_ylabel(f"Cost per 1,000 cases (USD), human review = {s['C_H']:.2f}/case ({s['C_H_scenario']})")
    ax.legend(fontsize=7); ax.set_title("Cost-to-serve sensitivity — human fallback can dominate sub-cent LLM cost\n(human-review cost is an ILLUSTRATIVE SCENARIO, not a measured company rate)")
    save(fig, "07_cost_sensitivity.png")

# 8. Break-even
def fig_breakeven():
    be = A["cost_to_serve"]["break_even"]; fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["Qwen p (actual)", "Qwen p needed\nto match GPT all-in cost", "GPT p needed\nto beat manual-only"]
    vals = [be["Qwen_vs_GPT"]["qwen_actual_p"], be["Qwen_vs_GPT"]["p_BE_qwen_needs"], be["AI_plus_human_vs_manual_only"]["p_BE_for_gpt_to_beat_manual"]]
    colors = ["#c53030" if vals[0] < vals[1] else "#38a169", "#2b6cb0", "#38a169"]
    ax.bar(labels, vals, color=colors); ax.set_ylabel("Joint success rate p"); ax.set_ylim(0, 1)
    for i, v in enumerate(vals): ax.text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=8)
    ax.set_title("Break-even success rates (illustrative human-review cost scenario)\nQwen's real p (0.397) falls far short of the p it would need to match GPT's all-in cost")
    save(fig, "08_breakeven.png")

# 9. Safe automation composition (100% stacked bar, E15 fresh validation)
def fig_safe_automation():
    pol = A["routing_safety"]["policies"]; names = list(pol); safe = [pol[p]["safe_automation_rate"] for p in names]; unsafe = [pol[p]["unsafe_automation_rate"] for p in names]; rev = [pol[p]["human_review_rate"] for p in names]
    fig, ax = plt.subplots(figsize=(6, 4)); ax.bar(names, safe, label="Safe automated", color="#38a169")
    ax.bar(names, rev, bottom=safe, label="Human review", color="#4299e1")
    ax.bar(names, unsafe, bottom=[s + r for s, r in zip(safe, rev)], label="Unsafe automated (silent failure)", color="#c53030")
    ax.set_ylabel("Share of cases"); ax.legend(fontsize=8, loc="upper right"); ax.set_title("Safe automation composition — E15 fresh DEV_ROUTING_v1 (n=138)\nR0 maximizes automation but leaves 29.0% silent failure; R3 needs 51.3% review")
    save(fig, "09_safe_automation_composition.png")

# 10. Review rate vs residual error
def fig_review_vs_residual():
    pol = A["routing_safety"]["policies"]; fig, ax = plt.subplots(figsize=(6, 4))
    xs = [pol[p]["review_rate"] for p in pol]; ys = [pol[p]["residual_joint_error"] for p in pol]
    ax.plot(xs, ys, "o-", color="#2b6cb0")
    for p, x, y in zip(pol, xs, ys): ax.annotate(p, (x, y), textcoords="offset points", xytext=(6, 4))
    ax.axvspan(0, 0.40, color="green", alpha=0.06); ax.axhspan(0, 0.10, color="green", alpha=0.06)
    ax.axvline(0.40, color="green", ls="--", lw=1); ax.axhline(0.10, color="green", ls="--", lw=1)
    ax.set_xlabel("Review rate"); ax.set_ylabel("Residual joint error (among auto-handled)")
    ax.set_title("Review rate vs. residual error — no policy enters the provisional target region\n(review<=40% AND residual<10%; region is inherited/provisional, not a measured SLA)")
    save(fig, "10_review_vs_residual.png")

# 11. Review rate vs failure capture
def fig_review_vs_capture():
    pol = A["routing_safety"]["policies"]; fig, ax = plt.subplots(figsize=(6, 4))
    xs = [pol[p]["review_rate"] for p in pol]; ys = [pol[p]["failure_capture"] for p in pol]
    ax.plot(xs, ys, "o-", color="#d69e2e"); ax.plot([0, 1], [0, 1], "k:", lw=1, label="random-review reference")
    for p, x, y in zip(pol, xs, ys): ax.annotate(p, (x, y), textcoords="offset points", xytext=(6, 4))
    ax.set_xlabel("Review rate"); ax.set_ylabel("Joint-failure capture rate"); ax.legend(fontsize=7)
    ax.set_title("Did review catch the cases that would otherwise be wrong?\nR2 tracks the random-review line closely; R3 clears it")
    save(fig, "11_review_vs_capture.png")

# 12. Robustness / security
def fig_robustness():
    r = A["robustness_summary"]; fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["Clean joint", "Attack joint"], [r["clean_joint"], r["attack_joint"]], color=["#38a169", "#c53030"])
    ax.set_ylim(0, 1); ax.set_ylabel("Joint success (n=20 pairs)")
    txt = f"Injection attack success: {r['injection_attack_successes']}/{r['n_injection_pairs']}\nAttack-induced regressions: {r['attack_induced_joint_regressions']}\nSource-valid rate clean/attack: {r['clean_source_valid_rate']:.0%}/{r['attack_source_valid_rate']:.0%}"
    ax.text(0.5, 0.5, txt, transform=ax.transAxes, ha="center", va="center", fontsize=8, bbox=dict(fc="white", ec="gray"))
    ax.set_title(f"E16 robustness (Outcome {r['decision']}) — small n=20 pairs, do not overstate\nSource-valid evidence != trusted instruction source")
    save(fig, "12_robustness.png")

# 13. Final failure taxonomy (full population, primary)
NAMES = {"notmentioned_over_inference": "NotMentioned over-inference", "reasoning_failure_or_missed_provision": "Contradiction: reasoning failure /\nmissed provision", "reasoning_failure": "Entailment: other reasoning failure",
         "missed_provision": "Missed provision (no evidence)", "correct_label_evidence_mismatch": "Correct label, evidence mismatch", "source_validation_issue": "Source-validation issue"}
def fig_failure_taxonomy():
    ft = A["failure_taxonomy"]["buckets_full_2091(primary)"]; total = A["failure_taxonomy"]["total_full_2091"]; fig, ax = plt.subplots(figsize=(7.5, 4))
    items = sorted(ft.items(), key=lambda x: -x[1]); names = [NAMES.get(k, k) for k, _ in items]; vals = [v for _, v in items]
    ax.barh(names, vals, color="#4a5568")
    for i, v in enumerate(vals): ax.text(v + 3, i, str(v), va="center", fontsize=8)
    ax.set_xlabel(f"Count (of {total} full-TEST joint failures, n=2,091)")
    ax.set_title(f"Final failure taxonomy — FULL TEST (n=2091, {total} joint failures)\nNotMentioned over-inference dominates; residual Contradiction failures are mostly interpretation, not missing context")
    save(fig, "13_failure_taxonomy.png")

for fn in (fig_final_test_comparison, fig_ladder, fig_oracle, fig_token_growth, fig_reliability, fig_full_vs_rag, fig_quality_vs_cost, fig_cost_sensitivity, fig_breakeven, fig_safe_automation, fig_review_vs_residual, fig_review_vs_capture, fig_robustness, fig_failure_taxonomy):
    fn(); print("wrote", fn.__name__)
