"""Validate the byte counter against a real read over the network.

``docs/conventions.md`` requires this: the counter is the instrument every row
of the read-path table rests on, and an instrument tested only against
synthetic log lines has not been validated at all.

**This validation failed, and these tests record what is actually true rather
than what was intended.** The log-based counter sees the header fetch and the
request count. It does not see bulk data transfer. See the warning in
:mod:`burn_scar_recovery.byte_counter` and the open decision in
``docs/decisions.md``.

The target is the Copernicus DEM on AWS Open Data. It needs no Earthdata
login, so the project's primary instrument can be checked on any machine with
a network connection rather than waiting on credentials. The tile is
N34/W119 -- Ventura, inside the area of interest, and a dataset phase 9 needs
anyway for slope and aspect.
"""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio import Env as GdalEnv
from rasterio.errors import RasterioIOError
from rasterio.windows import Window

from burn_scar_recovery.byte_counter import ByteCounter

pytestmark = [pytest.mark.network, pytest.mark.no_credentials]

#: Copernicus DEM 30 m, one degree tile covering Ventura. Public, no login.
DEM_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_N34_00_W119_00_DEM/"
    "Copernicus_DSM_COG_10_N34_00_W119_00_DEM.tif"
)
DEM_HREF = f"/vsicurl/{DEM_URL}"

#: One VSICURL chunk. GDAL fetches the header in a single 16 KiB range.
HEADER_CHUNK_BYTES = 16_384


@pytest.fixture
def dem_href() -> str:
    """Return the DEM path, skipping if the public bucket cannot be reached.

    The probe is deliberately non-caching. A plain open would pull the header
    into GDAL's process-global VSICURL cache, and
    ``test_the_vsicurl_cache_is_process_global`` would then see a cold read
    that is already warm.
    """
    try:
        with (
            GdalEnv(CPL_DEBUG=True, CPL_VSIL_CURL_NON_CACHED=DEM_HREF),
            rasterio.open(DEM_HREF),
        ):
            pass
    except (RasterioIOError, OSError) as exc:  # pragma: no cover - network shape
        pytest.skip(f"cannot open the public Copernicus DEM: {exc}")
    return DEM_HREF


def _read(window: Window, href: str, *, cached: bool = False) -> tuple[ByteCounter, np.ndarray]:
    options: dict[str, object] = {"CPL_DEBUG": True, "GDAL_CACHEMAX": 0}
    if not cached:
        options["CPL_VSIL_CURL_NON_CACHED"] = href
    with ByteCounter() as counter, GdalEnv(**options), rasterio.open(href) as src:
        data = src.read(1, window=window)
    return counter, data


def test_counter_observes_something_on_a_real_read(dem_href: str) -> None:
    """The counter must not be silently inert.

    A counter that always reported zero is the worst failure available here:
    every pushdown would look like a total saving and the table would read as
    a triumph.
    """
    counter, _ = _read(Window(0, 0, 256, 256), dem_href)
    assert counter.bytes_read > 0
    assert counter.requests > 0


def test_the_read_returns_real_pixels(dem_href: str) -> None:
    """Guards the tests below: they mean nothing if no data came back."""
    _, data = _read(Window(1800, 1800, 1024, 1024), dem_href)
    assert data.shape == (1024, 1024)
    # Ventura county terrain, in metres. Not a constant fill, not nodata.
    assert 0 < float(np.nanmin(data)) < float(np.nanmax(data)) < 4000
    assert len(np.unique(data)) > 1000


def test_the_vsicurl_cache_is_process_global(dem_href: str) -> None:
    """A second read of the same ranges costs nothing, which is a trap.

    Any benchmark that re-reads a tile inside one process records a saving
    that is entirely cache. This is why every measured run must either use a
    fresh process or disable the cache explicitly.
    """
    first, _ = _read(Window(0, 0, 256, 256), dem_href, cached=True)
    second, _ = _read(Window(0, 0, 256, 256), dem_href, cached=True)
    assert first.bytes_read > 0
    assert second.bytes_read == 0, (
        "the VSICURL cache appears to have stopped being process-global; "
        "if so the workaround in byte_counter can be revisited"
    )


def test_disabling_the_cache_restores_repeatability(dem_href: str) -> None:
    """CPL_VSIL_CURL_NON_CACHED makes repeated reads cost the same again."""
    counts = [_read(Window(0, 0, 256, 256), dem_href)[0].bytes_read for _ in range(3)]
    assert len(set(counts)) == 1, f"repeated reads disagreed: {counts}"
    assert counts[0] > 0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN GAP: the log-based counter misses bulk data transfer. GDAL emits "
        "'Downloading a-b' only for chunks it pulls into its cache, so a 1024 px "
        "read of a full float32 block reports the same 16 KiB header fetch as a "
        "256 px read. Fixing this needs a different measurement method -- see the "
        "open decision in docs/decisions.md. Strict, so this fails loudly if a "
        "GDAL upgrade or a method change makes it start working."
    ),
)
def test_a_bigger_window_costs_more_bytes(dem_href: str) -> None:
    """The property a byte counter must have, and currently does not."""
    small, _ = _read(Window(0, 0, 256, 256), dem_href)
    large, _ = _read(Window(1800, 1800, 1024, 1024), dem_href)
    assert large.bytes_read > small.bytes_read


def test_what_the_counter_does_measure_is_the_header_fetch(dem_href: str) -> None:
    """Pin the current behaviour, so a change in it is visible."""
    counter, _ = _read(Window(0, 0, 256, 256), dem_href)
    assert counter.bytes_read == HEADER_CHUNK_BYTES
    assert counter.requests == 1
