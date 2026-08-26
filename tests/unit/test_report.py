"""Tests for the README table generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from burn_scar_recovery.report import (
    render_read_path_table,
    splice,
    update_readme,
)
from burn_scar_recovery.runs import RunConfig, RunRecord

if TYPE_CHECKING:
    from pathlib import Path

_DOC = """# Title

Prose that must survive.

<!-- BEGIN GENERATED: read-path -->
| old | table |
<!-- END GENERATED: read-path -->

More prose.
"""


def _record(**kwargs: object) -> RunRecord:
    config = RunConfig()
    defaults: dict[str, object] = {
        "run_id": config.run_id,
        "config": config,
        "label": "naive",
    }
    return RunRecord.model_validate(defaults | kwargs)


def test_table_has_a_row_for_each_run() -> None:
    table = render_read_path_table([_record(label="naive"), _record(label="+ pushdown")])
    assert "| naive |" in table
    assert "| + pushdown |" in table


def test_bytes_come_before_seconds() -> None:
    """The project reports bytes first; the columns read in that order."""
    header = render_read_path_table([]).splitlines()[0]
    assert header.index("Bytes required") < header.index("Wall time")


def test_the_table_says_whether_a_figure_was_computed_or_measured() -> None:
    """A computed number presented as a measurement is the drift to avoid."""
    computed = render_read_path_table([_record(bytes_required=1_000_000_000)])
    assert "computed" in computed
    measured = render_read_path_table(
        [_record(bytes_required=1_000_000_000, bytes_observed=2_000_000_000, accounting="both")]
    )
    assert "computed + measured" in measured


def test_saving_is_shown_as_a_percentage() -> None:
    row = render_read_path_table(
        [_record(bytes_required=250_000_000, bytes_baseline=1_000_000_000)]
    ).splitlines()[-1]
    assert "75%" in row


def test_unmeasured_columns_are_blank_rather_than_zero() -> None:
    """A zero would claim a measurement that was never taken."""
    row = render_read_path_table([_record()]).splitlines()[-1]
    assert "0 GB" not in row
    assert "0.00x" not in row


def test_measured_values_are_formatted() -> None:
    record = _record(
        bytes_required=277_205_882_352,
        bytes_observed=377_000_000_000,
        accounting="both",
        wall_seconds=15_120.0,
        gpu_utilization=0.42,
        chips_total=850_000,
    )
    row = render_read_path_table([record]).splitlines()[-1]
    assert "277.2 GB" in row
    assert "1.36x" in row
    assert "4.20 h" in row
    assert "42%" in row


# -- Splicing ----------------------------------------------------------------


def test_splice_replaces_only_between_the_markers() -> None:
    updated = splice(_DOC, "read-path", "| new | table |")
    assert "| new | table |" in updated
    assert "| old | table |" not in updated
    assert "Prose that must survive." in updated
    assert "More prose." in updated


def test_splice_keeps_the_markers_so_it_can_run_again() -> None:
    once = splice(_DOC, "read-path", "| a |")
    twice = splice(once, "read-path", "| b |")
    assert "| b |" in twice
    assert "| a |" not in twice


def test_splice_fails_loudly_on_a_missing_marker() -> None:
    """Appending silently would put a generated table somewhere unexpected."""
    with pytest.raises(ValueError, match="no BEGIN/END GENERATED markers"):
        splice("# Title\n", "read-path", "| x |")


# -- The README ---------------------------------------------------------------


def test_no_runs_leaves_the_readme_alone(tmp_path: Path) -> None:
    """The stub tables describe the intended result. Do not wipe them."""
    readme = tmp_path / "README.md"
    readme.write_text(_DOC, encoding="utf-8")
    assert update_readme(readme, []) is False
    assert readme.read_text(encoding="utf-8") == _DOC


def test_a_run_is_written_in(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(_DOC, encoding="utf-8")
    assert update_readme(readme, [_record(bytes_required=1_000_000_000)]) is True
    assert "1.0 GB" in readme.read_text(encoding="utf-8")


def test_rerunning_with_the_same_data_reports_no_change(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(_DOC, encoding="utf-8")
    records = [_record(bytes_required=1_000_000_000)]
    assert update_readme(readme, records) is True
    assert update_readme(readme, records) is False
