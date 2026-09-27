# Agent Prompt V1 versus V2 — pre-run review

Status: **FROZEN FOR REVIEW; STOPPED BEFORE HOSTED EXECUTION.**

## 1. Verified historical result

Repository artifacts reproduce the required V1 result on the frozen 150-case TRAIN population:
base Accuracy 118/150 (78.7%), Joint 113/150 (75.3%), and Contradiction Recall 38/50
(76.0%); V1 Accuracy 117/150 (78.0%), Joint 110/150 (73.3%), and Contradiction Recall
35/50 (70.0%). V1 produced 0 Contradiction recoveries and 3 regressions, 5/6 classification
recoveries/regressions, 5/8 Joint recoveries/regressions, 2/150 tool-using cases, 148/150
step-one FINAL-without-tool cases, 152 hosted calls, and $0.22720225 cost. These artifacts are
reused without alteration.

## 2. Exact prompts

The exact prompts are frozen as `prompt_v1.txt` and `prompt_v2.txt`. `prompt_v1.txt` is
byte-identical to `prompts/agent_v2_control.txt`, SHA-1
`30781d7cac504c7887f2ae0dc63c1564f5430df9`. V2 SHA-1 is
`d3c059dca56300825c788c6653c3752470fe74ed`.

## 3. Section-level difference and rationale

| V1 | V2 change | Why |
|---|---|---|
| Brief investigator role | Defines an evidence-grounded NDA investigation controller and bars external knowledge | Makes context sufficiency, rather than immediate relabeling, the controller's job without adding a capability |
| “Most cases should conclude immediately” | Removed | This sentence directly biases the first action toward FINAL and is the ablated hypothesis |
| Informal “would one lookup help?” | Five mandatory silent checks before every action | Makes the intended decision procedure explicit while preserving the JSON-only output and avoiding emitted chain-of-thought |
| Cross-reference tool only when an explicit target is absent | Retained, with a materiality test | Preserves the tool schema while ensuring unresolved definitions/provisions are checked |
| No exception/completeness checklist | Adds qualification, completeness, alternative-evidence, and Contradiction-safety checks | Covers the missing-context failure modes named in the research question |
| `GET_MORE_CANDIDATES` only when none of the shown evidence addresses the requirement | Allows it when ranks outside top five could contain a material qualification, neighbor, or alternative clause | Aligns the frozen tool with its actual ability to expose ranks 6–10 without changing retrieval |
| FINAL whenever current evidence seems sufficient | FINAL only after all material missing-context checks pass | Raises the decision threshold for zero-tool FINAL |
| No explicit post-tool reassessment | Repeats the same checks after tool output and instructs FINAL once adequately supported | Prevents quota calls and uncontrolled looping |
| JSON schema and prompt-injection defense | Retained verbatim in substance | Preserves parser/control safety and direct comparability |

The qualifier check explicitly says that a cue word alone does not require a call. Tool use is
therefore purposeful rather than mandatory.

## 4. Frozen variables

No other system variable changes. Arms A and B reuse existing data. Arm C uses the same 150
ordered TRAIN cases, base RAG outputs, GPT-5-mini through OpenRouter, temperature 0, retry cap 1,
30-second request timeout, forced entry, controller implementation, two read-only tools, maximum
3 agent steps, maximum 2 tools, duplicate protection, 8,000-character context cap, 60-second
case cap, $0.01 estimated per-case circuit breaker, fallback, strict action parser, FINAL schema,
runtime validator v2, and evidence evaluator v2 at tau 0.5.

The post-approval experiment runner will change only the prompt path in its own process before
calling the existing loop. It will not edit `pipeline/agent_v2.py` or the historical V1 prompt.
Hash assertions will fail closed if any frozen input changes.

## 5. Expected behavior

V2 should reduce first-step FINAL actions specifically where the top-five context contains an
unresolved, materially relevant reference, qualification, missing neighbor, or plausible need
for lower-ranked evidence. It may still choose FINAL immediately when the shown context is
self-contained. Increased tool use is only a behavioral manipulation check; retention still
requires positive Joint and Contradiction value and the frozen evidence guardrails.

## 6. Risks

- **Over-tool-use:** common legal cue words may trigger calls even when their meaning is already complete.
- **Latency/cost growth:** a one-tool-then-FINAL path doubles model calls; the structural maximum triples them.
- **Unnecessary retrieval:** ranks 6–10 may be redundant or distract the controller.
- **Quality regression:** added clauses may cause label instability or worsen evidence selection/source validity.
- **Tool mismatch:** the two narrow tools may not retrieve the context V2 identifies as missing.
- **Control failure:** a longer prompt may increase malformed actions or exhaust the three-step limit before FINAL.

## 7. Calls and cost

Exactly **150 new case executions** are planned and **zero V1/base calls** will be repeated. The
number of hosted model calls cannot be fixed to one number without changing the adaptive loop:
it is exactly bounded at 150 minimum and 450 structural maximum; the declared point estimate is
300 (one tool action followed by FINAL per case). This uncertainty is part of the treatment and
will be reported as an actual count.

The V2 prompt is 800 `cl100k_base` tokens. Across the exact 150 first-turn messages, the
deterministic planning count is 275,835 input tokens (mean 1,838.9; median 1,855; p90 1,991;
max 2,463). At the frozen $0.25/M input and $2.00/M output prices:

| Scenario | Calls | Planning assumptions | Estimated cost |
|---|---:|---|---:|
| Minimum | 150 | one step; V1 observed mean output/call | $0.2403 |
| Point estimate | 300 | one tool then FINAL; +1,000 input tokens on later turn; V1 mean output | **$0.5181** |
| Conservative | 450 | three steps; +1,000 tokens per accumulated tool turn; observed A2 maximum output/call | **$1.9925** |

Because output length and adaptive actions are unknowable before execution, these are exact
calculations under declared scenarios, not a false claim that actual spend is knowable. The
exact hard run-level ceiling is **$3.00**. Immediately after approval, the provider balance will
be refreshed; execution will not start unless at least $3.25 remains (ceiling plus $0.25 reserve).
The runner will check cumulative actual spend before every call and stop safely at the ceiling.

## 8. Post-approval execution and stopping rule

After approval only: freeze hashes again, create a scorer-free manifest, run V2 append-only and
resumably over all 150 cases, then score Base/V1/V2 only after the raw V2 trace is complete. V2
will not be edited after partial outcomes are visible. Results will include behavior, quality,
Contradiction transitions, tool effectiveness, guardrails, cost, latency, and safety/control
events. No R6 or other routing experiment will be designed in this stage.

**Approval requested:** authorize transmitting the same 150 TRAIN NDA cases to OpenRouter for
the V2 full-agent run under the frozen prompt and $3.00 hard ceiling. Until approval, stop.
