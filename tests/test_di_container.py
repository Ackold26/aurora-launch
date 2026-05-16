"""Tests for the ServiceContainer DI layer (ROADMAP 2.7).

Verifies:
- ServiceContainer default state (all slots None).
- set_project_db / get_project_db round-trip.
- set_autosave_manager / get_autosave_manager round-trip.
- set_services_for_testing() allows mock injection.
- reset_services_for_testing() restores the default container.
- Container.clear() resets all slots without raising.
- _get_project_db() in methods.py uses the DI container when a mock is set.
- _get_autosave_manager() in methods.py uses the DI container when a mock is set.
- Thread-safety: concurrent reads from a populated container are consistent.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from aurora_launch.sidecar.services import (
    ServiceContainer,
    get_services,
    reset_services_for_testing,
    set_services_for_testing,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_container():
    """Ensure module-level container is reset after every test."""
    yield
    reset_services_for_testing()


# ---------------------------------------------------------------------------
# ServiceContainer unit tests
# ---------------------------------------------------------------------------


class TestServiceContainerDefaults:
    def test_default_project_db_is_none(self):
        c = ServiceContainer()
        assert c.get_project_db() is None

    def test_default_autosave_manager_is_none(self):
        c = ServiceContainer()
        assert c.get_autosave_manager() is None

    def test_default_gc_thread_is_none(self):
        c = ServiceContainer()
        assert c.gc_thread is None


class TestServiceContainerSetters:
    def test_set_project_db_returns_same_instance(self):
        c = ServiceContainer()
        mock_db = MagicMock(name="ProjectDB")
        c.set_project_db(mock_db)
        assert c.get_project_db() is mock_db

    def test_set_autosave_manager_returns_same_instance(self):
        c = ServiceContainer()
        mock_mgr = MagicMock(name="AutosaveManager")
        c.set_autosave_manager(mock_mgr)
        assert c.get_autosave_manager() is mock_mgr

    def test_constructor_injection(self):
        mock_db = MagicMock(name="ProjectDB")
        mock_mgr = MagicMock(name="AutosaveManager")
        c = ServiceContainer(project_db=mock_db, autosave_manager=mock_mgr)
        assert c.get_project_db() is mock_db
        assert c.get_autosave_manager() is mock_mgr


class TestServiceContainerClear:
    def test_clear_resets_all_slots(self):
        c = ServiceContainer(
            project_db=MagicMock(),
            autosave_manager=MagicMock(),
        )
        c.clear()
        assert c.get_project_db() is None
        assert c.get_autosave_manager() is None
        assert c.gc_thread is None


# ---------------------------------------------------------------------------
# Module-level container management
# ---------------------------------------------------------------------------


class TestModuleLevelContainer:
    def test_get_services_returns_container(self):
        svc = get_services()
        assert isinstance(svc, ServiceContainer)

    def test_set_services_for_testing_replaces_container(self):
        mock_db = MagicMock(name="ProjectDB")
        new_container = ServiceContainer(project_db=mock_db)
        set_services_for_testing(new_container)
        assert get_services() is new_container
        assert get_services().get_project_db() is mock_db

    def test_reset_services_for_testing_restores_empty_container(self):
        set_services_for_testing(ServiceContainer(project_db=MagicMock()))
        reset_services_for_testing()
        # After reset the container should be a fresh empty instance.
        assert get_services().get_project_db() is None

    def test_reset_is_idempotent_without_set(self):
        # Should not raise even if never set_services_for_testing was called.
        reset_services_for_testing()
        reset_services_for_testing()
        assert get_services().get_project_db() is None


# ---------------------------------------------------------------------------
# Integration: _get_project_db uses DI container
# ---------------------------------------------------------------------------


class TestMethodsUseDIContainer:
    def test_get_project_db_returns_mock_from_container(self):
        """methods._get_project_db() must return the injected mock."""
        from aurora_launch.sidecar import methods

        mock_db = MagicMock(name="MockProjectDB")
        container = ServiceContainer(project_db=mock_db)
        set_services_for_testing(container)

        result = methods._get_project_db()
        assert result is mock_db

    def test_get_autosave_manager_returns_mock_from_container(self):
        """methods._get_autosave_manager() must return the injected mock."""
        from aurora_launch.sidecar import methods

        mock_mgr = MagicMock(name="MockAutosaveManager")
        container = ServiceContainer(autosave_manager=mock_mgr)
        set_services_for_testing(container)

        result = methods._get_autosave_manager()
        assert result is mock_mgr

    def test_reset_restores_normal_dispatch(self):
        """After reset, _get_project_db no longer returns the injected mock.

        We verify via the container state rather than calling _get_project_db()
        directly — the production fallback path requires sqlcipher3 which is not
        installed in the CI test environment.
        """
        from aurora_launch.sidecar import methods  # noqa: F401

        mock_db = MagicMock(name="MockProjectDB")
        set_services_for_testing(ServiceContainer(project_db=mock_db))
        # Sanity: mock is active.
        assert get_services().get_project_db() is mock_db

        # Reset; now container has no project_db — mock is gone.
        reset_services_for_testing()
        assert get_services().get_project_db() is None
        # The mock must NOT be discoverable via the new (empty) container.
        assert get_services().get_project_db() is not mock_db


# ---------------------------------------------------------------------------
# Thread-safety smoke test
# ---------------------------------------------------------------------------


class TestContainerThreadSafety:
    def test_concurrent_get_project_db_sees_same_instance(self):
        """Multiple threads reading project_db all get the same mock."""
        mock_db = MagicMock(name="ProjectDB")
        container = ServiceContainer(project_db=mock_db)
        set_services_for_testing(container)

        results: list = []
        errors: list = []

        def worker():
            try:
                results.append(get_services().get_project_db())
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == 20
        assert all(r is mock_db for r in results)
