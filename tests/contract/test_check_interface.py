"""Contract tests - verify all checks implement BaseCheck correctly."""

from __future__ import annotations

import pytest

from aeo_audit.checks.base import BaseCheck
from aeo_audit.core.registry import CheckRegistry


class TestCheckInterface:
    """All registered checks must implement the BaseCheck interface."""

    @pytest.fixture
    def registry(self) -> CheckRegistry:
        reg = CheckRegistry()
        reg.discover_builtin_checks()
        return reg

    def test_all_checks_have_name(self, registry: CheckRegistry) -> None:
        for check_cls in registry.all_checks():
            assert hasattr(check_cls, "name"), f"{check_cls} missing 'name'"
            assert isinstance(check_cls.name, str)

    def test_all_checks_have_category(self, registry: CheckRegistry) -> None:
        for check_cls in registry.all_checks():
            assert hasattr(check_cls, "category"), f"{check_cls} missing 'category'"

    def test_all_checks_have_weight(self, registry: CheckRegistry) -> None:
        for check_cls in registry.all_checks():
            assert hasattr(check_cls, "weight"), f"{check_cls} missing 'weight'"
            assert 0.0 <= check_cls.weight <= 1.0

    def test_all_checks_have_run(self, registry: CheckRegistry) -> None:
        for check_cls in registry.all_checks():
            assert hasattr(check_cls, "run"), f"{check_cls} missing 'run'"
            assert callable(check_cls.run)
