# Stage C2 — RAG evidence/retrieval-risk routing

No hosted calls were made. All routers use runtime-only features; gold and the E09 failure taxonomy are scorer-only.

## Decision

**no router meets both predeclared targets; stop before agent pilot**

The inherited target is review rate ≤40% **and** residual joint error among accepted cases <10%.

The lowest residual error achievable within the workload ceiling is `R5_q10` at 27.3% review and 22.9% residual Joint error—more than twice the target.

## Router results

| Router | Routed | Review | Joint failures caught | Residual joint error | C label failures caught | C joint failures caught | Precision | False-review | Agent-eligible routed failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | 0/150 | 0.0% | 0/39 (0.0%) | 26.0% | 0/12 | 0/15 | — | 0.0% | 0/0 |
| R1 | 3/150 | 2.0% | 2/39 (5.1%) | 25.2% | 0/12 | 1/15 | 66.7% | 0.9% | 0/2 |
| R2_q10 | 18/150 | 12.0% | 6/39 (15.4%) | 25.0% | 2/12 | 4/15 | 33.3% | 10.8% | 2/6 |
| R2_q20 | 33/150 | 22.0% | 11/39 (28.2%) | 23.9% | 3/12 | 5/15 | 33.3% | 19.8% | 3/11 |
| R2_q30 | 47/150 | 31.3% | 13/39 (33.3%) | 25.2% | 5/12 | 7/15 | 27.7% | 30.6% | 3/13 |
| R3_q10 | 18/150 | 12.0% | 6/39 (15.4%) | 25.0% | 0/12 | 1/15 | 33.3% | 10.8% | 2/6 |
| R3_q20 | 33/150 | 22.0% | 7/39 (17.9%) | 27.4% | 0/12 | 1/15 | 21.2% | 23.4% | 3/7 |
| R3_q30 | 48/150 | 32.0% | 10/39 (25.6%) | 28.4% | 1/12 | 3/15 | 20.8% | 34.2% | 3/10 |
| R4_q10 | 30/150 | 20.0% | 10/39 (25.6%) | 24.2% | 2/12 | 4/15 | 33.3% | 18.0% | 4/10 |
| R4_q20 | 57/150 | 38.0% | 14/39 (35.9%) | 26.9% | 3/12 | 5/15 | 24.6% | 38.7% | 5/14 |
| R4_q30 | 80/150 | 53.3% | 18/39 (46.2%) | 30.0% | 5/12 | 8/15 | 22.5% | 55.9% | 5/18 |
| R5_q10 | 41/150 | 27.3% | 14/39 (35.9%) | 22.9% | 4/12 | 6/15 | 34.1% | 24.3% | 5/14 |
| R5_q20 | 66/150 | 44.0% | 18/39 (46.2%) | 25.0% | 5/12 | 7/15 | 27.3% | 43.2% | 6/18 |
| R5_q30 | 88/150 | 58.7% | 22/39 (56.4%) | 27.4% | 7/12 | 10/15 | 25.0% | 59.5% | 6/22 |
| H_rule_disagreement | 83/150 | 55.3% | 30/39 (76.9%) | 13.4% | 10/12 | 12/15 | 36.1% | 47.7% | 5/30 |

## Base RAG

- Accuracy: 118/150 (78.7%)
- Joint: 111/150 (74.0%)
- Contradiction Recall: 38/50 (76.0%)
- Contradiction joint success: 35/50 (70.0%)

## Agent-eligibility conclusion

No router passed the workload+safety target, so Stage C3 is not authorized regardless of diagnostic agent eligibility.

## Secondary diagnostics

- Pareto frontier: R0, R1, R2_q10, R3_q10, R4_q10, R2_q20, R5_q10, R5_q20, R5_q30
- Weak-score AUROC: 0.520
- Ambiguity-margin AUROC: 0.471
- AUROC is diagnostic only and was not used to choose a router.

## Governance

The approved pilot cost-per-net-C-recovery threshold is descriptive during a 20–30 case pilot and blocking only at confirmation. Final retention also requires the frozen Group F direct-human economic/workload comparison in `frozen_protocol.json`.
