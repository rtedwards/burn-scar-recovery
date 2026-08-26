"""Configuration for the integration tree.

Everything under ``tests/integration/`` talks to live infrastructure: CMR-STAC,
Earthdata Login, and HLS COGs in S3 us-west-2. These tests cost real seconds
and real bytes, so:

  * they are never collected by ``just test`` (path separation -- the unit run
    does not even import these modules);
  * they SKIP, rather than fail, when credentials or the network are absent,
    so a fork's CI and an offline laptop both stay green.

The skip logic lives here so it applies to the whole tree rather than being
repeated in every test.
"""

from __future__ import annotations

import netrc
import os
import socket
from pathlib import Path
from typing import Final

import pytest

# pytest calls pytest_collection_modifyitems on EVERY collected conftest and
# hands each one the complete item list, not just the items underneath it.
# Without this guard a whole-tree run (`just test-all`, `just cov`) would have
# the unit tests skipped by the integration tree's credential check.
_HERE: Final = Path(__file__).parent

# Any one of these is enough to authenticate against Earthdata.
_TOKEN_VARS: Final = ("EARTHDATA_TOKEN",)
_USERPASS_VARS: Final = ("EARTHDATA_USERNAME", "EARTHDATA_PASSWORD")

_NETRC_HOST: Final = "urs.earthdata.nasa.gov"
_PROBE_HOST: Final = "cmr.earthdata.nasa.gov"
_PROBE_TIMEOUT_S: Final = 5.0

# Bound to a name rather than written inline: with target-version = py314 the
# ruff formatter rewrites an inline tuple to PEP 758's unparenthesized
# `except A, B:`, which is a SyntaxError to anything older than 3.14.
_NETRC_ERRORS: Final = (OSError, netrc.NetrcParseError)


def _has_credentials() -> bool:
    """True if Earthdata credentials are present in the environment or .netrc."""
    if any(os.environ.get(v) for v in _TOKEN_VARS):
        return True
    if all(os.environ.get(v) for v in _USERPASS_VARS):
        return True
    # GDAL will also authenticate from a ~/.netrc entry.
    try:
        return netrc.netrc().authenticators(_NETRC_HOST) is not None
    except _NETRC_ERRORS:
        return False


def _has_network() -> bool:
    """True if the Earthdata endpoint resolves and accepts a TCP connection."""
    try:
        with socket.create_connection((_PROBE_HOST, 443), timeout=_PROBE_TIMEOUT_S):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def earthdata_credentials() -> dict[str, str]:
    """The credentials, for tests that need to pass them to GDAL explicitly."""
    return {v: os.environ[v] for v in (*_TOKEN_VARS, *_USERPASS_VARS) if os.environ.get(v)}


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip the integration tree when it cannot possibly work.

    Not every integration test needs Earthdata. The byte counter is validated
    against a public COG that needs no login, and skipping it for want of
    credentials it never uses would leave the project's primary instrument
    unvalidated on any machine without a NASA account. Tests marked
    ``no_credentials`` therefore need the network but not a login.
    """
    ours = [item for item in items if _HERE in Path(item.path).parents]
    if not ours:
        return

    offline = not _has_network()
    unauthenticated = not _has_credentials()

    network_reason = f"cannot reach {_PROBE_HOST}:443 -- offline?"
    credential_reason = (
        "no Earthdata credentials: set EARTHDATA_TOKEN, or "
        "EARTHDATA_USERNAME + EARTHDATA_PASSWORD, or add a ~/.netrc entry "
        f"for {_NETRC_HOST}. See .env.example."
    )

    for item in ours:
        needs_login = item.get_closest_marker("no_credentials") is None
        if offline:
            item.add_marker(pytest.mark.skip(reason=network_reason))
        elif needs_login and unauthenticated:
            item.add_marker(pytest.mark.skip(reason=credential_reason))
