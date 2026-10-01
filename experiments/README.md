# Running Experiments

Experiments are configured via JSON files in `configs/` (currently empty — in practice, every
experiment in this project was run via a dedicated standalone script in `scripts/run_*.py` or
`scripts/compare_*.py`, not via a generic `run_experiment.py --config` entry point; this directory
and its config-driven pattern were part of the original plan but were not the pattern actually
used).

The original experiment register (Section 8 of the initial project planning document, removed
from the repository, see git history) was historical planning, not a live index.

## Final

New final experiments (`E00` onward) get their own subdirectory here, e.g.
`experiments/E01_oracle_reasoning_ceiling/`, following the template at
`experiments/_template/README.md` and the rules in `docs/experiment_protocol.md`. The planned
sequence and its status is `docs/experiment_registry.md`. No `E##` directories exist yet —
this phase only adds the scaffolding.
