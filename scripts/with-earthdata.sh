#!/usr/bin/env bash
#
# Put Earthdata credentials in the environment, then run the given command.
#
# Precedence, highest first:
#
#   1. EARTHDATA_TOKEN already exported in the shell. Nothing else is consulted.
#   2. 1Password, if the `op` CLI is installed and a reference is configured.
#   3. Nothing. The application then falls back to its own dotenv file, or to a
#      ~/.netrc entry for urs.earthdata.nasa.gov.
#
# 1Password is a convenience and never a requirement. A contributor without it
# needs no account and no CLI: `op` is not found, this script changes nothing,
# and the command runs exactly as it would have. That property is the point --
# a project that can only be run by the person who set it up is not reproducible,
# and phase 11 promises a reproduce path.
#
# Escape hatches:
#
#   OP_EARTHDATA_REF=            disable the 1Password path entirely
#   OP_EARTHDATA_REF=op://v/i/f  point at a different vault, item or field
#
# The token is never printed, and never written to disk. It lives in the
# environment of one child process and dies with it.

set -euo pipefail

# A single dash, so an explicitly empty value disables the lookup rather than
# falling back to the default.
OP_EARTHDATA_REF="${OP_EARTHDATA_REF-op://Private/Earth Data/token}"

if [[ -z "${EARTHDATA_TOKEN:-}" && -n "${OP_EARTHDATA_REF}" ]] && command -v op >/dev/null 2>&1; then
    if token="$(op read "${OP_EARTHDATA_REF}" 2>/dev/null)"; then
        export EARTHDATA_TOKEN="${token}"
        printf 'earthdata: token from 1Password (%s)\n' "${OP_EARTHDATA_REF}" >&2
    else
        printf 'earthdata: no token at %s, continuing without one\n' \
            "${OP_EARTHDATA_REF}" >&2
    fi
fi

exec "$@"
