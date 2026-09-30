# Controlled agent-prompt ablation

Status: **COMPLETE; V2 REJECTED. STOPPED BEFORE ROUTING OR ARCHITECTURE CHANGES.**

This addendum tests one variable only: the agent controller prompt. Arm A reuses the frozen base
RAG outputs, Arm B reuses the completed full-agent V1 traces, and Arm C will run the same bounded
full-agent loop over the same 150 TRAIN cases with `prompt_v2.txt` after explicit approval.

The experiment did not use TEST, alter routing, change retrieval or classification, add tools,
or modify production runtime. The V2 runner selected the experimental prompt inside its own
process while calling the existing loop unchanged. See `pre_run_plan.md` and `config.json` for
the frozen comparison and budget envelope.

The approved V2 run completed all 150 cases for $0.398776. V2 increased tool use but materially
reduced overall quality and produced no useful tool-associated cases. See `summary.md` for the
decision and `results/arm_metrics.json` for exact counts.
