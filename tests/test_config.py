"""Tests for config helpers — domain normalization and model picker list."""

import pytest

from config import (
    OPENAI_GUIDANCE_MODEL,
    available_models,
    normalise_freshservice_domain,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("acme", "acme"),
        ("ACME", "acme"),
        ("https://acme.freshservice.com/", "acme"),
        ("acme.freshservice.com", "acme"),
        ("  acme  ", "acme"),
    ],
)
def test_normalise_domain(raw, expected):
    assert normalise_freshservice_domain(raw) == expected


def test_normalise_domain_rejects_empty():
    with pytest.raises(ValueError):
        normalise_freshservice_domain("")


def test_available_models_lists_guidance_default_first_and_unique():
    models = available_models()
    assert isinstance(models, list) and models
    assert models[0] == OPENAI_GUIDANCE_MODEL
    assert len(models) == len(set(models))  # no duplicates
