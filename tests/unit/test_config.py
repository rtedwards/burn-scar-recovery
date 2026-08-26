"""Tests for settings: what the machine provides.

The chip plan is deliberately not here. It lives on ``RunConfig`` because
phase 4 sweeps the stride, and a swept knob must be inside the hashed
configuration. See ``test_runs.py``.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from burn_scar_recovery import Settings, __version__, get_logger


def test_version_is_exported() -> None:
    assert __version__


def test_defaults_match_the_roadmap() -> None:
    settings = Settings()
    # HLS sits in us-west-2. Reading from elsewhere adds latency to every
    # range request, which is the thing the project measures.
    assert settings.aws_region == "us-west-2"
    assert settings.cmr_stac_url.startswith("https://")


def test_chip_plan_is_not_on_settings() -> None:
    """A swept knob on Settings would hash identically across a sweep.

    Phase 4 sweeps the stride. If it lived here rather than on RunConfig,
    every run of that sweep would share a run ID and the results table would
    compare unlike things while claiming they were the same.
    """
    assert "chip_size" not in Settings.model_fields
    assert "chip_stride" not in Settings.model_fields


def test_secrets_are_not_in_the_repr() -> None:
    settings = Settings(earthdata_password=SecretStr("hunter2"))
    assert "hunter2" not in repr(settings)
    assert settings.earthdata_password is not None
    assert settings.earthdata_password.get_secret_value() == "hunter2"


def test_settings_are_frozen() -> None:
    settings = Settings()
    with pytest.raises(ValidationError):
        settings.aws_region = "eu-west-1"


def test_logger_is_usable() -> None:
    assert get_logger("burn_scar_recovery.tests").name == "burn_scar_recovery.tests"
