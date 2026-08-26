"""Tests for the run configuration and the run record."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from burn_scar_recovery.runs import (
    RUNS_FILENAME,
    RunConfig,
    RunRecord,
    append_run,
    load_runs,
)

if TYPE_CHECKING:
    from pathlib import Path


def _record(**kwargs: object) -> RunRecord:
    config = RunConfig()
    defaults: dict[str, object] = {
        "run_id": config.run_id,
        "config": config,
        "label": "test",
    }
    return RunRecord.model_validate(defaults | kwargs)


# -- The chip plan -----------------------------------------------------------


def test_halo_comes_out_of_the_stride() -> None:
    assert RunConfig(chip_size=224, chip_stride=192).halo == 16
    assert RunConfig(chip_size=224, chip_stride=208).halo == 8


@pytest.mark.parametrize(
    ("stride", "expected"),
    [(208, 1.16), (192, 1.36), (176, 1.62), (160, 1.96)],
)
def test_read_amplification_matches_the_roadmap_table(stride: int, expected: float) -> None:
    """The stride/amplification table in ROADMAP.md phase 4."""
    amplification = RunConfig(chip_stride=stride).stride_read_amplification
    assert amplification == pytest.approx(expected, abs=0.005)


def test_stride_larger_than_chip_is_rejected() -> None:
    """A stride above the chip size leaves unread ground between chips."""
    with pytest.raises(ValidationError, match="leave gaps"):
        RunConfig(chip_size=224, chip_stride=256)


# -- The run identifier ------------------------------------------------------


def test_run_id_is_stable_for_equal_configs() -> None:
    assert RunConfig().run_id == RunConfig().run_id


def test_run_id_changes_when_a_swept_knob_changes() -> None:
    """This is the property the whole sweep design rests on."""
    assert RunConfig(chip_stride=192).run_id != RunConfig(chip_stride=176).run_id


def test_run_id_ignores_field_order() -> None:
    a = RunConfig(chip_size=224, chip_stride=176)
    b = RunConfig(chip_stride=176, chip_size=224)
    assert a.run_id == b.run_id


def test_run_id_is_stable_across_processes() -> None:
    """The reason run_id uses hashlib and never the builtin hash().

    CPython salts hash() for strings per process unless PYTHONHASHSEED is
    pinned. A builtin hash would therefore give a different run ID on every
    run, and the whole point of the identifier would be silently lost. Two
    interpreters with different seeds must agree.
    """
    program = (
        "from burn_scar_recovery.runs import RunConfig;print(RunConfig(chip_stride=176).run_id)"
    )
    seeds = ["0", "12345"]
    outputs = [
        subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        ).stdout.strip()
        for seed in seeds
    ]
    assert outputs[0] == outputs[1]
    assert outputs[0] == RunConfig(chip_stride=176).run_id


def test_config_is_frozen() -> None:
    config = RunConfig()
    with pytest.raises(ValidationError):
        config.chip_stride = 160


def test_unknown_field_is_rejected() -> None:
    """extra='forbid' stops a typo becoming an untracked knob.

    Constructed through model_validate because mypy catches the typo in the
    keyword form. Both defences are wanted: the type checker for code, and
    extra='forbid' for a config loaded from JSON at runtime.
    """
    with pytest.raises(ValidationError):
        RunConfig.model_validate({"chip_strid": 176})


def test_canonical_json_sorts_keys() -> None:
    payload = json.loads(RunConfig().canonical_json())
    assert list(payload) == sorted(payload)


# -- Derived measurements ----------------------------------------------------


def test_saving_is_computed_from_the_baseline() -> None:
    """The pushdown claim. Computed, so it holds at any link speed."""
    record = _record(bytes_required=250, bytes_baseline=1000)
    assert record.saved_fraction == pytest.approx(0.75)


def test_saving_is_none_without_a_baseline() -> None:
    assert _record(bytes_required=250).saved_fraction is None


def test_read_amplification_needs_wire_observation() -> None:
    """It is the one figure that cannot be computed.

    Defaulting it to 1.0 from analytic figures alone would invent a
    measurement, and would claim the alignment row was filled when it was not.
    """
    assert _record(bytes_required=100).read_amplification is None


def test_read_amplification_divides_observed_by_required() -> None:
    record = _record(bytes_required=100, bytes_observed=136, accounting="both")
    assert record.read_amplification == pytest.approx(1.36)


def test_accounting_defaults_to_analytic() -> None:
    assert _record().accounting == "analytic"


def test_accounting_rejects_an_unknown_provenance() -> None:
    with pytest.raises(ValidationError):
        _record(accounting="guessed")


def test_rates_are_none_when_the_run_was_not_timed() -> None:
    record = _record(chips_total=100)
    assert record.chips_per_second is None
    assert record.megabytes_per_second is None


def test_throughput_needs_observed_bytes() -> None:
    """MB/s is a wire figure; required bytes cannot stand in for it."""
    record = _record(bytes_required=2_000_000, wall_seconds=2.0)
    assert record.megabytes_per_second is None


def test_rates_divide_by_wall_time() -> None:
    record = _record(
        chips_total=100,
        bytes_observed=2_000_000,
        wall_seconds=2.0,
        accounting="both",
    )
    assert record.chips_per_second == pytest.approx(50.0)
    assert record.megabytes_per_second == pytest.approx(1.0)


# -- Persistence -------------------------------------------------------------


def test_append_then_load_round_trips(tmp_path: Path) -> None:
    first = _record(label="naive", bytes_required=10)
    second = _record(label="+ predicate pushdown", bytes_required=5)
    append_run(first, tmp_path)
    append_run(second, tmp_path)

    loaded = load_runs(tmp_path)
    assert [record.label for record in loaded] == ["naive", "+ predicate pushdown"]
    assert loaded[1].bytes_required == 5
    assert loaded[0].config == first.config


def test_append_creates_the_results_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "results"
    append_run(_record(), target)
    assert (target / RUNS_FILENAME).exists()


def test_load_runs_is_empty_before_anything_is_recorded(tmp_path: Path) -> None:
    assert load_runs(tmp_path) == []


def test_blank_lines_are_tolerated(tmp_path: Path) -> None:
    append_run(_record(), tmp_path)
    path = tmp_path / RUNS_FILENAME
    path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    assert len(load_runs(tmp_path)) == 1
