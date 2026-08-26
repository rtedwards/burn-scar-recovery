"""The run configuration and the run record.

The project produces nine table rows, a dozen measurements for each phase, two
machines and several sweeps. This module is what all of that is written into.

Two objects, with different jobs:

* :class:`RunConfig` describes *what a run does*. It is immutable and its hash
  is the run identifier. It holds no paths and no secrets, so the same
  experiment on two machines produces the same identifier.
* :class:`RunRecord` describes *what happened*. One is appended to
  ``results/runs.jsonl`` for each run, and the README tables are generated
  from that file.

Settings, in :mod:`burn_scar_recovery.config`, is a third thing and is
deliberately not hashed: it holds credentials and machine-local paths, which
must not change a run identifier.

See ``docs/conventions.md``.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Length of the hex digest kept as a run identifier. 12 hex characters is 48
#: bits, which is far beyond collision range for a few thousand runs and short
#: enough to paste into a table cell.
_RUN_ID_LENGTH: Final = 12

RUNS_FILENAME: Final = "runs.jsonl"


class RunConfig(BaseModel):
    """An immutable description of one run. Its hash is the run identifier.

    A sweep is a list of these. A sweep is never a set of edited constants: if
    a knob lives outside this object, two runs that differ produce the same
    identifier and the results table silently compares unlike things.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # -- Extent ---------------------------------------------------------------
    tiles: tuple[str, ...] = Field(default=(), description="MGRS tile identifiers.")
    start_date: str = Field(default="2017-07-01", description="Inclusive ISO date.")
    end_date: str = Field(default="2025-06-30", description="Inclusive ISO date.")

    # -- Band projection ------------------------------------------------------
    # Six bands matching the model, plus Fmask for the probe read.
    bands: tuple[str, ...] = Field(default=("B02", "B03", "B04", "B8A", "B11", "B12"))

    # -- Chip plan ------------------------------------------------------------
    # These live here and not in Settings because phase 4 sweeps the stride.
    # 224/192 gives a 16 px halo and 1.36x read amplification.
    chip_size: int = Field(default=224, gt=0)
    chip_stride: int = Field(default=192, gt=0)

    # -- Read path ------------------------------------------------------------
    align_windows: bool = Field(
        default=True,
        description="Align read windows to COG internal tile boundaries.",
    )
    two_phase_read: bool = Field(
        default=True,
        description="Read Fmask first, then fetch the six bands for clear chips only.",
    )
    max_scene_cloud_cover: float = Field(default=80.0, ge=0.0, le=100.0)
    min_chip_clear_fraction: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Open decision, phase 2. Record the drop rate for each value.",
    )
    gdal_options: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="GDAL environment knobs, as sorted pairs so the hash is stable.",
    )

    # -- Compute --------------------------------------------------------------
    batch_size: int = Field(default=32, gt=0)
    precision: str = Field(default="fp32")
    cpu_actors: int = Field(default=1, gt=0)
    gpu_actors: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _check_chip_plan(self) -> Self:
        if self.chip_stride > self.chip_size:
            msg = (
                f"chip_stride {self.chip_stride} exceeds chip_size "
                f"{self.chip_size}, which would leave gaps between chips"
            )
            raise ValueError(msg)
        return self

    @property
    def halo(self) -> int:
        """Pixels of overlap on each side of a chip."""
        return (self.chip_size - self.chip_stride) // 2

    @property
    def stride_read_amplification(self) -> float:
        """Bytes read per byte of unique ground, from the chip overlap alone."""
        return (self.chip_size / self.chip_stride) ** 2

    def canonical_json(self) -> str:
        """Return the configuration as canonical JSON, for hashing."""
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

    @property
    def run_id(self) -> str:
        """A stable identifier for this configuration.

        Built with :mod:`hashlib` over canonical JSON, never with :func:`hash`.
        CPython salts :func:`hash` for strings per process, so a builtin hash
        would give a different identifier on every run and quietly destroy the
        property this whole module exists for.
        """
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return digest[:_RUN_ID_LENGTH]


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def git_revision(repo: Path | None = None) -> str:
    """Return the current commit, with ``-dirty`` appended if the tree is not clean.

    The suffix matters. A measurement taken from a modified tree cannot be
    reproduced from the commit alone, and a record that hides that fact is
    worse than one that has no revision at all.

    Args:
        repo: Repository to inspect. Defaults to the current directory.

    Returns:
        A short commit hash, or ``"unknown"`` if this is not a git checkout.
    """
    cwd = repo or Path.cwd()
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 - git resolved from PATH
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],  # noqa: S607 - git resolved from PATH
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except subprocess.SubprocessError, OSError:
        return "unknown"
    return f"{sha}-dirty" if status else sha


