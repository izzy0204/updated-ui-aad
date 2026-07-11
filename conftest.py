"""Pytest configuration for clinical model card tests."""

from __future__ import annotations

import pytest

collect_ignore = ["test_updates.py"]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if "test_caching" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif "test_updates" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif not any(m.name in ("unit", "integration") for m in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
