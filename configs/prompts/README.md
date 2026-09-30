# Prompt configs (final naming convention)

Existing prompt text is not rewritten or moved yet — it stays at `prompts/*.txt`.
The historical `classify_v1.txt`-`classify_v6.txt`/`agent_step_v1*.txt`/`agent_step_v2.txt`
lineage this note originally pointed at was removed in the 2026-09-29 legacy cleanup pass —
see `prompts/README.md` for what's live now and the decision history.

Going forward, final prompt versions get a structured file under
`configs/prompts/classification/` or `configs/prompts/agent/`, named:

```
classification_p00.yaml
classification_p01.yaml
agent_p00.yaml
```

Each file should eventually contain:

```yaml
version:
purpose:
system_instructions:
user_template:
output_schema:
date:
experiment_that_introduced_it:   # e.g. E03
```

No files exist under `classification/` or `agent/` yet — this is a naming-convention
placeholder for E03 (prompt selection), not a migration of the historical `.txt` prompts.
