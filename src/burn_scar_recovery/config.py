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

    # NOTE: the chip plan is deliberately NOT here. chip_size and chip_stride
    # live on RunConfig in burn_scar_recovery.runs, because phase 4 sweeps the
    # stride and a swept knob must be inside the hashed configuration. If it
    # sat here, every run of the sweep would hash identically and the results
    # table would compare unlike things while claiming they were the same.
    #
    # The rule: Settings holds what a machine provides. RunConfig holds what an
    # experiment decides.


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, constructed once."""
    return Settings()
