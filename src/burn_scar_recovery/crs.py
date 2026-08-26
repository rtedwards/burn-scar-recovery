"""Coordinate reference systems, and the one rule that matters.

Three coordinate systems, each with one job:

* **Read** in the native UTM of the MGRS tile. No reprojection on the read
  path, which is the path the project measures.
* **Write** GeoParquet in EPSG:4326, which the specification expects.
* **Measure area** in EPSG:5070, CONUS Albers, which is equal area.

Scar area against time is the headline result of the project. A UTM area is
correct inside one zone and wrong across the three-tile belt, and the error is
silent: nothing raises, the numbers are simply off. This module exists so that
the correct thing is the easy thing -- call :func:`area_hectares` and the
reprojection cannot be forgotten.

See ``docs/conventions.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import geopandas as gpd
from pyproj import CRS
from shapely.geometry.base import BaseGeometry

if TYPE_CHECKING:
    from collections.abc import Sequence

#: GeoParquet output. The GeoParquet 1.1 specification expects lon/lat.
WRITE_CRS: Final = CRS.from_epsg(4326)

#: Every area figure. CONUS Albers is equal area, so a hectare in the San Diego
#: backcountry is a hectare in Santa Barbara. UTM does not promise that.
AREA_CRS: Final = CRS.from_epsg(5070)

#: Web mercator. Present only so that a display layer can name it explicitly.
#: Never compute an area in it. See ``docs/visualization.md``.
DISPLAY_CRS: Final = CRS.from_epsg(3857)

_SQUARE_METRES_PER_HECTARE: Final = 10_000.0


def utm_crs_for_mgrs(tile: str) -> CRS:
    """Return the native UTM CRS of an MGRS tile.

    Args:
        tile: An MGRS tile identifier such as ``11SKU``, with or without a
            leading ``T``.

    Returns:
        The UTM CRS the HLS product for that tile is stored in.

    Raises:
        ValueError: If ``tile`` is not a recognisable MGRS tile identifier.
    """
    cleaned = tile.removeprefix("T").upper()
    expected_length = 5
    if len(cleaned) != expected_length or not cleaned[:2].isdigit():
        msg = f"not an MGRS tile identifier: {tile!r}"
        raise ValueError(msg)

    zone = int(cleaned[:2])
    if not 1 <= zone <= 60:  # noqa: PLR2004 - the UTM zone range is a fact
        msg = f"UTM zone out of range in {tile!r}: {zone}"
        raise ValueError(msg)

    # MGRS latitude bands run C..X south to north. N and above is northern.
    band = cleaned[2]
    northern = band >= "N"
    epsg = (32600 if northern else 32700) + zone
    return CRS.from_epsg(epsg)


def area_hectares(
    geometry: BaseGeometry | Sequence[BaseGeometry],
    source_crs: CRS | str | int,
) -> list[float]:
    """Return the area of each geometry in hectares, measured in EPSG:5070.

    The reprojection happens here so that no caller has to remember it. Pass
    geometries in whatever CRS they are already in and say which one that is.

    Args:
        geometry: One geometry, or a sequence of them.
        source_crs: The CRS ``geometry`` is currently expressed in.

    Returns:
        One area in hectares for each input geometry, in input order.
    """
    geometries = [geometry] if isinstance(geometry, BaseGeometry) else list(geometry)
    if not geometries:
        return []

    series = gpd.GeoSeries(geometries, crs=source_crs).to_crs(AREA_CRS)
    return [float(value) / _SQUARE_METRES_PER_HECTARE for value in series.area]
