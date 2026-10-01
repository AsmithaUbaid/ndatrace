# Professor-requirement compliance matrix

This checklist separates report requirements from repository and video submission requirements. Sources reviewed: proposal watch-outs, submitted problem statement, both passes of written professor feedback, executed notebooks, experiment registry, architecture records and current runtime code.

## Report requirements

| Requirement | Evidence in fresh report | Status / risk |
| --- | --- | --- |
| Real problem, named user and changed workflow | Section 1 | Complete; no productivity claim |
| Why AI rather than rules | Section 1; Table 2; Table 3 | Complete; Rule contradiction recall shown |
| Complete build-versus-rent stack | Section 2; Table 1 | Complete; incomplete controls disclosed |
| Accurate implemented architecture | Figure 1; Section 2 | Complete; verified against `frozen_rag.py`, `final_review.py`, API routes |
| Model fit and Oracle ceiling before retrieval | Section 3; Table 2 | Complete |
| Controlled prompt/retrieval tuning | Section 3; Table 2 | Complete; differing populations not treated as direct comparisons |
| Full experimental journey without diary structure | Table 2 organised by research question | Complete |
| Unexpected FULL-versus-RAG result | Section 4; Tables 3-4; Figure 2 | Central argument |
| Original target reproduced accurately | Table 4 | Complete: +1.2 points vs required +5.0; not achieved |
| Joint metric and class-specific recall | Table 3; Figure 2; metric critique | Complete |
| Evaluation criticism | Section 4 | Complete: gold overlap, annotation, class asymmetry and benchmark-transfer limits |
| Agent measurements and actual tool behaviour | Section 5; Table 5 | Complete: 15 triggers, zero tools, net zero Joint |
| Routing workload/error trade-off | Section 5; Table 6 | Complete; no policy adopted |
| Official population-level failure evidence | Figure 3 | Complete: denominator 576 |
| Targeted case mechanisms | Section 5; Table 7 | Complete; not pooled with TEST |
| Performance tuning consequences | Table 2 and Sections 3-4 | Complete: reranker, top-K, tokens, latency and rejected dense retrieval |
| Output-token cost observation | Section 6; Table 8 | Complete |
| Cost beyond inference | Table 9; Figure 4 | Complete as assumptions; fixed cost excluded and disclosed |
| No achieved ROI claim | Section 6 | Complete; timed reviewer study proposed |
| Difficulties overcome versus unresolved | Section 7 | Complete; evaluator correction distinguished from unresolved reasoning |
| Security and responsible use | Sections 5 and 7; Table 10 | Complete; injection limitation explicit |
| Prioritised research and production work | Table 10 | Complete |
| Restrained conclusion answering research question | Section 8 | Complete |
| Approximately 1,200 words | Generated verification output | Complete if verifier passes; both prose and inclusive counts reported |
| Citations and source discipline | References; evidence map | Complete for ContractNLI and vendor research; vendor conflict disclosed |

## Separate repository/submission requirements

| Requirement | Location outside report | Status / risk |
| --- | --- | --- |
| Persona, input and output | `README.md` - Tina's problem / What NDATrace does | Present |
| Product architecture | `README.md`; `docs/architecture.md` | Present; current runtime is RAG despite historical architecture changes |
| Targeted and achieved metrics | `README.md` - Metrics: targeted vs reached | Present |
| Module responsibilities | `README.md` repository map; module docstrings | Present |
| Checked-in data and cases | `data/`; experiment manifests; targeted battery | Present subject to dataset licence |
| Reproducibility | `scripts/verify_reproducibility.py`; experiment summaries | Present |
| Installation and execution | `README.md` quick start | Present |
| Working product | FastAPI backend + Next.js frontend | Present; not modified in this task |
| Video with face and screen | User-produced submission video | **Outstanding: cannot be verified from repository** |
| Final browser/print visual approval | Open fresh HTML locally and print-preview | **Outstanding user check if automated local-browser preview remains unavailable** |

## Outstanding submission risks

- The official TEST lineage is re-derived and not tuned in the final sequence, but an older superseded lineage partially observed TEST; avoid the phrase “perfectly blind.”
- ContractNLI is not evidence of performance on confidential, long or jurisdiction-specific enterprise agreements.
- The targeted n=49 set is deliberately difficult and cannot supply population frequencies.
- Human-time savings, override frequency, rework rate and fixed operating cost remain unmeasured.
- The submitted video and local print preview still require the student's final check.
