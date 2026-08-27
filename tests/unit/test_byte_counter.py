"""Tests for the byte counter.

The parser is tested against GDAL debug lines directly, so these stay hermetic.
The counter is validated against a real read over the network in
``tests/integration/``.
"""

from __future__ import annotations

import logging

import pytest

from burn_scar_recovery.byte_counter import (
    ByteCounter,
    analytic_bytes,
    parse_downloaded_bytes,
)

_GDAL_LOGGER = "rasterio._env"


def _emit(message: str) -> None:
    logging.getLogger(_GDAL_LOGGER).debug(message)


def test_range_is_inclusive_at_both_ends() -> None:
    """0-16383 is 16384 bytes, not 16383.

    An off-by-one here biases every figure in the project by one byte for each
    request. At a million requests that is a megabyte of invented saving.
    """
    assert parse_downloaded_bytes("VSICURL: Downloading 0-16383 (https://x/y.tif)...") == 16384


def test_a_later_range_is_measured_by_its_span() -> None:
    assert parse_downloaded_bytes("VSICURL: Downloading 16384-32767 (https://x)") == 16384


def test_single_byte_range() -> None:
    assert parse_downloaded_bytes("Downloading 5-5") == 1


@pytest.mark.parametrize(
    "line",
    [
        "",
        "VSICURL: GetFileSize(https://x/y.tif)=12345",
        "HTTP: Establishing connection",
        "Downloading a-b",
    ],
)
def test_lines_that_are_not_range_requests_are_ignored(line: str) -> None:
    assert parse_downloaded_bytes(line) is None


def test_a_reversed_range_is_ignored_rather_than_counted_negative() -> None:
    assert parse_downloaded_bytes("Downloading 100-1") is None


# -- The counter -------------------------------------------------------------


def test_counter_sums_ranges_and_counts_requests() -> None:
    with ByteCounter() as counter:
        _emit("VSICURL: Downloading 0-16383 (https://x)")
        _emit("VSICURL: Downloading 16384-32767 (https://x)")
    assert counter.bytes_read == 32768
    assert counter.requests == 2
    assert counter.mean_request_bytes == pytest.approx(16384.0)


def test_counter_ignores_unrelated_debug_output() -> None:
    with ByteCounter() as counter:
        _emit("VSICURL: GetFileSize(https://x)=999999")
        _emit("HTTP: reusing connection")
    assert counter.bytes_read == 0
    assert counter.requests == 0


def test_mean_is_none_with_no_requests() -> None:
    with ByteCounter() as counter:
        pass
    assert counter.mean_request_bytes is None


def test_counting_stops_when_the_block_exits() -> None:
    """A counter that kept counting would attribute later reads to this run."""
    with ByteCounter() as counter:
        _emit("Downloading 0-9")
    _emit("Downloading 0-999999")
    assert counter.bytes_read == 10


def test_the_gdal_logger_level_is_restored() -> None:
    logger = logging.getLogger(_GDAL_LOGGER)
    logger.setLevel(logging.WARNING)
    with ByteCounter():
        assert logger.level == logging.DEBUG
    assert logger.level == logging.WARNING


def test_two_counters_nest_without_stealing_from_each_other() -> None:
    with ByteCounter() as outer:
        _emit("Downloading 0-9")
        with ByteCounter() as inner:
            _emit("Downloading 0-99")
    assert inner.bytes_read == 100
    # The outer counter sees every read inside its own block, including the
    # ones the inner counter also saw.
    assert outer.bytes_read == 110


# -- The analytic cross-check ------------------------------------------------


def test_analytic_bytes_multiplies_out() -> None:
    assert (
        analytic_bytes(
            blocks_touched=4,
            block_width=512,
            block_height=512,
            bands=6,
            dtype_size=2,
        )
        == 4 * 512 * 512 * 6 * 2
    )


def test_one_fmask_band_is_a_sixth_of_six_bands() -> None:
    """The two-phase read: the probe is 1 band of 6, so about 17% of the bytes."""
    common = {"blocks_touched": 9, "block_width": 256, "block_height": 256, "dtype_size": 2}
    probe = analytic_bytes(bands=1, **common)
    full = analytic_bytes(bands=6, **common)
    assert probe / full == pytest.approx(1 / 6)
