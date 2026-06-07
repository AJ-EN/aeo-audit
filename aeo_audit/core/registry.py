"""Check plugin registry - auto-discovers checks via entry points."""

from __future__ import annotations

import importlib
import importlib.metadata
from typing import Any

from aeo_audit.checks.base import BaseCheck
from aeo_audit.core.models import Category


class CheckRegistry:
    """Registry for AEO check plugins.

    Discovers checks via:
    1. Built-in modules (aeo_audit.checks.*)
    2. Entry points (aeo_audit.checks group)
    3. Manual registration
    """

    def __init__(self) -> None:
        self._checks: dict[str, type[BaseCheck]] = {}
        self._categories: dict[Category, list[type[BaseCheck]]] = {
            cat: [] for cat in Category
        }

    def register(self, check_cls: type[BaseCheck]) -> None:
        """Register a check class."""
        if check_cls.name in self._checks:
            return
        self._checks[check_cls.name] = check_cls
        self._categories[check_cls.category].append(check_cls)

    def get(self, name: str) -> type[BaseCheck] | None:
        """Get a check by name."""
        return self._checks.get(name)

    def get_by_category(self, category: Category) -> list[type[BaseCheck]]:
        """Get all checks in a category."""
        return self._categories.get(category, [])

    def all_checks(self) -> list[type[BaseCheck]]:
        """Get all registered checks."""
        return list(self._checks.values())

    def discover_builtin_checks(self) -> None:
        """Discover and register built-in checks."""
        builtin_modules = [
            "aeo_audit.checks.discovery",
            "aeo_audit.checks.identity",
            "aeo_audit.checks.capabilities",
            "aeo_audit.checks.commerce",
            "aeo_audit.checks.trust",
        ]
        for module_name in builtin_modules:
            try:
                module = importlib.import_module(module_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseCheck)
                        and attr is not BaseCheck
                        and hasattr(attr, "name")
                    ):
                        self.register(attr)
            except ImportError:
                pass

    def load_entry_point_checks(self) -> None:
        """Discover checks from installed entry points."""
        try:
            eps = importlib.metadata.entry_points(group="aeo_audit.checks")
            for ep in eps:
                try:
                    module = ep.load()
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseCheck)
                            and attr is not BaseCheck
                        ):
                            self.register(attr)
                except Exception:
                    pass
        except Exception:
            pass

    def discover_all(self) -> None:
        """Run all discovery mechanisms."""
        self.discover_builtin_checks()
        self.load_entry_point_checks()

    def __len__(self) -> int:
        return len(self._checks)

    def __contains__(self, name: str) -> bool:
        return name in self._checks


# Global registry instance
registry = CheckRegistry()


def create_check(name: str, config: Any = None) -> BaseCheck | None:
    """Factory function to instantiate a check by name."""
    check_cls = registry.get(name)
    if check_cls:
        return check_cls()
    return None
