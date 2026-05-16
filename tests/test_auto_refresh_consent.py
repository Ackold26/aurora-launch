"""Tests for ConsentManager — RefreshConsentSetting persistence (ROADMAP §3.5).

Covers: get (null state), set (enabled/frequency), persistence, frequency update.
"""

from __future__ import annotations

from typing import Any

import pytest

from aurora_launch.engines.data_source_watcher import ConsentManager
from aurora_launch.schemas.auto_refresh import RefreshConsentSetting


# ---------------------------------------------------------------------------
# In-memory dict shim (mirrors what methods.py _DbKvShim does)
# ---------------------------------------------------------------------------


class _DictStore:
    """Simple in-memory key-value store for testing ConsentManager."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_returns_none_when_no_consent_stored() -> None:
    mgr = ConsentManager(db_store=_DictStore())
    result = mgr.get()
    assert result is None, "First-run: consent should be None"


def test_set_enabled_persists_and_returns_setting() -> None:
    store = _DictStore()
    mgr = ConsentManager(db_store=store)
    result = mgr.set(enabled=True, frequency="weekly")
    assert isinstance(result, RefreshConsentSetting)
    assert result.enabled is True
    assert result.frequency == "weekly"
    assert result.last_prompted_at is not None


def test_get_after_set_returns_same_value() -> None:
    store = _DictStore()
    mgr = ConsentManager(db_store=store)
    mgr.set(enabled=True, frequency="monthly")
    retrieved = mgr.get()
    assert retrieved is not None
    assert retrieved.enabled is True
    assert retrieved.frequency == "monthly"


def test_set_disabled_persists() -> None:
    store = _DictStore()
    mgr = ConsentManager(db_store=store)
    mgr.set(enabled=True, frequency="daily")
    mgr.set(enabled=False, frequency="daily")
    result = mgr.get()
    assert result is not None
    assert result.enabled is False


def test_frequency_change_persists() -> None:
    store = _DictStore()
    mgr = ConsentManager(db_store=store)
    mgr.set(enabled=True, frequency="daily")
    mgr.set(enabled=True, frequency="monthly")
    result = mgr.get()
    assert result is not None
    assert result.frequency == "monthly"


def test_consent_works_without_store() -> None:
    """ConsentManager without db_store: in-memory only, no crash."""
    mgr = ConsentManager(db_store=None)
    assert mgr.get() is None
    result = mgr.set(enabled=True)
    assert result.enabled is True
    # get() should return cached value
    assert mgr.get() is not None
    assert mgr.get().enabled is True  # type: ignore[union-attr]


def test_consent_setting_default_frequency() -> None:
    store = _DictStore()
    mgr = ConsentManager(db_store=store)
    result = mgr.set(enabled=False)
    assert result.frequency == "weekly"  # default
