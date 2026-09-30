"""Regression test for the model-config source-of-truth fix (grading audit section 3).

Guards against the runtime silently drifting back to a hardcoded model that
disagrees with pipeline/config.py's settings.default_model.
"""

from pipeline.config import settings
from pipeline import final_review


def test_default_model_is_gpt5_mini():
    assert settings.default_model == "openai/gpt-5-mini"


def test_final_review_model_matches_settings():
    # final_review.MODEL must be sourced from settings, not hardcoded,
    # so there is exactly one place that defines the shipped model.
    assert final_review.MODEL == settings.default_model
