"""Count the bytes that actually cross the network.

Bytes are the primary metric of this project. Bytes saved by a pushdown is a
property of the pipeline and holds at any link speed; seconds is a property of
the machine the run happened on. Every row of the read-path table is a byte
count, so this module is the instrument the whole table rests on.

**Use one counter for every measurement.** Two counters, or one counter changed
halfway through, makes the rows incomparable and the table meaningless.

``rasterio`` does not report bytes over the wire. GDAL logs some of them, in
its debug log, when ``CPL_DEBUG`` is on: VSICURL emits a ``Downloading a-b``
line for chunks it pulls into its cache. ``rasterio`` forwards those lines to
the Python :mod:`logging` module, so a handler can read and sum them.

.. warning::

   **This does not yet count bulk transfers, and must not be used for a
   headline figure.** Measured against a public Copernicus DEM COG: a 256 px
   window and a 1024 px window both report 16384 bytes, which is the header
   chunk alone. The 1024 px read returns a full float32 block with a million
   distinct values, so the data plainly crossed the network without a
   ``Downloading`` line being emitted for it.

   Two further findings from the same validation:

   * GDAL's VSICURL cache is **process-global**. A second read of the same
     ranges reports zero bytes. Any benchmark that re-reads a tile in one
     process would record a saving that is pure cache. Phase 2 already lists
     ``VSI_CACHE`` as a knob to measure; this makes it a correctness concern
     and not only a tuning one. ``CPL_VSIL_CURL_NON_CACHED`` restores
     repeatability.
   * What this counter *does* measure reliably is the **request count** and
     the header fetch. Small reads are latency bound, so request count is a
     genuinely useful figure -- it is simply not a byte total.

   The measurement method is therefore an open decision. See
   ``docs/decisions.md``.

A second, analytic count is kept as a cross-check: the number of blocks touched
multiplied by the block size. It does not replace the primary count. It catches
a read that the pipeline drops without raising, where the primary count would
simply be low and look like a saving.

See ``docs/conventions.md``.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import TYPE_CHECKING, Final, Self

if TYPE_CHECKING:
    from types import TracebackType

#: GDAL's VSICURL debug lines name an inclusive HTTP byte range, for example
#: ``VSICURL: Downloading 0-16383 (https://example/x.tif)...``. The wording has
#: varied across GDAL versions, so the prefix is matched loosely and only the
#: range itself is required.
_RANGE_PATTERN: Final = re.compile(r"Downloading\s+(\d+)-(\d+)")

#: The logger rasterio forwards GDAL's CPL debug messages to.
_GDAL_LOGGER_NAME: Final = "rasterio._env"


def parse_downloaded_bytes(message: str) -> int | None:
    """Return the byte count named by one GDAL debug line.

    The range GDAL prints is inclusive at both ends, so ``0-16383`` is 16384
    bytes and not 16383. Getting that off by one would bias every figure in the
    project by one byte for each request, which at a million requests is a
    megabyte of invented saving.

    Args:
        message: One line of GDAL debug output.

    Returns:
        The number of bytes, or ``None`` if the line is not a range request.
    """
    match = _RANGE_PATTERN.search(message)
    if match is None:
        return None
    start, end = int(match[1]), int(match[2])
    if end < start:
        return None
    return end - start + 1


class _CountingHandler(logging.Handler):
    """A logging handler that sums VSICURL range requests."""

    def __init__(self) -> None:
        """Start at zero."""
        super().__init__(level=logging.DEBUG)
        self._lock = threading.Lock()
        self.bytes_read = 0
        self.requests = 0

    def emit(self, record: logging.LogRecord) -> None:
        counted = parse_downloaded_bytes(record.getMessage())
        if counted is None:
            return
        with self._lock:
            self.bytes_read += counted
            self.requests += 1


class ByteCounter:
    """Count bytes fetched over the network inside a block.

    Use it as a context manager around the reads to be measured::

        with ByteCounter() as counter:
            with rasterio.open(href) as src:
                src.read(1, window=window)
        record.bytes_read = counter.bytes_read

    The counter attaches to GDAL's debug log, so it observes every read made
    inside the block, including reads made by libraries this module knows
    nothing about.

    Note:
        ``CPL_DEBUG`` must be on for GDAL to emit the lines at all. Pass the
        reads through :func:`rasterio.Env` with ``CPL_DEBUG=True``, or use
        :meth:`gdal_env`.
    """

    def __init__(self) -> None:
        """Create a counter. Nothing is counted until the block is entered."""
        self._handler = _CountingHandler()
        self._logger = logging.getLogger(_GDAL_LOGGER_NAME)
        self._previous_level: int | None = None

    @property
    def bytes_read(self) -> int:
        """Total bytes fetched over the network inside the block."""
        return self._handler.bytes_read

    @property
    def requests(self) -> int:
        """Number of range requests issued inside the block.

        Small reads are latency bound, so this is the figure that explains a
        disappointing throughput number when the byte count looks fine.
        """
        return self._handler.requests

    @property
    def mean_request_bytes(self) -> float | None:
        """Mean size of a range request, or ``None`` if there were none."""
        if self._handler.requests == 0:
            return None
        return self._handler.bytes_read / self._handler.requests

    def __enter__(self) -> Self:
        """Attach to GDAL's debug log and start counting."""
        self._previous_level = self._logger.level
        self._logger.setLevel(logging.DEBUG)
        self._logger.addHandler(self._handler)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Detach, so later reads are not attributed to this run."""
        self._logger.removeHandler(self._handler)
        if self._previous_level is not None:
            self._logger.setLevel(self._previous_level)


def analytic_bytes(
    *,
    blocks_touched: int,
    block_width: int,
    block_height: int,
    bands: int,
    dtype_size: int,
) -> int:
    """Return the bytes a read *should* have cost, computed rather than observed.

    This is the cross-check, not the measurement. A COG is read a whole block at
    a time, so asking for one pixel costs a full block. Comparing this against
    :class:`ByteCounter` shows two different failures:

    * observed much higher than analytic: the windows are not aligned to the
      COG block grid, and each read is straddling block boundaries.
    * observed much lower than analytic: reads are being dropped somewhere, and
      the apparent saving is a bug rather than a pushdown.

    Args:
        blocks_touched: Number of COG internal blocks the windows overlap.
        block_width: Block width in pixels.
        block_height: Block height in pixels.
        bands: Number of bands read.
        dtype_size: Bytes for one sample, for example 2 for ``int16``.

    Returns:
        Uncompressed bytes. Real COGs are compressed, so this is an upper bound
        and the ratio to it is what carries the information, not the difference.
    """
    return blocks_touched * block_width * block_height * bands * dtype_size
