# The justfile is the single source of truth for how the quality gates are
# invoked. Pre-commit and CI both shell out to these recipes rather than
# calling ruff/mypy/pytest themselves, so a hook, a CI run and a local run are
# provably the same command.
#
# Prerequisites: `just` and `uv`.
#     brew install just uv          (macOS)
#     cargo install just            (or)
#     https://docs.astral.sh/uv/getting-started/installation/
# The pre-commit hooks shell out to `just`, so a missing `just` fails the hook
# with a confusing "command not found". Install it before `just setup`.

set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := true
set dotenv-filename := ".env"
set dotenv-required := false

# List the available recipes.
default:
    @just --list --unsorted

# One-time setup: resolve the environment and install the git hooks.
setup:
    uv sync
    # Both hook types. `pre-commit install` alone writes only .git/hooks/pre-commit,
    # which leaves the Conventional Commits check silently inert.
    uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
    @echo
    @echo "Ready. Copy .env.example to .env and fill in your Earthdata login."

# Format the tree in place. Takes optional paths; defaults to everything.
fmt *paths:
    uv run ruff format {{ if paths == "" { "." } else { paths } }}
    uv run ruff check --fix {{ if paths == "" { "." } else { paths } }}

# Lint without modifying anything. Takes optional paths; defaults to everything.
lint *paths:
    uv run ruff check {{ if paths == "" { "." } else { paths } }}
    uv run ruff format --check {{ if paths == "" { "." } else { paths } }}

# Lint with autofix. What the pre-commit hook calls: repairs what it can.
lint-fix *paths:
    uv run ruff check --fix --exit-non-zero-on-fix {{ if paths == "" { "." } else { paths } }}
    uv run ruff format {{ if paths == "" { "." } else { paths } }}

# Type-check in strict mode. Always whole-project; see .pre-commit-config.yaml.
typecheck:
    uv run mypy

# Unit tests only. Fast, hermetic, no network, no GPU, no coverage. The hook.
test *ARGS:
    uv run pytest tests/unit -q -x {{ ARGS }}

# The live S3 / CMR-STAC / Earthdata tests. Needs credentials; skips without.
test-integration *ARGS:
    ./scripts/with-earthdata.sh uv run pytest tests/integration --run-all {{ ARGS }}

# Everything, both trees, all markers enabled.
test-all *ARGS:
    ./scripts/with-earthdata.sh uv run pytest --run-all {{ ARGS }}

# Report whether Earthdata credentials resolve, without printing them.
#
# Credentials come from the environment first, then 1Password, then the
# application's own dotenv or ~/.netrc. See scripts/with-earthdata.sh.
earthdata-check:
    @./scripts/with-earthdata.sh sh -c 'if [ -n "$EARTHDATA_TOKEN" ]; then \
        printf "EARTHDATA_TOKEN resolved, %s characters\n" "$(printf %s "$EARTHDATA_TOKEN" | wc -c | tr -d " ")"; \
    else \
        echo "EARTHDATA_TOKEN not resolved. Export it, add it to your dotenv file, or store it in 1Password."; \
    fi'

# Only the tests that need a CUDA device. Run this on the 5070 node.
test-gpu *ARGS:
    uv run pytest --run-gpu -m gpu {{ ARGS }}

# Coverage. Both trees, since unit-only coverage under-reports badly.
cov *ARGS:
    uv run pytest --run-all --cov=burn_scar_recovery --cov-report=term-missing:skip-covered --cov-report=html {{ ARGS }}

# Lint + typecheck + unit tests. The full gate, and exactly what CI runs.
check: lint typecheck test

# Run every pre-commit hook over the whole tree.
hooks:
    uv run pre-commit run --all-files

# Update the lockfile and the pinned pre-commit hook revisions.
update:
    uv lock --upgrade
    uv run pre-commit autoupdate

# Phase 0 gate: report the interpreter, the torch build, and the visible device.
gate:
    @uv run python -c "import sys, torch; print(f'python  {sys.version.split()[0]}'); print(f'torch   {torch.__version__}'); print(f'cuda    {torch.version.cuda}'); print(f'device  {torch.cuda.get_device_name(0) if torch.cuda.is_available() else (\"mps\" if torch.backends.mps.is_available() else \"cpu\")}'); print(f'sm      {torch.cuda.get_device_capability(0) if torch.cuda.is_available() else \"n/a\"}')"

# Regenerate the README result tables from results/runs.jsonl.
#
# The tables are generated, never typed: a hand-edited number stops matching
# the code that produced it and no reader can tell. With no runs recorded this
# is a no-op, so it does not wipe the stub tables before there is a result.
report:
    uv run python -m burn_scar_recovery.report

# Remove caches and build artifacts. Leaves data/, cache/ and results/ alone.
clean:
    rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov .coverage coverage.xml dist build
    find . -type d -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} +
    find . -type d -name "*.egg-info" -not -path "./.venv/*" -prune -exec rm -rf {} +

# Also remove the virtualenv and the ~10 GB instrument cache. Destructive.
clean-all: clean
    rm -rf .venv cache
