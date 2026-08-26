"""Runtime settings, read from the environment or a local ``.env``.

See ``.env.example`` for the variables this expects and why each one is here.
Nothing in this module reaches the network; it only describes where things
live and which knobs phase 2 is going to sweep.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Everything the pipeline needs from outside the process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # -- NASA Earthdata Login -------------------------------------------------
    # HLS is behind Earthdata. Either a bearer token or a user/password pair;
    # the token path avoids putting a password in a .netrc for GDAL.
    earthdata_token: SecretStr | None = None
    earthdata_username: str | None = None
    earthdata_password: SecretStr | None = None

    # -- Object storage -------------------------------------------------------
    # HLS sits in us-west-2. Reading it from anywhere else adds latency to
    # every range request, which is the thing the project is measuring.
    aws_region: str = "us-west-2"
    cmr_stac_url: str = "https://cmr.earthdata.nasa.gov/stac/LPCLOUD"

    # -- Local paths ----------------------------------------------------------
    # The chip cache is an instrument, not a data store: ~10 GB, ~20k chips,
    # on NVMe. It answers "how fast does the card go when nothing starves it".
    data_dir: Path = Field(default=REPO_ROOT / "data")
    cache_dir: Path = Field(default=REPO_ROOT / "cache")
    results_dir: Path = Field(default=REPO_ROOT / "results")

    # -- Chip plan ------------------------------------------------------------
    # The model input is fixed, so the halo comes out of the stride and every
    # pixel of it costs read amplification. 224/192 is 1.36x.
    chip_size: int = 224
    chip_stride: int = 192

    @property
    def halo(self) -> int:
        """Pixels of overlap on each side of a chip."""
        return (self.chip_size - self.chip_stride) // 2

    @property
    def read_amplification(self) -> float:
        """Bytes read per byte of unique ground area, from the stride alone."""
        return (self.chip_size / self.chip_stride) ** 2


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, constructed once."""
    return Settings()
