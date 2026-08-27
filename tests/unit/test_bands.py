"""Tests for band resolution.

The mapping here was verified against live CMR-STAC responses for both
collections. These tests pin it so a future edit cannot quietly reintroduce
the defect they were written for.
"""

from __future__ import annotations

import pytest

from burn_scar_recovery.bands import (
    HLSL30,
    HLSS30,
    MODEL_BANDS,
    QA_ASSET,
    Band,
    asset_name,
    asset_names,
    normalise_collection,
    qa_asset_name,
)


def test_the_model_takes_six_bands_in_order() -> None:
    assert MODEL_BANDS == (
        Band.BLUE,
        Band.GREEN,
        Band.RED,
        Band.NIR_NARROW,
        Band.SWIR1,
        Band.SWIR2,
    )


def test_sentinel_asset_names() -> None:
    assert asset_names(HLSS30) == ("B02", "B03", "B04", "B8A", "B11", "B12")


def test_landsat_asset_names() -> None:
    assert asset_names(HLSL30) == ("B02", "B03", "B04", "B05", "B06", "B07")


def test_the_two_collections_disagree_where_it_matters() -> None:
    """The defect this module exists for.

    A single tuple of asset keys was correct for Sentinel-2 and wrong for
    Landsat. Landsat carries no B8A and no B12 at all, so the request would
    have asked for assets that do not exist rather than failing a validation.
    """
    sentinel = set(asset_names(HLSS30))
    landsat = set(asset_names(HLSL30))
    assert "B8A" in sentinel
    assert "B12" in sentinel
    assert "B8A" not in landsat
    assert "B12" not in landsat


@pytest.mark.parametrize(
    ("band", "sentinel", "landsat"),
    [
        (Band.BLUE, "B02", "B02"),
        (Band.GREEN, "B03", "B03"),
        (Band.RED, "B04", "B04"),
        (Band.NIR_NARROW, "B8A", "B05"),
        (Band.SWIR1, "B11", "B06"),
        (Band.SWIR2, "B12", "B07"),
    ],
)
def test_each_band_resolves_per_collection(band: Band, sentinel: str, landsat: str) -> None:
    assert asset_name(HLSS30, band) == sentinel
    assert asset_name(HLSL30, band) == landsat


def test_order_is_preserved() -> None:
    """Channel order is the model's input order.

    Reordering the channels of a fine-tuned model produces confident nonsense
    rather than an error, so this is not cosmetic.
    """
    reversed_bands = tuple(reversed(MODEL_BANDS))
    assert asset_names(HLSS30, reversed_bands) == ("B12", "B11", "B8A", "B04", "B03", "B02")


# -- Collection identifiers --------------------------------------------------


@pytest.mark.parametrize(
    "spelling",
    ["HLSS30_2.0", "HLSS30", "S30", "hlss30_2.0", "HLS.S30.T11SLT.2018002T185421.v2.0"],
)
def test_sentinel_spellings_all_normalise(spelling: str) -> None:
    assert normalise_collection(spelling) == HLSS30


@pytest.mark.parametrize(
    "spelling",
    ["HLSL30_2.0", "HLSL30", "L30", "HLS.L30.T11SKU.2018003T182828.v2.0"],
)
def test_landsat_spellings_all_normalise(spelling: str) -> None:
    assert normalise_collection(spelling) == HLSL30


@pytest.mark.parametrize("bad", ["", "HLS", "MODIS", "HLSS31_2.0", "S2"])
def test_unknown_collections_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="not an HLS collection"):
        normalise_collection(bad)


def test_asset_name_rejects_an_unknown_collection() -> None:
    with pytest.raises(ValueError, match="not an HLS collection"):
        asset_name("MODIS", Band.RED)


# -- Fmask and the S3 twins --------------------------------------------------


def test_fmask_is_the_same_in_both_collections() -> None:
    assert qa_asset_name(HLSS30) == QA_ASSET
    assert qa_asset_name(HLSL30) == QA_ASSET


def test_direct_s3_assets_are_prefixed() -> None:
    """The in-region path. Only reachable from us-west-2."""
    assert asset_name(HLSS30, Band.RED, direct_s3=True) == "s3_B04"
    assert qa_asset_name(HLSL30, direct_s3=True) == "s3_Fmask"
    assert asset_names(HLSL30, direct_s3=True)[0] == "s3_B02"
