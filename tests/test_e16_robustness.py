"""E16 Phase A: deterministic robustness/security checks (no model calls). Each check is defined in scripts/e16_phase_a.py."""
import pytest
from scripts import e16_phase_a as A


@pytest.mark.parametrize("c", A.CHECKS, ids=[c["id"] for c in A.CHECKS])
def test_phase_a_check(c):
    assert c["pass"], c["actual"]
