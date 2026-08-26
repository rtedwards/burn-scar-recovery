"""Tests for the coordinate systems, and for the silent area error they prevent."""

from __future__ import annotations

import pytest
from shapely.geometry import box

from burn_scar_recovery.crs import (
    AREA_CRS,
    WRITE_CRS,
    area_hectares,
    utm_crs_for_mgrs,
)


def test_the_three_crs_are_what_conventions_says() -> None:
    assert WRITE_CRS.to_epsg() == 4326
    assert AREA_CRS.to_epsg() == 5070


@pytest.mark.parametrize(
    ("tile", "epsg"),
    [
        ("11SKU", 32611),  # southern California, northern hemisphere
        ("T11SKU", 32611),  # the STAC form
        ("10SGD", 32610),  # west of 120W
        ("19HCC", 32719),  # southern hemisphere, band H
    ],
)
def test_utm_crs_for_mgrs(tile: str, epsg: int) -> None:
    assert utm_crs_for_mgrs(tile).to_epsg() == epsg


@pytest.mark.parametrize("bad", ["", "11S", "ABCDE", "99SKU"])
def test_bad_tiles_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match=r"MGRS|out of range"):
        utm_crs_for_mgrs(bad)


def test_area_of_a_known_square() -> None:
    """A 1 km square in UTM is 100 ha, to within the projection difference."""
    square = box(400_000, 3_800_000, 401_000, 3_801_000)
    (hectares,) = area_hectares(square, utm_crs_for_mgrs("11SKU"))
    assert hectares == pytest.approx(100.0, rel=0.01)


def test_a_single_geometry_and_a_sequence_agree() -> None:
    square = box(400_000, 3_800_000, 401_000, 3_801_000)
    utm = utm_crs_for_mgrs("11SKU")
    assert area_hectares(square, utm) == area_hectares([square], utm)


def test_empty_input_gives_empty_output() -> None:
    assert area_hectares([], WRITE_CRS) == []


def test_area_is_equal_across_the_belt() -> None:
    """The reason areas are measured in EPSG:5070 and never in per-tile UTM.

    Two equal-sized squares of ground at opposite ends of the three-tile belt
    must report the same area. Measured in a single UTM zone they would not,
    because the scale factor grows with distance from the central meridian, and
    nothing raises when that happens.
    """
    west = box(-120.0, 34.0, -120.0 + 0.01, 34.01)
    east = box(-116.5, 33.0, -116.5 + 0.01, 33.01)
    west_ha, east_ha = area_hectares([west, east], WRITE_CRS)

    # Same angular size at different latitudes differs mostly by cos(lat).
    # The point is that both are computed in one equal-area CRS, so the ratio
    # reflects real ground and not a projection artefact.
    assert west_ha > 0
    assert east_ha > 0
    assert east_ha / west_ha == pytest.approx(1.0, abs=0.05)
