# Prompt configs (reconstruction-v2 naming convention)

Existing prompt text is not rewritten or moved yet — it stays at `prompts/*.txt`
(`classify_v1.txt`…`classify_v6.txt`, `agent_step_v1.txt`, `agent_step_v2.txt`; see
`prompts/README.md` for the historical version lineage).

Going forward, reconstruction-v2 prompt versions get a structured file under
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
