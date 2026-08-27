"""Band names, which belong to the collection and not to the experiment.

The model wants six bands: blue, green, red, narrow NIR, SWIR 1 and SWIR 2.
That list is a property of the model and it never changes.

**The asset names for those six differ between the two HLS collections**, and
they do not merely differ in spelling. Landsat has no ``B12`` and no ``B8A``
at all:

===========  ==================  ==================
Band         HLSS30 (Sentinel-2) HLSL30 (Landsat)
===========  ==================  ==================
blue         B02                 B02
green        B03                 B03
red          B04                 B04
narrow NIR   B8A                 B05
SWIR 1       B11                 B06
SWIR 2       B12                 B07
===========  ==================  ==================

So a configuration must hold the *semantic* list and resolve it against the
collection at read time. A single tuple of asset names cannot be correct for
both, and asking HLSL30 for ``B12`` requests an asset that does not exist.

Verified against the live CMR-STAC responses for ``HLSS30_2.0`` and
``HLSL30_2.0``: Sentinel-2 granules carry ``B8A`` and ``B12``, Landsat granules
carry neither and carry ``B05`` to ``B07`` instead. Both carry ``Fmask``.

Every asset also has an ``s3_`` twin, for example ``s3_B04``. Those resolve to
``s3://`` URLs which only work from ``us-west-2``. That is the in-region path
the README's bottleneck table estimates, and it is addressable rather than
hypothetical.

See ``docs/data-sources.md``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class Band(StrEnum):
    """A spectral band, named by what it measures rather than by an asset key."""

    BLUE = "blue"
    GREEN = "green"
    RED = "red"
    NIR_NARROW = "nir_narrow"
    SWIR1 = "swir1"
    SWIR2 = "swir2"


#: The six bands the burn scar head was fine-tuned on, in model input order.
MODEL_BANDS: Final = (
    Band.BLUE,
    Band.GREEN,
    Band.RED,
    Band.NIR_NARROW,
    Band.SWIR1,
    Band.SWIR2,
)

#: The Sentinel-2 collection.
HLSS30: Final = "HLSS30_2.0"

#: The Landsat 8/9 collection.
HLSL30: Final = "HLSL30_2.0"

#: The QA band, used by the phase 2 probe read. Same name in both collections.
QA_ASSET: Final = "Fmask"

#: Prefix for the direct-S3 twin of any asset. Only reachable from us-west-2.
S3_ASSET_PREFIX: Final = "s3_"

_ASSETS: Final[dict[str, dict[Band, str]]] = {
    HLSS30: {
        Band.BLUE: "B02",
        Band.GREEN: "B03",
        Band.RED: "B04",
        Band.NIR_NARROW: "B8A",
        Band.SWIR1: "B11",
        Band.SWIR2: "B12",
    },
    HLSL30: {
        Band.BLUE: "B02",
        Band.GREEN: "B03",
        Band.RED: "B04",
        Band.NIR_NARROW: "B05",
        Band.SWIR1: "B06",
        Band.SWIR2: "B07",
    },
}

#: Accepted spellings for each collection. STAC uses ``HLSS30_2.0``; granule
#: identifiers use ``HLS.S30.``; people write ``HLSS30``.
_ALIASES: Final[dict[str, str]] = {
    "HLSS30_2.0": HLSS30,
    "HLSS30": HLSS30,
    "S30": HLSS30,
    "HLSL30_2.0": HLSL30,
    "HLSL30": HLSL30,
    "L30": HLSL30,
}


def normalise_collection(collection: str) -> str:
    """Return the canonical collection identifier.

    Args:
        collection: A collection id, a short name, or an HLS granule id such
            as ``HLS.S30.T11SLT.2018002T185421.v2.0``.

    Returns:
        Either :data:`HLSS30` or :data:`HLSL30`.

    Raises:
        ValueError: If the collection is not one of the two HLS products.
    """
    text = collection.strip().upper()
    if text.startswith("HLS."):
        # A granule id: HLS.S30.T11SLT...
        parts = text.split(".")
        text = parts[1] if len(parts) > 1 else text

    resolved = _ALIASES.get(text)
    if resolved is None:
        msg = f"not an HLS collection: {collection!r}. Expected {HLSS30} or {HLSL30}"
        raise ValueError(msg)
    return resolved


def asset_name(collection: str, band: Band, *, direct_s3: bool = False) -> str:
    """Return the STAC asset key for one band of one collection.

    Args:
        collection: Collection id, short name, or granule id.
        band: The band wanted.
        direct_s3: Return the ``s3_`` twin, which resolves to an ``s3://`` URL.
            Only reachable from ``us-west-2``.

    Returns:
        The asset key, for example ``B8A`` for narrow NIR on Sentinel-2 and
        ``B05`` for the same band on Landsat.

    Raises:
        ValueError: If the collection is not an HLS product.
    """
    key = _ASSETS[normalise_collection(collection)][band]
    return f"{S3_ASSET_PREFIX}{key}" if direct_s3 else key


def asset_names(
    collection: str,
    bands: tuple[Band, ...] = MODEL_BANDS,
    *,
    direct_s3: bool = False,
) -> tuple[str, ...]:
    """Return the asset keys for several bands, in the order given.

    Order is preserved because it is the model's input order, and reordering
    the channels of a fine-tuned model produces confident nonsense rather than
    an error.
    """
    return tuple(asset_name(collection, band, direct_s3=direct_s3) for band in bands)


def qa_asset_name(collection: str, *, direct_s3: bool = False) -> str:
    """Return the Fmask asset key. Validates the collection on the way past."""
    normalise_collection(collection)
    return f"{S3_ASSET_PREFIX}{QA_ASSET}" if direct_s3 else QA_ASSET
