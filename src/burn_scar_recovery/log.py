"""Logging setup.

The project is fundamentally about recording measurements, so log records
carry a timestamp and the logger name and are safe to interleave across Ray
actors on two nodes.
"""

from __future__ import annotations

import logging
import os
import sys

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_configured = False


def configure_logging(level: int | str | None = None, *, force: bool = False) -> None:
    """Install a stderr handler on the root logger.

    Safe to call from a Ray worker: repeated calls are a no-op unless ``force``
    is set, so actors do not stack duplicate handlers.

    Args:
        level: Log level. Defaults to ``$BSR_LOG_LEVEL``, then ``INFO``.
        force: Reconfigure even if this process has already been configured.
    """
    global _configured  # noqa: PLW0603 - process-wide, by design
    if _configured and not force:
        return

    resolved = level if level is not None else os.environ.get("BSR_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=resolved,
        format=_FORMAT,
        datefmt=_DATE_FORMAT,
        stream=sys.stderr,
        force=True,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger, configuring the root logger on first use."""
    configure_logging()
    return logging.getLogger(name)
