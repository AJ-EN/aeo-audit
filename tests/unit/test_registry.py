"""Tests for the check plugin registry."""

from __future__ import annotations

from aeo_audit.checks.base import BaseCheck
from aeo_audit.core.models import Category, CheckContext, CheckResult, CheckStatus
from aeo_audit.core.registry import CheckRegistry, create_check


class MockCheck(BaseCheck):
    """Mock check for testing the registry."""

    name = "mock_check"
    category = Category.DISCOVERY
    weight = 0.5
    description = "Mock check description"

    async def run(self, context: CheckContext) -> CheckResult:
        return self._make_result(status=CheckStatus.PASS, score=1.0)


class TestCheckRegistry:
    """Tests for the CheckRegistry class."""

    def test_register_and_get(self) -> None:
        reg = CheckRegistry()
        reg.register(MockCheck)

        assert len(reg) == 1
        assert "mock_check" in reg

        check_cls = reg.get("mock_check")
        assert check_cls is MockCheck

        # Instantiate check
        check = check_cls()
        assert check.name == "mock_check"
        assert check.category == Category.DISCOVERY
        assert check.weight == 0.5

    def test_get_by_category(self) -> None:
        reg = CheckRegistry()
        reg.register(MockCheck)

        discovery_checks = reg.get_by_category(Category.DISCOVERY)
        assert len(discovery_checks) == 1
        assert discovery_checks[0] is MockCheck

        identity_checks = reg.get_by_category(Category.IDENTITY)
        assert len(identity_checks) == 0

    def test_all_checks(self) -> None:
        reg = CheckRegistry()
        reg.register(MockCheck)

        checks = reg.all_checks()
        assert len(checks) == 1
        assert checks[0] is MockCheck

    def test_create_check_factory(self) -> None:
        # Register in global registry for the factory function
        from aeo_audit.core.registry import registry

        registry.register(MockCheck)

        check = create_check("mock_check")
        assert check is not None
        assert isinstance(check, BaseCheck)
        assert check.name == "mock_check"

        # Test nonexistent check
        assert create_check("nonexistent_check") is None

        # Cleanup global registry
        if "mock_check" in registry._checks:
            del registry._checks["mock_check"]
            registry._categories[Category.DISCOVERY].remove(MockCheck)

    def test_base_check_helpers(self) -> None:
        check = MockCheck()

        # Test score helper
        result = check._make_result(status=CheckStatus.PASS, score=0.8)
        assert check.score(result) == 0.8

        # Test validate helper
        assert check.validate(result) is True

        invalid_result1 = check._make_result(status=CheckStatus.PASS, score=0.2)
        assert check.validate(invalid_result1) is False

        invalid_result2 = check._make_result(status=CheckStatus.FAIL, score=0.7)
        assert check.validate(invalid_result2) is False

        invalid_result3 = CheckResult.model_construct(
            name=check.name,
            category=check.category,
            status=CheckStatus.PASS,
            score=1.2,
            weight=check.weight,
        )
        assert check.validate(invalid_result3) is False