class RunRecord(BaseModel):
    """One row of the results table. Append one for each run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    config: RunConfig
    label: str = Field(description="Which table row this run fills.")
    phase: str = Field(default="", description="Roadmap phase, for grouping.")

    git_sha: str = Field(default_factory=git_revision)
    machine: str = Field(default_factory=platform.node)
    platform_tag: str = Field(default_factory=platform.platform)
    recorded_at: str = Field(default_factory=_utc_now_iso)

    # -- The measurements -----------------------------------------------------
    # Bytes first. Bytes saved is a property of the pipeline and holds at any
    # link speed. Seconds is a property of the machine this ran on.
    #
    # Provenance is explicit, because most pushdown rows are COMPUTED rather
    # than observed and a column labelled "bytes read" that actually holds
    # "bytes required" is exactly the quiet drift this project avoids
    # elsewhere. See burn_scar_recovery.sizes and docs/conventions.md.
    accounting: Literal["analytic", "wire", "both"] = Field(
        default="analytic",
        description="How the byte figures below were arrived at.",
    )
    bytes_required: int = Field(
        default=0,
        ge=0,
        description="Computed exactly: summed sizes of the assets this config needs.",
    )
    bytes_baseline: int = Field(
        default=0,
        ge=0,
        description="Computed exactly: what a naive read of the same extent needs.",
    )
    bytes_observed: int | None = Field(
        default=None,
        ge=0,
        description="Measured on the wire. Only set where wire observation ran.",
    )
    requests: int = Field(default=0, ge=0)
    tile_dates: int = Field(default=0, ge=0)
    chips_total: int = Field(default=0, ge=0)
    chips_dropped: int = Field(default=0, ge=0)
    wall_seconds: float = Field(default=0.0, ge=0.0)
    gpu_utilization: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str = ""

    @property
    def saved_fraction(self) -> float | None:
        """Fraction of the naive read this configuration avoided.

        This is the pushdown claim, and it is computed rather than measured, so
        it holds at any link speed and on any machine.
        """
        if self.bytes_baseline <= 0:
            return None
        return 1.0 - (self.bytes_required / self.bytes_baseline)

    @property
    def read_amplification(self) -> float | None:
        """Bytes actually fetched for each byte required.

        ``None`` unless wire observation ran. This is the one figure that
        cannot be computed: the gap between blocks needed and bytes pulled
        comes from GDAL's fetch granularity, which is the thing phase 2
        measures rather than models.
        """
        if self.bytes_observed is None or self.bytes_required == 0:
            return None
        return self.bytes_observed / self.bytes_required

    @property
    def chips_per_second(self) -> float | None:
        """Inference rate. ``None`` when the run was not timed."""
        if self.wall_seconds == 0.0:
            return None
        return self.chips_total / self.wall_seconds

    @property
    def megabytes_per_second(self) -> float | None:
        """Sustained read rate. ``None`` when the run was not timed."""
        if self.wall_seconds == 0.0 or self.bytes_observed is None:
            return None
        return self.bytes_observed / self.wall_seconds / 1_000_000


def append_run(record: RunRecord, results_dir: Path) -> Path:
    """Append one run record to ``results/runs.jsonl``.

    JSON Lines rather than Parquet, on purpose: an append is one line, a
    conflict is readable, and a reviewer can see in a diff what a commit
    claims to have measured.

    Args:
        record: The record to append.
        results_dir: Directory holding ``runs.jsonl``. Created if absent.

    Returns:
        The path written to.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / RUNS_FILENAME
    line = json.dumps(record.model_dump(mode="json"), sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return path


def load_runs(results_dir: Path) -> list[RunRecord]:
    """Return every run record, oldest first.

    Args:
        results_dir: Directory holding ``runs.jsonl``.

    Returns:
        The records. Empty if the file does not exist yet.
    """
    path = results_dir / RUNS_FILENAME
    if not path.exists():
        return []

    records: list[RunRecord] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line:
            payload: dict[str, Any] = json.loads(line)
            records.append(RunRecord.model_validate(payload))
    return records
