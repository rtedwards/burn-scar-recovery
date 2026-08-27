"""Validate analytic byte accounting against a real published asset.

Analytic accounting is only exact if the sizes it sums are real. This checks
the one step that touches the network -- the HEAD request -- against a public
Copernicus DEM COG that needs no Earthdata login.
"""

from __future__ import annotations

import pytest

from burn_scar_recovery.sizes import AssetSizeError, AssetSizeIndex, content_length

pytestmark = [pytest.mark.network, pytest.mark.no_credentials]

DEM_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_N34_00_W119_00_DEM/"
    "Copernicus_DSM_COG_10_N34_00_W119_00_DEM.tif"
)

#: Observed via HEAD. A published archive does not resize its files, so a
#: change here means the asset was republished and the cached index is stale.
KNOWN_BYTES = 42_718_799


def test_head_returns_the_real_size() -> None:
    assert content_length(DEM_URL) == KNOWN_BYTES


def test_a_missing_asset_raises_rather_than_returning_zero() -> None:
    """Zero would silently under-report and flatter every pushdown."""
    with pytest.raises(AssetSizeError):
        content_length(DEM_URL.replace("N34", "N99"))


def test_the_index_fetches_and_then_caches() -> None:
    index = AssetSizeIndex()
    assert index.fetch([DEM_URL]) == 1
    assert index.total([DEM_URL]) == KNOWN_BYTES
    # Second call must not go back to the network.
    assert index.fetch([DEM_URL]) == 0
