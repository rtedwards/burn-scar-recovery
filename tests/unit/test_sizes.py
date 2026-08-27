"""Tests for analytic byte accounting.

No network here. ``content_length`` is exercised against a live public asset in
``tests/integration/``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import pytest

from burn_scar_recovery.sizes import (
    SIZES_FILENAME,
    AssetSizeError,
    AssetSizeIndex,
    content_length,
    saving,
)

if TYPE_CHECKING:
    from pathlib import Path

_A = "https://example.invalid/a.tif"
_B = "https://example.invalid/b.tif"
_FMASK = "https://example.invalid/fmask.tif"


@pytest.fixture
def index() -> AssetSizeIndex:
    return AssetSizeIndex({_A: 100, _B: 250, _FMASK: 40})


def test_total_sums_known_sizes(index: AssetSizeIndex) -> None:
    assert index.total([_A, _B]) == 350


def test_a_repeated_asset_is_counted_each_time(index: AssetSizeIndex) -> None:
    """Reading the same file twice costs twice. Deduplicating would under-report."""
    assert index.total([_A, _A]) == 200


def test_unknown_size_raises_rather_than_being_skipped(index: AssetSizeIndex) -> None:
    """Skipping an unknown would under-report.

    That is the direction that makes a pushdown look better than it is, which
    is the one kind of error this table must not make.
    """
    with pytest.raises(AssetSizeError, match="no known size"):
        index.total([_A, "https://example.invalid/missing.tif"])


def test_empty_selection_is_zero(index: AssetSizeIndex) -> None:
    assert index.total([]) == 0


def test_membership_and_length(index: AssetSizeIndex) -> None:
    assert _A in index
    assert "https://example.invalid/nope.tif" not in index
    assert len(index) == 3
    assert index.get(_A) == 100
    assert index.get("https://example.invalid/nope.tif") is None


def test_fetch_is_a_noop_when_everything_is_known(index: AssetSizeIndex) -> None:
    """A cached extent must not re-issue HEAD requests.

    The example.invalid hosts do not resolve, so if this tried the network the
    test would hang or fail rather than pass.
    """
    assert index.fetch([_A, _B]) == 0


# -- The pushdown arithmetic -------------------------------------------------


def test_band_projection_saving(index: AssetSizeIndex) -> None:
    """Six assets of the available set: the saving is exact, not measured."""
    naive = index.total([_A, _B, _FMASK])
    projected = index.total([_A, _FMASK])
    assert saving(projected, naive) == pytest.approx(1 - 140 / 390)


def test_saving_is_zero_when_nothing_is_pruned() -> None:
    assert saving(100, 100) == pytest.approx(0.0)


def test_saving_is_one_when_everything_is_pruned() -> None:
    assert saving(0, 100) == pytest.approx(1.0)


def test_saving_without_a_baseline_is_none() -> None:
    assert saving(10, 0) is None


# -- Persistence -------------------------------------------------------------


def test_save_then_load_round_trips(tmp_path: Path, index: AssetSizeIndex) -> None:
    index.save(tmp_path)
    assert (tmp_path / SIZES_FILENAME).exists()
    assert AssetSizeIndex.load(tmp_path).to_dict() == index.to_dict()


def test_load_is_empty_when_there_is_no_cache(tmp_path: Path) -> None:
    assert len(AssetSizeIndex.load(tmp_path)) == 0


def test_to_dict_is_a_copy(index: AssetSizeIndex) -> None:
    snapshot = index.to_dict()
    snapshot[_A] = 999
    assert index.get(_A) == 100


# -- The request itself ------------------------------------------------------


class _FakeResponse:
    """Minimal stand-in for an HTTP response."""

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def test_headers_are_sent_on_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Earthdata bearer token path.

    LP DAAC assets sit behind lp-prod-protected, so every real HEAD in this
    project carries an Authorization header. Untested, this would fail only
    once credentials existed, which is the worst time to find out.
    """
    captured: dict[str, str] = {}

    def fake_urlopen(request: object, timeout: float = 0.0) -> _FakeResponse:
        captured.update(request.headers)  # type: ignore[attr-defined]
        return _FakeResponse({"Content-Length": "123"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert content_length(_A, headers={"Authorization": "Bearer secret"}) == 123
    # urllib title-cases header names.
    assert captured == {"Authorization": "Bearer secret"}


def test_a_network_failure_raises_asset_size_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object, **__: object) -> None:
        raise OSError("connection reset")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(AssetSizeError, match="HEAD failed"):
        content_length(_A)


def test_a_missing_content_length_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A size we cannot read must not silently become zero."""
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_, **__: _FakeResponse({}),
    )
    with pytest.raises(AssetSizeError, match="no Content-Length"):
        content_length(_A)


def test_fetch_tolerates_one_bad_asset_but_leaves_it_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed HEAD must not become a zero. total() then refuses to guess."""

    def selective(request: object, timeout: float = 0.0) -> _FakeResponse:
        if request.full_url == _B:  # type: ignore[attr-defined]
            raise OSError("gone")
        return _FakeResponse({"Content-Length": "10"})

    monkeypatch.setattr("urllib.request.urlopen", selective)
    index = AssetSizeIndex()
    index.fetch([_A, _B], max_workers=2)
    assert index.get(_A) == 10
    assert index.get(_B) is None
    with pytest.raises(AssetSizeError, match="no known size"):
        index.total([_A, _B])
