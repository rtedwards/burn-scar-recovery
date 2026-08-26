"""Pytest configuration.

This project has tests that cost real money and real minutes: reads against
HLS in us-west-2, and forward passes on the GPU node. They are marked and
deselected by default. `just test` runs the cheap set; `just test-all` runs
everything.
"""

from __future__ import annotations

from typing import Final

import pytest

# marker -> (flag, reason shown when skipped)
OPT_IN_MARKERS: Final[dict[str, tuple[str, str]]] = {
    "slow": ("--run-slow", "needs --run-slow (or --run-all)"),
    "network": ("--run-network", "needs --run-network (or --run-all): hits S3/Earthdata"),
    "gpu": ("--run-gpu", "needs --run-gpu (or --run-all): requires a CUDA device"),
}


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the opt-in flags, one per expensive marker."""
    group = parser.getgroup("burn-scar-recovery")
    for marker, (flag, reason) in OPT_IN_MARKERS.items():
        group.addoption(
            flag,
            action="store_true",
            default=False,
            help=f"run tests marked `{marker}` ({reason})",
        )
    group.addoption(
        "--run-all",
        action="store_true",
        default=False,
        help="run every opt-in marker: " + ", ".join(OPT_IN_MARKERS),
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip opt-in markers unless their flag (or --run-all) was passed."""
    run_all = bool(config.getoption("--run-all"))
    enabled = {
        marker
        for marker, (flag, _) in OPT_IN_MARKERS.items()
        if run_all or bool(config.getoption(flag))
    }
    disabled = set(OPT_IN_MARKERS) - enabled
    if not disabled:
        return

    for item in items:
        item_markers: set[str] = {m.name for m in item.iter_markers()}
        for marker in sorted(item_markers & disabled):
            item.add_marker(pytest.mark.skip(reason=OPT_IN_MARKERS[marker][1]))
            break
