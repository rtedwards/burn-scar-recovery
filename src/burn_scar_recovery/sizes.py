"""Analytic byte accounting: what a configuration required, computed exactly.

Most rows of the read-path table are set arithmetic, not measurements. Which
tile-dates survived the predicate. Which six assets of the available ones were
projected. Which chips the Fmask probe kept. Each of those is a subset, and the
bytes it costs is the sum of the sizes of the files in it.

That number is **exact and machine-independent**, which is what the project
wants: "bytes saved by a pushdown is a property of the pipeline and holds at
any link speed", while seconds are a property of the machine. A figure that is
computed from file sizes is a better instrument for that claim than a figure
observed on one domestic connection.

What this module deliberately does **not** do is sub-file accounting. Once a
read goes inside a granule -- a window covering some COG blocks and not others
-- the cost depends on GDAL's fetch granularity, and the gap between blocks
needed and bytes pulled is the thing phase 2 measures rather than computes.
That row needs wire observation and per-tile ``TileByteCounts``, and both are
deferred to phase 2 where they belong.

**HEAD requests carry no body.** Asking for a size costs latency and a request,
not bytes, so building this index does not pollute the figure it produces.

See ``docs/conventions.md``.
"""

from __future__ import annotations

import concurrent.futures
import json
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Final

from burn_scar_recovery.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

_LOG: Final = get_logger(__name__)

#: Sizes are stable for a published archive, so the index is cached on disk and
#: an extent is only ever measured once.
SIZES_FILENAME: Final = "asset_sizes.json"

_DEFAULT_TIMEOUT_S: Final = 30.0
_DEFAULT_WORKERS: Final = 16


class AssetSizeError(RuntimeError):
    """Raised when an asset's size cannot be determined."""


def content_length(
    href: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> int:
    """Return the size of one asset in bytes, via an HTTP HEAD request.

    Args:
        href: The asset URL.
        headers: Extra request headers, for example an Earthdata bearer token.
        timeout: Seconds to wait.

    Returns:
        The value of the ``Content-Length`` response header.

    Raises:
        AssetSizeError: If the request fails or the header is absent.
    """
    request = urllib.request.Request(href, method="HEAD")  # noqa: S310 - https URLs from STAC
    for key, value in (headers or {}).items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.headers.get("Content-Length")
    except urllib.error.HTTPError as exc:
        # HTTPError *is* a response object and holds an open handle. Building
        # the index issues tens of thousands of HEAD requests, so leaking one
        # per failure would exhaust file descriptors long before it looked
        # like a resource problem.
        exc.close()
        msg = f"HEAD failed for {href}: HTTP {exc.code}"
        raise AssetSizeError(msg) from exc
    except (urllib.error.URLError, OSError) as exc:
        msg = f"HEAD failed for {href}: {exc}"
        raise AssetSizeError(msg) from exc

    if raw is None:
        msg = f"no Content-Length for {href}"
        raise AssetSizeError(msg)
    return int(raw)


class AssetSizeIndex:
    """A cached map from asset URL to size in bytes.

    An archive's file sizes do not change, so the index is written to disk and
    an extent is measured once rather than once per benchmark run.
    """

    def __init__(self, sizes: dict[str, int] | None = None) -> None:
        """Create an index, optionally seeded with known sizes."""
        self._sizes: dict[str, int] = dict(sizes or {})

    def __len__(self) -> int:
        """Number of assets with a known size."""
        return len(self._sizes)

    def __contains__(self, href: str) -> bool:
        """Whether this asset's size is already known."""
        return href in self._sizes

    def get(self, href: str) -> int | None:
        """Return a known size, or ``None`` if it has not been fetched."""
        return self._sizes.get(href)

    def total(self, hrefs: Iterable[str]) -> int:
        """Return the summed size of these assets.

        Args:
            hrefs: Asset URLs. Duplicates are counted once each time they
                appear, because reading the same file twice costs twice.

        Returns:
            Total bytes.

        Raises:
            AssetSizeError: If any href has no known size. Silently skipping an
                unknown would under-report, which is the direction that makes a
                pushdown look better than it is.
        """
        missing = [href for href in hrefs if href not in self._sizes]
        if missing:
            msg = f"{len(missing)} asset(s) have no known size, first: {missing[0]}"
            raise AssetSizeError(msg)
        return sum(self._sizes[href] for href in hrefs)

    def fetch(
        self,
        hrefs: Iterable[str],
        *,
        headers: Mapping[str, str] | None = None,
        max_workers: int = _DEFAULT_WORKERS,
        timeout: float = _DEFAULT_TIMEOUT_S,
    ) -> int:
        """Fetch sizes for any assets not already known.

        HEAD requests are latency bound and independent, so they are issued
        concurrently. They carry no response body, so this does not add to the
        byte figures it exists to produce.

        Args:
            hrefs: Asset URLs.
            headers: Extra request headers, for example a bearer token.
            max_workers: Concurrent HEAD requests.
            timeout: Seconds to wait for each.

        Returns:
            How many sizes were newly fetched.
        """
        wanted = sorted({href for href in hrefs if href not in self._sizes})
        if not wanted:
            return 0

        _LOG.info("fetching %d asset size(s) with %d workers", len(wanted), max_workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(content_length, href, headers=headers, timeout=timeout): href
                for href in wanted
            }
            for future in concurrent.futures.as_completed(futures):
                href = futures[future]
                try:
                    self._sizes[href] = future.result()
                except AssetSizeError:
                    _LOG.warning("no size for %s", href)
        return len(wanted)

    def to_dict(self) -> dict[str, int]:
        """Return a copy of the underlying map."""
        return dict(self._sizes)

    def save(self, results_dir: Path) -> Path:
        """Write the index to ``results/asset_sizes.json``."""
        results_dir.mkdir(parents=True, exist_ok=True)
        path = results_dir / SIZES_FILENAME
        path.write_text(json.dumps(self._sizes, indent=1, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, results_dir: Path) -> AssetSizeIndex:
        """Read the index from ``results/asset_sizes.json``, if it exists."""
        path = results_dir / SIZES_FILENAME
        if not path.exists():
            return cls()
        return cls(json.loads(path.read_text(encoding="utf-8")))


def saving(required: int, baseline: int) -> float | None:
    """Return the fraction of the naive read that a configuration avoided.

    Args:
        required: Bytes this configuration needs.
        baseline: Bytes the naive configuration over the same extent needs.

    Returns:
        A fraction between 0 and 1, or ``None`` if there is no baseline to
        compare against.
    """
    if baseline <= 0:
        return None
    return 1.0 - (required / baseline)
