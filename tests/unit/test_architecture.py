"""Enforce the layering in ``docs/architecture.md``.

A dependency rule written only in prose erodes. This walks the import graph and
fails when a layer reaches somewhere it should not, so the boundary is checked
by the commit hook rather than remembered.

The two rules that matter:

* A **stage** must not import the **instrument**. A stage that can write a run
  record eventually will, and then measurements are scattered across eleven
  phases with no single place to read them.
* A **stage** must not import ``ray``. A stage that does cannot be tested
  without a Ray runtime, and the commit hook runs these tests.

Stage modules do not exist yet. The rules are encoded now so that phase 1
cannot introduce a violation unnoticed, which is the whole reason for writing
them down before the code rather than after.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

_PACKAGE: Final = "burn_scar_recovery"
_SRC: Final = Path(__file__).resolve().parents[2] / "src" / _PACKAGE

#: Layers, outermost last. See docs/architecture.md.
FOUNDATION: Final = frozenset({"config", "log"})
PRIMITIVES: Final = frozenset({"bands", "crs", "ids"})
INSTRUMENT: Final = frozenset({"runs", "sizes", "byte_counter", "report"})
STAGES: Final = frozenset({"stac", "read", "chip", "infer", "vectorize", "union", "write"})
DRIVER: Final = frozenset({"cli", "pipeline"})

#: Third-party packages a stage must not reach for.
FORBIDDEN_IN_STAGES: Final = frozenset({"ray"})


def _module_names() -> list[str]:
    return sorted(p.stem for p in _SRC.glob("*.py") if p.stem != "__init__")


def _imports_from_source(source: str) -> set[str]:
    """Return every top-level package or sibling module ``source`` imports."""
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root == _PACKAGE:
                parts = node.module.split(".")
                if len(parts) > 1:
                    found.add(parts[1])
            else:
                found.add(root)
    return found


def _imports(module: str) -> set[str]:
    """Return every top-level package or sibling module ``module`` imports."""
    return _imports_from_source((_SRC / f"{module}.py").read_text(encoding="utf-8"))


def _present(layer: frozenset[str]) -> list[str]:
    return sorted(layer.intersection(_module_names()))


# -- The two rules -----------------------------------------------------------


@pytest.mark.parametrize("module", _present(STAGES) or [pytest.param("", marks=pytest.mark.skip)])
def test_a_stage_does_not_import_the_instrument(module: str) -> None:
    """A stage returns its statistics. It never records them itself."""
    leaked = _imports(module) & INSTRUMENT
    assert not leaked, (
        f"stage {module!r} imports instrument module(s) {sorted(leaked)}. "
        "A stage returns data and stats; the driver builds the RunRecord."
    )


@pytest.mark.parametrize("module", _present(STAGES) or [pytest.param("", marks=pytest.mark.skip)])
def test_a_stage_does_not_import_ray(module: str) -> None:
    """Ray Data owns the plumbing. A stage owns one batch."""
    leaked = _imports(module) & FORBIDDEN_IN_STAGES
    assert not leaked, (
        f"stage {module!r} imports {sorted(leaked)}. Stages take a batch and "
        "return a batch; the driver hands them to map_batches."
    )


# -- The layering underneath -------------------------------------------------


@pytest.mark.parametrize("module", _present(PRIMITIVES))
def test_a_primitive_reaches_no_further_than_the_foundation(module: str) -> None:
    """Domain facts must not depend on measurement or on a pipeline step."""
    leaked = _imports(module) & (INSTRUMENT | STAGES | DRIVER)
    assert not leaked, f"primitive {module!r} imports {sorted(leaked)}"


@pytest.mark.parametrize("module", _present(INSTRUMENT))
def test_the_instrument_does_not_import_a_stage(module: str) -> None:
    """Measurement observes the pipeline. It must not depend on one."""
    leaked = _imports(module) & (STAGES | DRIVER)
    assert not leaked, f"instrument module {module!r} imports {sorted(leaked)}"


@pytest.mark.parametrize("module", _present(FOUNDATION))
def test_the_foundation_depends_on_nothing_in_the_project(module: str) -> None:
    leaked = _imports(module) & (PRIMITIVES | INSTRUMENT | STAGES | DRIVER)
    assert not leaked, f"foundation module {module!r} imports {sorted(leaked)}"


# -- The map itself ----------------------------------------------------------


def test_every_module_is_assigned_to_a_layer() -> None:
    """A new module must be placed deliberately, not left unclassified.

    Without this, adding a module silently exempts it from every rule above.
    """
    known = FOUNDATION | PRIMITIVES | INSTRUMENT | STAGES | DRIVER
    unassigned = sorted(set(_module_names()) - known)
    assert not unassigned, (
        f"module(s) {unassigned} are in no layer. Add them to a layer in "
        "tests/unit/test_architecture.py and to the table in docs/architecture.md."
    )


def test_the_package_root_does_not_re_export_a_stage() -> None:
    """``import burn_scar_recovery`` must stay cheap.

    ``infer`` imports torch, which costs seconds, and the commit hook runs
    these tests. Stages are imported by path instead.
    """
    root = ast.parse((_SRC / "__init__.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(root):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == _PACKAGE and len(parts) > 1:
                imported.add(parts[1])
    leaked = imported & STAGES
    assert not leaked, (
        f"__init__.py re-exports stage(s) {sorted(leaked)}. Import them by path: "
        "from burn_scar_recovery.infer import ..."
    )


# -- The checker itself ------------------------------------------------------
#
# The two stage rules skip while no stage module exists, so without these the
# enforcement logic would first run during phase 1 -- exactly when a violation
# would be introduced. These prove the checker catches one.


def test_the_checker_sees_a_plain_import() -> None:
    assert "ray" in _imports_from_source("import ray")


def test_the_checker_sees_a_dotted_import() -> None:
    assert "ray" in _imports_from_source("import ray.data as rd")


def test_the_checker_sees_a_from_import() -> None:
    assert "ray" in _imports_from_source("from ray.data import Dataset")


def test_the_checker_sees_a_sibling_module() -> None:
    source = "from burn_scar_recovery.runs import RunRecord"
    assert "runs" in _imports_from_source(source)


def test_the_checker_sees_an_import_nested_in_a_function() -> None:
    """A deferred import is still an import, and would still break the rule."""
    source = "def f():\n    import ray\n    return ray"
    assert "ray" in _imports_from_source(source)


def test_the_checker_would_reject_a_violating_stage() -> None:
    """The rule, applied to a stage that breaks both halves of it."""
    source = "import ray\nfrom burn_scar_recovery.runs import append_run\n"
    found = _imports_from_source(source)
    assert found & FORBIDDEN_IN_STAGES == {"ray"}
    assert found & INSTRUMENT == {"runs"}


def test_the_checker_passes_a_compliant_stage() -> None:
    source = (
        "import numpy as np\n"
        "from burn_scar_recovery.bands import MODEL_BANDS\n"
        "from burn_scar_recovery.ids import chip_id\n"
    )
    found = _imports_from_source(source)
    assert not found & FORBIDDEN_IN_STAGES
    assert not found & INSTRUMENT
