# E15 addendum — RAG evidence/retrieval-risk routing

Stage C2 evaluates deterministic runtime-only routers on the frozen 150-case
`TRAIN_ARCH_v1` GPT-5-mini/P0 top-5 RAG outputs. It makes no hosted calls and does not alter the
production runtime.

`frozen_protocol.json` was written after inspecting runtime-signal distributions but before the
new router candidates were scored against gold correctness or evidence. `results/` contains the
reproducible scorer output produced by `scripts/analyze_rag_evidence_routing.py`.

The experiment stops after Stage C2. An agent pilot requires separate approval and is permitted
only if a router satisfies both the inherited review-rate and residual-joint-error targets and
the routed failures contain a meaningful information-acquisition subset.
