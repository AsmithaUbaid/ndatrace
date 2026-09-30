"""E15 gold-separation guard: routing features must not read gold/correctness fields."""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import e15_routing_stage_a as E


def test_routing_signals_and_policies_never_reference_gold():
    src = inspect.getsource(E.signals) + inspect.getsource(E.R1_REASONS) + "".join(inspect.getsource(f) for f in [E.POLICIES["R2"], E.POLICIES["R3"]])
    for banned in ("gold", "joint", "label_ok", "joint_ok"):
        assert banned not in src.replace("ASSERT_NO_GOLD", ""), banned


def test_policies_are_monotone_supersets_of_r1():
    s = {"unusable": False, "label": "Entailment", "n_quotes": 1, "n_hallucinated_v2": 1, "rule_label": "Entailment"}
    assert E.POLICIES["R1"](s) and E.POLICIES["R2"](s) and E.POLICIES["R3"](s) and not E.POLICIES["R0"](s)
