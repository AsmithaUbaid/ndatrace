"""
Tests for evaluation/harness.py — WBS T007, experiments A09-A11.

Covers run resumption (A09), append-only storage (A10), and config
snapshotting (A11) against a temporary results directory.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evaluation.harness import EvaluationHarness
from evaluation.schemas import ExperimentConfig, GoldCase, Label, Prediction


def make_gold(doc_id, hyp_id, label="Entailment"):
    return GoldCase(doc_id=doc_id, hypothesis_id=hyp_id, gold_label=Label(label))


def make_pred(doc_id, hyp_id, label="Entailment"):
    return Prediction(doc_id=doc_id, hypothesis_id=hyp_id, predicted_label=Label(label))


def test_run_resumption_checkpoint_roundtrip(tmp_path):
    """A09: a crashed run's checkpointed predictions can be reloaded and skipped."""
    harness = EvaluationHarness(results_dir=str(tmp_path))
    experiment_id = "test_run_001"

    assert harness.completed_case_keys(experiment_id) == set()

    harness.save_prediction_checkpoint(experiment_id, make_pred("d1", "h1"))
    harness.save_prediction_checkpoint(experiment_id, make_pred("d1", "h2"))

    keys = harness.completed_case_keys(experiment_id)
    assert keys == {("d1", "h1"), ("d1", "h2")}

    # Simulate resuming: skip cases already in the checkpoint.
    all_cases = [("d1", "h1"), ("d1", "h2"), ("d1", "h3")]
    pending = [c for c in all_cases if c not in keys]
    assert pending == [("d1", "h3")]


def test_clear_checkpoint_removes_file(tmp_path):
    harness = EvaluationHarness(results_dir=str(tmp_path))
    harness.save_prediction_checkpoint("run_002", make_pred("d1", "h1"))
    assert harness.checkpoint_path("run_002").exists()
    harness.clear_checkpoint("run_002")
    assert not harness.checkpoint_path("run_002").exists()
    assert harness.completed_case_keys("run_002") == set()


def test_save_result_is_append_only(tmp_path):
    """A10: repeated saves to the same file accumulate, never overwrite."""
    harness = EvaluationHarness(
        results_dir=str(tmp_path),
        gold_cases=[make_gold("d1", "h1")],
    )
    config = ExperimentConfig(experiment_id="exp_A")
    predictions = [make_pred("d1", "h1")]

    result1 = harness.evaluate(predictions, config)
    harness.save_result(result1, filename="run.jsonl")
    result2 = harness.evaluate(predictions, config)
    harness.save_result(result2, filename="run.jsonl")

    loaded = harness.load_results("run.jsonl")
    assert len(loaded) == 2


def test_config_snapshot_persisted_with_result(tmp_path):
    """A11: every saved run carries its full config snapshot."""
    harness = EvaluationHarness(
        results_dir=str(tmp_path),
        gold_cases=[make_gold("d1", "h1")],
    )
    config = ExperimentConfig(
        experiment_id="exp_B",
        model="openrouter/openai/gpt-5-mini",
        seed=42,
        top_k=5,
    )
    result = harness.evaluate([make_pred("d1", "h1")], config)
    harness.save_result(result, filename="run_b.jsonl")

    loaded = harness.load_results("run_b.jsonl")
    assert len(loaded) == 1
    assert loaded[0].config.experiment_id == "exp_B"
    assert loaded[0].config.model == "openrouter/openai/gpt-5-mini"
    assert loaded[0].config.seed == 42


def test_evaluate_raises_without_gold_cases(tmp_path):
    harness = EvaluationHarness(results_dir=str(tmp_path))
    config = ExperimentConfig(experiment_id="exp_C")
    try:
        harness.evaluate([make_pred("d1", "h1")], config)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_experiment_config_sample_size_round_trips(tmp_path):
    """
    Regression test: sample_size was passed by run_oracle_experiment.py but
    not declared on ExperimentConfig, so pydantic's default extra="ignore"
    silently dropped it - the field never made it into saved results.
    """
    config = ExperimentConfig(experiment_id="exp_D", sample_size=150, seed=42)
    assert config.sample_size == 150

    harness = EvaluationHarness(results_dir=str(tmp_path), gold_cases=[make_gold("d1", "h1")])
    result = harness.evaluate([make_pred("d1", "h1")], config)
    harness.save_result(result, filename="run_d.jsonl")

    loaded = harness.load_results("run_d.jsonl")
    assert loaded[0].config.sample_size == 150


def test_experiment_config_rejects_unknown_field():
    """
    extra="forbid": an undeclared field must raise immediately, not
    silently vanish the way sample_size did before this fix.
    """
    with pytest.raises(ValidationError):
        ExperimentConfig(experiment_id="exp_E", this_field_does_not_exist=123)
