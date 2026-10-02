# UI-to-report content map

Audit of `frontend/app/project/{OverviewTab,CaseExplorerTab,BuildTab}.tsx` and
`frontend/data/projectPresentation.ts`/`project-presentation.json` against the final report
(`report/NDATrace_Final_Report.html`) and canonical experiment artifacts. Source-of-truth
order used throughout: Problem Statement > canonical experiment artifacts > notebooks/ADRs > UI.
The UI is presentation and explanatory material; where it disagreed with a canonical artifact,
the artifact won and the disagreement is logged below.

## Retained or already equivalent (no report change)

| UI section | What it shows | Report equivalent |
| --- | --- | --- |
| `BuildTab`'s build/rent table | Layer-by-layer ownership | Report Section 2 table (same content, same source) |
| `BuildTab`'s runtime flow / controls | Pre-model, model-boundary, post-model guardrails | Report Figure 1 + Section 2 prose |
| `CaseExplorerTab` | Interactive browser over saved TEST/TRAIN cases | Report Section 5's case table (007/043/034/038/040/001) and the checked-in `examples/case_success/`, `examples/case_failure/` worked examples cover the same cases without the interactive layer |
| `AgentTools`'s "why only two tools" / excluded-tools panel | Tool-surface rationale | Folded into the new agent-investigation table (see below) |
| `CostToServeCurve` / `CostFormula` (`C_total = C_AI + (1-p_joint) x C_human`) | A hypothetical selective-review cost curve at enterprise volumes | Conceptually the same territory as report Figure 5 (cost-to-serve sensitivity), which already explores review-time/rate/volume/success-rate scenarios. Not imported as a second formula: its `(1-p_joint)` term assumes only *failed* cases get human review, which is in tension with E15's own finding (routing/selective review rejected, residual error too high) and with the report's explicit "no case skips review" assumption. The UI chart is itself labeled "Modeled, not realized savings," so this is a labeling-consistent hypothetical, not a contradiction requiring correction — just not re-imported as a competing cost model |

## Added to the report (new, sourced from the UI's framing, verified against canonical artifacts)

| Addition | UI source | Verified against | Where it landed |
| --- | --- | --- | --- |
| Architecture ladder table (Rule=baseline, FULL=reference, RAG=adopted, Agent=rejected) | `OverviewTab`'s `ArchitectureLadder` / `p.architectureLadder` | `results/final/v2/rule_full_test_metrics.json`, `results/final/v2/gpt_full_test_metrics.json`, `experiments/E20_final_rag_test/results/E20_final_report.json`, `experiments/E11_selective_agent_evaluation/summary.md` — all four numbers matched exactly | New table at the top of report Section 3 |
| Full experiment-index table (31 rows, not just the 8 headline ones) | Requested directly, cross-checked against `docs/experiment_registry.md` | Each row's outcome phrase matches its registry entry | New appendix table, report Section 3 |
| Agent-investigation table (diagnostic -> reassessment -> design freeze -> empirical test) and the explicit rejection argument | `AgentJustification`, `AgentTools`, `AgentExperiments` components | `experiments/E08_rag_failure_analysis/`, `E09_agent_justification/`, `E10_agent_design/`, `E11_selective_agent_evaluation/` summaries | New table + prose, report Section 3 |

## Discrepancy found and corrected

**Agent tool count.** The report's first draft of the new agent table said "a 3-tool agent," following `docs/experiment_registry.md`'s E10 line ("Frozen minimal tool set (3, not the historical 5)"). Cross-checking against the UI (`AgentTools`'s `t.tools`, which lists exactly two: `FOLLOW_CROSS_REFERENCE`, `GET_MORE_CANDIDATES`) surfaced the discrepancy. `experiments/E10_agent_design/summary.md` itself resolves it: Section 7 is explicitly titled "Exact minimal tool set (**2 tools**, revised from an initial 3-tool draft, not the historical 5)," and states "`get_definition` was dropped as a standalone action before implementation." `experiments/E11_selective_agent_evaluation/summary.md`'s logged tool calls (`FOLLOW_CROSS_REFERENCE`: 0, `GET_MORE_CANDIDATES`: 0) confirm only two tools existed at runtime. The registry's "3" is stale, pre-dating that revision, and was not updated. **The report was corrected to say 2 tools**, with the dropped third tool noted; the registry itself was left untouched (frozen historical record, not reader-facing narrative, per this project's established practice of fixing narrative documents rather than rewriting frozen experiment logs).

## Not imported

- `CaseExplorerTab`'s live filter/search UI and raw structured-output traces: presentation-layer interactivity, not an analytical finding: nothing to extract into static report prose.
- `BuildTab`'s "smallest working product slice" milestone (`experiments/E00_smallest_slice/`): confirmed to exist and be accurate, but it is a development-process milestone, not an evaluation result; out of scope for an analytical report built around measured outcomes.
