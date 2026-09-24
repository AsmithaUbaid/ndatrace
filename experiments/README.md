# Running Experiments

Experiments are configured via JSON files in `configs/` (currently empty — in practice, every
experiment in this project was run via a dedicated standalone script in `scripts/run_*.py` or
`scripts/compare_*.py`, not via a generic `run_experiment.py --config` entry point; this directory
and its config-driven pattern were part of the original plan but were not the pattern actually
used).

The authoritative, chronological experiment ledger is `docs/experiments.md`. The reasoning and
decision behind each major experiment is in `docs/decisions.md`. The original experiment register
(Section 8 of `docs/archive/initial_project_plan.md`) is historical planning, not a live index.
