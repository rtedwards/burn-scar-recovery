"""Burn scar recovery: a query plan over raster.

Segmentation inference across eight years of Harmonized Landsat Sentinel-2
imagery, read from object storage and measured as a sequence of pushdowns.

The pipeline itself is still being designed; see ``ROADMAP.md``. This package
currently holds only the pieces every phase needs: settings and logging.
"""

from burn_scar_recovery.config import Settings, get_settings
from burn_scar_recovery.log import configure_logging, get_logger

__version__ = "0.1.0"

__all__ = [
    "Settings",
    "__version__",
    "configure_logging",
    "get_logger",
    "get_settings",
]
