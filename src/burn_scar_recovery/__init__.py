"""Burn scar recovery: a query plan over raster.

Segmentation inference across eight years of Harmonized Landsat Sentinel-2
imagery, read from object storage and measured as a sequence of pushdowns.

The pipeline itself is still being built; see ``ROADMAP.md``. This package
currently holds phase 0.5, the instrument: the pieces every later phase writes
its measurements into.

* :mod:`burn_scar_recovery.config` -- what the machine provides.
* :mod:`burn_scar_recovery.runs` -- what an experiment decides, and what it
  measured.
* :mod:`burn_scar_recovery.ids` -- chip identifiers, derived not assigned.
* :mod:`burn_scar_recovery.crs` -- read in UTM, write 4326, measure area in 5070.
* :mod:`burn_scar_recovery.sizes` -- what a configuration required, computed.
* :mod:`burn_scar_recovery.byte_counter` -- the bytes that crossed the network.
* :mod:`burn_scar_recovery.report` -- the README tables, generated from results.
"""

from burn_scar_recovery.byte_counter import ByteCounter, analytic_bytes
from burn_scar_recovery.config import Settings, get_settings
from burn_scar_recovery.crs import AREA_CRS, WRITE_CRS, area_hectares, utm_crs_for_mgrs
from burn_scar_recovery.ids import chip_id, chip_origins, parse_chip_id
from burn_scar_recovery.log import configure_logging, get_logger
from burn_scar_recovery.runs import RunConfig, RunRecord, append_run, load_runs
from burn_scar_recovery.sizes import AssetSizeIndex, content_length, saving

__version__ = "0.1.0"

__all__ = [
    "AREA_CRS",
    "WRITE_CRS",
    "AssetSizeIndex",
    "ByteCounter",
    "RunConfig",
    "RunRecord",
    "Settings",
    "__version__",
    "analytic_bytes",
    "append_run",
    "area_hectares",
    "chip_id",
    "chip_origins",
    "configure_logging",
    "content_length",
    "get_logger",
    "get_settings",
    "load_runs",
    "parse_chip_id",
    "saving",
    "utm_crs_for_mgrs",
]
