# E04B — Majority-class TEST baseline

This frozen, deterministic sanity check always predicts the majority label from the official ContractNLI TEST distribution. It is a **TRIVIAL BASELINE**, not an architecture rung and not a model experiment.

```bash
python3 experiments/E04B_majority_baseline/run_majority_baseline.py
```

The official TEST set contains 2,091 cases: 968 Entailment, 903 NotMentioned, and 220 Contradiction. Always predicting Entailment produces 46.3% accuracy, 0.211 Macro-F1, 0% Contradiction Recall, and 0% Joint success.

Joint is well-defined here: Entailment requires supporting evidence, but this trivial classifier returns none. Its Entailment predictions therefore fail evidence correctness, while its other predictions have the wrong label. No hosted calls are made.
