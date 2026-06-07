"""Integration tests for trust checks."""

from __future__ import annotations

import pytest

from aeo_audit.checks.trust import (
    AuditLogEndpointCheck,
    HealthCheckCheck,
    ReceiptVerificationCheck,
    SlaStatusPageCheck,
    StructuredErrorsCheck,
)
from aeo_audit.core.crawler import Crawler
from aeo_audit.core.models import CheckStatus


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_audit_log_endpoint_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test audit_log_endpoint check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = AuditLogEndpointCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_receipt_verification_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test receipt_verification check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = ReceiptVerificationCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_health_check_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test health_check check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = HealthCheckCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_structured_errors_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test structured_errors check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = StructuredErrorsCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_sla_status_page_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test sla_status_page check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = SlaStatusPageCheck()
        result = await check.run(ctx)
        assert result.status == expected_status
