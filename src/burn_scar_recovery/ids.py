"""Chip identifiers, derived rather than assigned.

A chip identifier must be reproducible. Phase 9 joins scars across dates on it,
and phase 10 restarts a killed job and skips finished work by it. If the same
chip could get two identifiers on two runs, neither of those works.

So an identifier is a pure function of ``(tile, date, row, col)`` and nothing
else. No counter, no UUID, no insertion order. Two machines that never talk to
each other produce the same identifier for the same ground.

See ``docs/conventions.md``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    import datetime as dt

_ID_PATTERN: Final = re.compile(
    r"^(?P<tile>[0-9]{2}[A-Z]{3})/(?P<date>\d{4}-\d{2}-\d{2})/r(?P<row>\d{4})c(?P<col>\d{4})$"
)


class ChipKey(NamedTuple):
    """The four fields a chip identifier is built from."""

    tile: str
    date: str
    row: int
    col: int


def chip_id(tile: str, date: dt.date | str, row: int, col: int) -> str:
    """Return the canonical identifier for one chip.

    The form is ``<tile>/<iso-date>/r<row>c<col>``, for example
    ``11SKU/2018-01-02/r0007c0012``.

    A readable composite is deliberate. A hash would be shorter and would also
    be undebuggable: when a chip looks wrong, the identifier should say which
    ground it covers without a lookup.

    Args:
        tile: MGRS tile identifier, with or without a leading ``T``.
        date: Observation date.
        row: Chip row index within the tile grid. See :func:`chip_origins`.
        col: Chip column index within the tile grid.

    Returns:
        The canonical chip identifier.

    Raises:
        ValueError: If ``row`` or ``col`` is negative.
    """
    if row < 0 or col < 0:
        msg = f"chip row and col must be non-negative, got r={row} c={col}"
        raise ValueError(msg)

    tile_clean = tile.removeprefix("T").upper()
    date_text = date if isinstance(date, str) else date.isoformat()
    return f"{tile_clean}/{date_text}/r{row:04d}c{col:04d}"


def parse_chip_id(identifier: str) -> ChipKey:
    """Return the fields a chip identifier was built from.

    Args:
        identifier: A string produced by :func:`chip_id`.

    Returns:
        The tile, date, row and column.

    Raises:
        ValueError: If ``identifier`` is not in the canonical form.
    """
    match = _ID_PATTERN.match(identifier)
    if match is None:
        msg = f"not a chip identifier: {identifier!r}"
        raise ValueError(msg)
    return ChipKey(
        tile=match["tile"],
        date=match["date"],
        row=int(match["row"]),
        col=int(match["col"]),
    )


def chip_origins(extent: int, size: int, stride: int) -> list[int]:
    """Return the pixel origins of chips along one axis.

    The row and column indices in a chip identifier are positions in this list,
    which is what makes them derived. Given the same extent, size and stride,
    the list is always the same.

    A regular ``range`` leaves a remainder at the far edge uncovered: an HLS
    tile is 3660 px, and 224/192 reaches only 3488. The final chip is therefore
    clamped to the edge, which overlaps its neighbour by more than the stride.
    That is correct for coverage and it is why the origins are enumerated here
    once rather than recomputed at each call site.

    Args:
        extent: Size of the raster along this axis, in pixels.
        size: Chip size in pixels.
        stride: Distance between consecutive chip origins, in pixels.

    Returns:
        Ascending pixel origins. Empty if the raster is smaller than one chip.

    Raises:
        ValueError: If ``size`` or ``stride`` is not positive, or ``stride``
            exceeds ``size``, which would leave gaps between chips.
    """
    if size <= 0 or stride <= 0:
        msg = f"size and stride must be positive, got size={size} stride={stride}"
        raise ValueError(msg)
    if stride > size:
        msg = f"stride {stride} exceeds size {size}, which would leave gaps"
        raise ValueError(msg)
    if extent < size:
        return []

    origins = list(range(0, extent - size + 1, stride))
    last = extent - size
    if origins[-1] != last:
        origins.append(last)
    return origins
