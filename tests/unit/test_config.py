"""Tests for settings and the chip-plan arithmetic derived from them."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from burn_scar_recovery import Settings, __version__, get_logger


def test_version_is_exported() -> None:
    assert __version__


def test_defaults_match_the_roadmap() -> None:
    settings = Settings()
    # Three tiles of southern California chaparral, and the data is in-region.
    assert settings.aws_region == "us-west-2"
    assert settings.cmr_stac_url.startswith("https://")
    # 224 chip, 192 stride. Phase 4.
    assert settings.chip_size == 224
    assert settings.chip_stride == 192


def test_halo_comes_out_of_the_stride() -> None:
    assert Settings(chip_size=224, chip_stride=192).halo == 16
    assert Settings(chip_size=224, chip_stride=208).halo == 8


@pytest.mark.parametrize(
    ("stride", "expected"),
    [(208, 1.16), (192, 1.36), (176, 1.62), (160, 1.96)],
)
def test_read_amplification_matches_the_roadmap_table(stride: int, expected: float) -> None:
    """The stride/amplification table in ROADMAP.md phase 4."""
    assert Settings(chip_stride=stride).read_amplification == pytest.approx(expected, abs=0.005)


def test_secrets_are_not_in_the_repr() -> None:
    settings = Settings(earthdata_password=SecretStr("hunter2"))
    assert "hunter2" not in repr(settings)
    assert settings.earthdata_password is not None
    assert settings.earthdata_password.get_secret_value() == "hunter2"


def test_settings_are_frozen() -> None:
    """A run config is immutable; its hash is the run ID."""
    settings = Settings()
    with pytest.raises(ValidationError):
        settings.chip_size = 128


def test_logger_is_usable() -> None:
    assert get_logger("burn_scar_recovery.tests").name == "burn_scar_recovery.tests"
