# Legacy Delete Manifest (completed 2026-09-29)

Generated from a repo-wide dependency sweep. **This plan has been executed**: every row marked
`DELETE` below was removed in commit `b8d2c90` ("Cleaning the repo", 2026-09-29), and every row
marked `KEEP`/`HOLD` is still present in the working tree (verified). Kept as a historical record of
what was removed and why — not a live to-do list. The three judgment calls at the bottom are also
resolved (see the note after each): the Case Explorer was rebuilt to use only reconstruction-v2 data
(no legacy substitution), `docs/decisions.md`/`docs/experiments.md` were kept with explicit
historical-only framing rather than deleted, and "benchmark" terminology was renamed out of the
primary user-facing docs.

| Path | Why legacy | Current dependency? | Migration required? | Final action |
|---|---|---|---|---|
| `archive/pre_reconstruction/` (76 files, 2.0M) | Pre-reconstruction scripts/tests/notebooks/results | No code imports it — every hit in current files is a comment or doc citation | No | **DELETE** |
| `archive/legacy_experiments/` (7 files, 1.2M — AV01, PVAL01) | Pre-reconstruction architecture/prompt validation manifests | No code reads it — doc prose citations only | No | **DELETE** |
| `results/final/legacy/` (8 files, 12M — run_AV01\*, run_T041\* ×4, carveout_examples.md) | Pre-reconstruction Gemini-era final-test runs | **YES** — `scripts/build_project_presentation_data.py` (lines 91-94, 260) and `scripts/build_e00b_forecast.py` (lines 234-236, 266-268) hard-open these files | **YES** — see judgment call #1 below | Migrate first, then delete |
| `results/archive/runs/` (15 files, 6.5M — B01-B04, T018×5, T024, T041-llama×3) | Pre-reconstruction dev-sample experiment runs | **YES** — `scripts/build_e00b_forecast.py` (lines 185, 231-233, 263-265) hard-opens 6 of these | **YES** — see judgment call #1 below | Migrate first, then delete |
| `results/runs/` (AV01/T041/B01-04/T018/T024 filenames) | — | Already empty — this duplicate copy was deleted previously (see `docs/data_contamination_register.md`) | No | Nothing to do |
| `prompts/classify_v1.txt` – `v5.txt` | Superseded prompt lineage | No — only `docs/experiments.md` / archive scripts reference them | No | **DELETE** |
| `prompts/classify_v6.txt` + `pipeline/classifier.py` | Old classifier prompt/module | **Borderline** — `scripts/run_oracle_experiment.py` and `tests/test_classifier.py` touch `classifier.py`, and `scripts/build_e00b_forecast.py` cites `classify_v6.txt`; neither test/script carries an explicit legacy marker (unlike agent.py/agent_tools.py/confidence.py's WBS-numbered docstrings) | Needs a manual read of those two files before deciding | **HOLD — verify before deleting** |
| `prompts/agent_step_v1.txt`, `agent_step_v1_3tools.txt` | Superseded agent prompt lineage | No — archive scripts and completed-experiment summaries only | No | **DELETE** |
| `prompts/agent_step_v2.txt` | Tied to legacy `pipeline/agent.py` | No current-runtime importer (only `pipeline/agent.py` itself) | No | **DELETE** (alongside `pipeline/agent.py`) |
| `prompts/oracle_v1.txt` | — | **YES** — `tests/test_oracle.py`, `scripts/run_e01_oracle.py` (live, non-archived) | No | **KEEP** |
| `prompts/reconstruction_v2/**`, `prompts/agent_v2_control.txt` | Current | Live E10/E11/E12 experiments and reconstruction runtime | No | **KEEP** |
| `pipeline/agent.py` | Legacy 5-tool agent (WBS T029) | Only legacy test (`tests/test_agent.py`) and a negative test asserting it must NOT run (`tests/test_legacy_review.py`); `run_e21_owasp.py` itself documents it as unreachable dead code by design | Delete `tests/test_agent.py`'s positive-behavior assertions; keep/adjust the negative assertion in `test_legacy_review.py` if it still adds value against regressions, else drop it too | **DELETE module + legacy test** |
| `pipeline/agent_tools.py` | Legacy tool set (WBS T028) | Only `pipeline/agent.py` and its legacy test | No other current importer | **DELETE module + legacy test** |
| `pipeline/confidence.py` | Legacy confidence router (WBS T027) | Only archive scripts + legacy test (`tests/test_confidence.py`); confirmed NOT imported by backend | No | **DELETE module + legacy test** |
| `pipeline/agent_v2.py`, `pipeline/agent_tools_v2.py` | Current reconstruction agent (E10/E11) | Live E10/E11 scripts and `test_agent_v2.py`/`test_agent_tools_v2.py` | No | **KEEP** |
| `docs/decisions.md` | Entirely pre-reconstruction ADR-001–011 history | No code reads it, but **dozens of current-facing docs cite it** as the "why" trail (architecture.md, summary.md, experiment_registry.md, INDEX.md, evaluation docs, pipeline/config.py comments, etc.) | **YES** — every "see docs/decisions.md" pointer needs replacing with the matching reconstruction ADR/experiment before deletion, or the file becomes dangling doc rot | **HOLD — link migration required, see judgment call #2** |
| `docs/experiments.md` | Entirely pre-reconstruction T-/B-/C-series ledger | Same pattern — cited by `docs/experiment_registry.md` as "the full chronological ledger" for that era, plus several other docs | **YES** — same link-migration need | **HOLD — link migration required, see judgment call #2** |
| `frontend/app/project/BuildTab.tsx:232` | Renders a raw filesystem path (`docs/experiment_registry.md, experiments/${e.id}_*/summary.md`) in user-facing UI | N/A | Reword to a human-readable label | **FIX (doc/UI edit, not deletion)** |
| "benchmark" terminology (~35+ call sites: README.md, docs/summary.md, docs/architecture.md, frontend/app/experiments/page.tsx, frontend/app/project/OverviewTab.tsx, frontend/components/project/Primitives.tsx, frontend/data/project-presentation.json, scripts/build_project_presentation_data.py) | User wants "benchmark" removed from current-facing language | This is **current, deliberate, load-bearing vocabulary** for the FULL-vs-RAG distinction, not leftover Gemini-era language | Systematic rename across markdown, a TSX type/enum (`Status = "baseline" \| "benchmark" \| ...`), generated JSON, and its Python generator | **HOLD — confirm scope, see judgment call #3** |

## No stale current-facing claims found (nothing to fix)
Repo-wide sweep found **zero** current-facing hits for: "Gemini selected/active", "RAG+agent" as a production claim, "confidence router active", "FULL fallback" as active, "dense/FAISS retrieval" as current, "classify_v6 current". Every mention of these in README/docs/architecture is already correctly framed as historical or as an explicit "this is NOT active" disclaimer. Good news — this part needs no work.

## Case Explorer / Agent Story data provenance (confirmed, not yet acted on)
`scripts/build_project_presentation_data.py` hard-loads the 4 legacy `run_T041_*_google_gemini-2.5-flash-lite.jsonl` files to build the entire Case Explorer (`case_index`, per-case Rule/FULL/RAG/Agent columns, "Start here" picks). The per-case "Agent" column shown when clicking through a case is legacy Gemini T041 data — the reconstruction-era E11 agent numbers only appear as headline aggregates and as separate raw tool-call traces, never joined per-case. The UI already discloses this mismatch via a visible banner. This is judgment call #1.

---

## Three judgment calls before Phase 2/3 can proceed

**#1 — Case Explorer rebuild.** Your brief says: use only E17/E17B (FULL)/E20 (RAG)/E04 (Rule)/E11 (Agent) reconstruction data for Case Explorer, and where no matched reconstruction-era case exists across all four architectures, show "Not available for this configuration" rather than substituting legacy data. This is not a deletion — it's a real rebuild of `scripts/build_project_presentation_data.py`'s Case Explorer section, and I don't yet know whether E04/E17/E17B/E20/E11 actually share a joined per-case population the way T041 did (T041 was explicitly built as "the only saved per-case, cross-architecture dataset in the repo" per its own disclosure banner). If they don't share a population, Case Explorer may end up much thinner (fewer or no populated case cards) than what's currently shown. Similarly `build_e00b_forecast.py` needs a small frozen extract of historical cost inputs moved into `experiments/E00B_budget_forecast/inputs/` before `results/archive/runs/` and `results/final/legacy/` can be deleted.

**#2 — docs/decisions.md and docs/experiments.md link migration.** Deleting them (as your brief suggests as a candidate) means rewriting dozens of "see docs/decisions.md ADR-00X" pointers scattered across current docs to point at the matching reconstruction-era ADR/experiment instead — a large, mechanical but non-trivial edit pass, and some old ADRs (pre-reconstruction model/retrieval choices) may have no reconstruction-era equivalent to point to at all.

**#3 — "benchmark" rename scope.** The term is currently the load-bearing word distinguishing "FULL = strongest measured configuration" from "RAG = served runtime" across ~35+ sites including a TypeScript type union and status-styling map. Renaming it means touching README.md, docs/summary.md, docs/architecture.md, three frontend files (including a shared `Status` type consumed elsewhere), a generated JSON file, and its Python generator — consistently, everywhere, in one pass, or the FULL/RAG distinction becomes internally inconsistent mid-rename.

**Resolution (verified 2026-09-30):**
- **#1 Case Explorer** — resolved without legacy substitution. `scripts/build_project_presentation_data.py`
  joins only reconstruction-v2 per-case files (Rule=E04/E17, FULL=E17/E17B, RAG=E20); the disjoint
  E11 agent population (TRAIN n=150) has no per-case match, so the Agent column is left unpopulated
  with an honest "No matched reconstruction result available" label rather than backfilled from T041.
  `build_e00b_forecast.py` was switched to a frozen extract at
  `experiments/E00B_budget_forecast/inputs/` (see that folder's README) instead of the deleted
  `results/archive/runs/` paths.
- **#2 docs/decisions.md / docs/experiments.md** — kept (not deleted), each opens with an explicit
  "historical evidence only, not the current decision" banner pointing to
  `docs/architecture_decisions/INDEX.md` for the live reconstruction-v2 ADRs.
- **#3 "benchmark" rename** — done in the primary user-facing surfaces (README.md, docs/summary.md,
  docs/architecture.md, frontend). It remains in a handful of internal/technical docs
  (`docs/experiment_registry.md`, `docs/evaluation_protocol.md`, etc.) where it is not user-facing.
