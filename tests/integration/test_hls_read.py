"""The phase 0 access gate, as a test.

Earthdata Login works, CMR-STAC returns HLS hrefs, and a windowed read over
``/vsicurl/`` returns pixels without pulling the whole COG. That last one is
the measurement the entire project is built on, so it is worth having as a
test rather than as a notebook cell.

Skipped automatically without credentials or network; see conftest.py.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.network

# A tile in the southern California chaparral belt. Phase 1 resolves the real
# three from the STAC search; this one only has to exist.
BBOX = (-119.85, 34.35, -119.55, 34.55)  # Ventura / Santa Barbara
DATE_RANGE = "2018-01-01/2018-03-31"
COLLECTIONS = ["HLSL30_2.0", "HLSS30_2.0"]

CHIP = 224


_GDAL_KEYS = (
    "GDAL_DISABLE_READDIR_ON_OPEN",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS",
    "GDAL_HTTP_MULTIPLEX",
    "VSI_CACHE",
    "GDAL_HTTP_HEADERS",
    "GDAL_HTTP_COOKIEFILE",
    "GDAL_HTTP_COOKIEJAR",
)


@pytest.fixture(scope="module", autouse=True)
def _gdal_env(
    earthdata_credentials: dict[str, str],
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """The phase 2 vsicurl settings plus Earthdata auth, for this module.

    LP DAAC redirects protected assets through urs.earthdata.nasa.gov, so GDAL
    needs somewhere to keep the redirect cookie. Without the cookie jar the
    redirect lands on an HTML login page and GDAL reports the far less helpful
    "not recognized as being in a supported file format".
    """
    previous = {k: os.environ.get(k) for k in _GDAL_KEYS}

    cookies = tmp_path_factory.mktemp("gdal") / "cookies.txt"
    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
        "GDAL_HTTP_MULTIPLEX": "YES",
        "VSI_CACHE": "TRUE",
        "GDAL_HTTP_COOKIEFILE": str(cookies),
        "GDAL_HTTP_COOKIEJAR": str(cookies),
    }
    token = earthdata_credentials.get("EARTHDATA_TOKEN")
    if token:
        env["GDAL_HTTP_HEADERS"] = f"Authorization: Bearer {token}"
    # Without a token GDAL falls back to ~/.netrc for urs.earthdata.nasa.gov,
    # which conftest.py has already confirmed exists.

    os.environ.update(env)
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="module")
def hls_item() -> Any:
    """One HLS scene over the area of interest, via CMR-STAC."""
    pystac_client = pytest.importorskip("pystac_client")

    from burn_scar_recovery import get_settings

    client = pystac_client.Client.open(get_settings().cmr_stac_url)
    search = client.search(
        collections=COLLECTIONS,
        bbox=BBOX,
        datetime=DATE_RANGE,
        max_items=1,
    )
    items = list(search.items())
    if not items:
        pytest.skip(f"CMR-STAC returned no items for {BBOX} over {DATE_RANGE}")
    return items[0]


def test_stac_search_returns_band_hrefs(hls_item: Any) -> None:
    """Phase 1: the manifest needs IDs, band hrefs, footprints and CRS."""
    assert hls_item.id
    assert hls_item.geometry is not None
    # Fmask is the cloud probe band; without it there is no two-phase read.
    assert "Fmask" in hls_item.assets
    href = hls_item.assets["Fmask"].href
    assert href.endswith((".tif", ".TIF"))


@pytest.mark.slow
def test_windowed_vsicurl_read_returns_one_chip(hls_item: Any) -> None:
    """Phase 2: read a 224x224 window over /vsicurl/, not the whole COG."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.windows import Window

    href = hls_item.assets["Fmask"].href
    url = href if href.startswith("/vsicurl/") else f"/vsicurl/{href}"

    try:
        src_cm = rasterio.open(url)
    except rasterio.errors.RasterioIOError as exc:
        # The overwhelmingly likely cause is auth, not a corrupt COG: LP DAAC
        # hands back an HTML login page, which GDAL cannot identify.
        pytest.fail(
            f"could not open {url}: {exc}\n\n"
            "This is almost always Earthdata authorisation rather than a bad "
            "file. Check that:\n"
            "  1. the token/password is current (tokens expire), and\n"
            "  2. the account has authorised the 'LP DAAC Data Pool' "
            "application at https://urs.earthdata.nasa.gov/profile.\n"
            "See .env.example.",
        )

    with src_cm as src:
        assert src.count == 1
        # HLS is on the Sentinel-2 MGRS grid: 3660x3660 at 30m.
        assert src.width >= CHIP
        assert src.height >= CHIP
        # A COG, so the read below can be tile-aligned rather than striped.
        assert src.profile.get("tiled", False), "expected an internal-tiled COG"

        window = Window(0, 0, CHIP, CHIP)
        data = src.read(1, window=window)

    assert data.shape == (CHIP, CHIP)
