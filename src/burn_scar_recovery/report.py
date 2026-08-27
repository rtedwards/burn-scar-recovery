"""Generate the README result tables from ``results/runs.jsonl``.

The tables in ``README.md`` are generated, never typed. A hand-edited number
stops matching the code that produced it and no reader can tell, which is the
quiet way a results table becomes fiction.

The generated regions are marked in ``README.md``::

    <!-- BEGIN GENERATED: read-path -->
    <!-- END GENERATED: read-path -->

Anything between a pair of markers is replaced. Anything outside them is left
alone, so the prose around the tables stays hand-written.

**With no runs recorded, this does nothing.** The README currently holds stub
tables that describe the shape of the eventual result. Replacing them with an
empty table would lose that, so the generator declines to write until there is
something real to write.

See ``docs/conventions.md``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from burn_scar_recovery.config import REPO_ROOT, get_settings
from burn_scar_recovery.log import get_logger
from burn_scar_recovery.runs import load_runs

if TYPE_CHECKING:
    from pathlib import Path

    from burn_scar_recovery.runs import RunRecord

_LOG: Final = get_logger(__name__)

_MISSING: Final = ""

#: Shown in the Source column. A reader must be able to tell at a glance which
#: figures were computed from file sizes and which were observed on the wire.
#: Both are legitimate; conflating them is not.
_SOURCE_LABEL: Final = {
    "analytic": "computed",
    "wire": "measured",
    "both": "computed + measured",
}


def _marker_pattern(section: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?P<open><!--\s*BEGIN GENERATED:\s*{re.escape(section)}\s*-->\n)"
        rf".*?"
        rf"(?P<close>\n<!--\s*END GENERATED:\s*{re.escape(section)}\s*-->)",
        re.DOTALL,
    )


def _bytes_column(value: int) -> str:
    if value == 0:
        return _MISSING
    return f"{value / 1_000_000_000:.1f} GB"


def _seconds_column(value: float) -> str:
    if value == 0.0:
        return _MISSING
    if value < 90.0:  # noqa: PLR2004 - a readability threshold, not a constant
        return f"{value:.0f} s"
    if value < 5400.0:  # noqa: PLR2004 - a readability threshold, not a constant
        return f"{value / 60:.1f} min"
    return f"{value / 3600:.2f} h"


def _ratio_column(value: float | None) -> str:
    return _MISSING if value is None else f"{value:.2f}x"


def _percent_column(value: float | None) -> str:
    return _MISSING if value is None else f"{value * 100:.0f}%"


def render_read_path_table(records: list[RunRecord]) -> str:
    """Return the read-path table as GitHub-flavoured markdown.

    Bytes come first and wall time second, which is the order the project
    reports in and the order the columns are read in.

    The Source column is not decoration. Most pushdown rows are computed
    exactly from asset sizes, which is the better instrument for a claim that
    is meant to hold at any link speed. Read amplification is the exception:
    it can only be observed. A reader must be able to tell which is which.

    Args:
        records: Run records, oldest first. One row is emitted for each.

    Returns:
        A markdown table, without surrounding blank lines.
    """
    header = (
        "| Configuration | Bytes required | Saved vs naive | Source | "
        "Read amp | Wall time | GPU util |\n"
        "| --- | --- | --- | --- | --- | --- | --- |"
    )
    rows = []
    for record in records:
        columns = [
            record.label,
            _bytes_column(record.bytes_required),
            _percent_column(record.saved_fraction),
            _SOURCE_LABEL[record.accounting],
            _ratio_column(record.read_amplification),
            _seconds_column(record.wall_seconds),
            _percent_column(record.gpu_utilization),
        ]
        rows.append("| " + " | ".join(columns) + " |")
    return "\n".join([header, *rows])


def splice(text: str, section: str, replacement: str) -> str:
    """Replace one generated region of a document.

    Args:
        text: The full document.
        section: The section name used in the marker comments.
        replacement: Markdown to place between the markers.

    Returns:
        The document with that region replaced.

    Raises:
        ValueError: If the document has no marker pair for ``section``. A
            missing marker is a mistake worth failing on: silently appending
            would put a generated table somewhere nobody expects it.
    """
    pattern = _marker_pattern(section)
    if pattern.search(text) is None:
        msg = f"README has no BEGIN/END GENERATED markers for section {section!r}"
        raise ValueError(msg)
    return pattern.sub(lambda m: f"{m['open']}{replacement}{m['close']}", text)


def update_readme(readme: Path, records: list[RunRecord]) -> bool:
    """Rewrite the generated tables in ``README.md``.

    Args:
        readme: Path to ``README.md``.
        records: Run records to render.

    Returns:
        ``True`` if the file changed, ``False`` if there was nothing to write.
    """
    if not records:
        _LOG.info("no runs in results/, README left unchanged")
        return False

    original = readme.read_text(encoding="utf-8")
    updated = splice(original, "read-path", render_read_path_table(records))
    if updated == original:
        _LOG.info("README already up to date")
        return False

    readme.write_text(updated, encoding="utf-8")
    _LOG.info("wrote %d run(s) into %s", len(records), readme.name)
    return True


def main() -> int:
    """Regenerate the README tables. Entry point for ``just report``."""
    records = load_runs(get_settings().results_dir)
    update_readme(REPO_ROOT / "README.md", records)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via `just report`
    raise SystemExit(main())
