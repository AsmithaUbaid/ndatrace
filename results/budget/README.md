# Budget tracking

Empty until E00B runs. This is not calculated in this phase — see
`docs/project_contract.md` §14 and Contradiction #4: `.env`'s `MAX_BUDGET_USD=6.99` is stale
(last verified 2026-09-22, before substantial logged T041 spend) and must not be treated as
current remaining credit.

E00B will reconcile, and write its output here:

- actual historical hosted spend (derivable from `results/runs/*.jsonl` and
  `results/final/*.jsonl` cost fields, and `data/cost_estimates.json` /
  `data/budget_plan.json` as historical inputs — not yet re-summed)
- remaining user credit (must be freshly verified against the provider, not assumed)
- projected Oracle spend (E01)
- projected prompt-selection spend (E03)
- projected hosted-vs-local spend (E15)
- reserve
- estimated runtime

No API calls, recomputation, or budget figure is produced in this phase.
