"""Check the band mapping against the live archive.

The mapping in :mod:`burn_scar_recovery.bands` was read off real CMR-STAC
responses. This asserts it still holds, so that a change in the archive -- or
an edit to the table -- fails here rather than at a read.

This is the test that would have caught the original defect: a single tuple of
asset keys resolved against HLSL30 asks for B8A and B12, which that collection
does not have.

Search is public, so no Earthdata login is needed.
"""

from __future__ import annotations

import json
import urllib.request
from typing import NamedTuple

import pytest

from burn_scar_recovery.bands import HLSL30, HLSS30, asset_names, qa_asset_name

pytestmark = [pytest.mark.network, pytest.mark.no_credentials]

_SEARCH = "https://cmr.earthdata.nasa.gov/stac/LPCLOUD/search"
# Ventura, inside the area of interest, early in the observation window.
_BBOX = "-119.5,34.0,-119.0,34.5"
_DATES = "2018-01-01T00:00:00Z/2018-02-28T23:59:59Z"


class _Granule(NamedTuple):
    """The parts of a STAC item these tests care about."""

    identifier: str
    assets: frozenset[str]


def _one_granule(collection: str) -> _Granule:
    url = f"{_SEARCH}?collections={collection}&bbox={_BBOX}&datetime={_DATES}&limit=1"
    try:
        with urllib.request.urlopen(url, timeout=90) as response:  # noqa: S310
            payload = json.load(response)
    except OSError as exc:  # pragma: no cover - network shape
        pytest.skip(f"cannot reach CMR-STAC: {exc}")
    features = payload.get("features") or []
    if not features:
        pytest.skip(f"no {collection} granules for the probe extent")
    item = features[0]
    return _Granule(identifier=str(item["id"]), assets=frozenset(item["assets"]))


@pytest.mark.parametrize("collection", [HLSS30, HLSL30])
def test_every_resolved_asset_exists_in_a_real_granule(collection: str) -> None:
    granule = _one_granule(collection)

    missing = [name for name in asset_names(collection) if name not in granule.assets]
    assert not missing, f"{collection} granule {granule.identifier} lacks {missing}"
    assert qa_asset_name(collection) in granule.assets


def test_landsat_really_does_lack_the_sentinel_keys() -> None:
    """Pins why one tuple of asset keys cannot serve both collections."""
    available = _one_granule(HLSL30).assets
    assert "B8A" not in available
    assert "B12" not in available


@pytest.mark.parametrize("collection", [HLSS30, HLSL30])
def test_the_direct_s3_twins_exist(collection: str) -> None:
    """The in-region path the bottleneck table estimates is addressable."""
    available = _one_granule(collection).assets
    for name in asset_names(collection, direct_s3=True):
        assert name in available
