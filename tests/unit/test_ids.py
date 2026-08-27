"""Tests for chip identifiers and the chip grid they index into."""

from __future__ import annotations

from datetime import date

import pytest

from burn_scar_recovery.ids import ChipKey, chip_id, chip_origins, parse_chip_id

#: An HLS tile is 3660 x 3660 pixels at 30 m.
HLS_TILE_PX = 3660


def test_chip_id_is_canonical() -> None:
    assert chip_id("11SKU", date(2018, 1, 2), 7, 12) == "11SKU/2018-01-02/r0007c0012"


def test_leading_t_is_stripped() -> None:
    """STAC ids carry a T prefix; the identifier must not depend on which form."""
    assert chip_id("T11SKU", "2018-01-02", 0, 0) == chip_id("11SKU", "2018-01-02", 0, 0)


def test_string_and_date_agree() -> None:
    assert chip_id("11SKU", date(2018, 1, 2), 1, 1) == chip_id("11SKU", "2018-01-02", 1, 1)


def test_identifier_is_a_pure_function_of_its_inputs() -> None:
    """No counter, no insertion order: two calls must agree."""
    assert chip_id("11SKU", "2020-06-01", 3, 4) == chip_id("11SKU", "2020-06-01", 3, 4)


def test_round_trip() -> None:
    identifier = chip_id("11SKU", "2018-01-02", 7, 12)
    assert parse_chip_id(identifier) == ChipKey("11SKU", "2018-01-02", 7, 12)


def test_zero_padding_keeps_lexical_and_numeric_order_together() -> None:
    ordered = [chip_id("11SKU", "2018-01-02", 0, col) for col in (2, 10)]
    assert sorted(ordered) == ordered


@pytest.mark.parametrize("bad", ["", "11SKU/2018-01-02", "nope/2018-01-02/r0000c0000"])
def test_bad_identifiers_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="not a chip identifier"):
        parse_chip_id(bad)


def test_negative_indices_are_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        chip_id("11SKU", "2018-01-02", -1, 0)


# -- The grid ----------------------------------------------------------------


def test_origins_start_at_zero_and_step_by_the_stride() -> None:
    origins = chip_origins(1000, 224, 192)
    assert origins[0] == 0
    assert origins[1] == 192


def test_final_chip_is_clamped_so_the_far_edge_is_covered() -> None:
    """A plain range leaves a remainder unread at the right and bottom edges.

    3660 px with 224/192 reaches only 3488 on the regular grid, leaving 172 px
    of ground never inferred. The last origin is therefore clamped to the edge.
    """
    origins = chip_origins(HLS_TILE_PX, 224, 192)
    assert origins[-1] == HLS_TILE_PX - 224
    assert origins[-1] + 224 == HLS_TILE_PX


def test_no_clamped_duplicate_when_the_grid_already_lands_on_the_edge() -> None:
    origins = chip_origins(416, 224, 192)
    assert origins == [0, 192]


def test_grid_is_deterministic() -> None:
    assert chip_origins(HLS_TILE_PX, 224, 192) == chip_origins(HLS_TILE_PX, 224, 192)


def test_raster_smaller_than_a_chip_yields_nothing() -> None:
    assert chip_origins(100, 224, 192) == []


def test_stride_above_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="leave gaps"):
        chip_origins(1000, 224, 256)


@pytest.mark.parametrize(("size", "stride"), [(0, 192), (224, 0), (-1, 192)])
def test_non_positive_geometry_is_rejected(size: int, stride: int) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        chip_origins(1000, size, stride)
