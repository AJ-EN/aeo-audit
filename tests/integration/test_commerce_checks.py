"""Integration tests for commerce checks."""

from __future__ import annotations

import pytest

from aeo_audit.checks.commerce import (
    AgentPricingJsonCheck,
    CryptoPaymentHintsCheck,
    StripeCheckoutHintsCheck,
    TrialFreemiumSignalsCheck,
    UsageMeteringApiCheck,
)
from aeo_audit.core.crawler import Crawler
from aeo_audit.core.models import CheckStatus


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("no_pricing", CheckStatus.FAIL),
        ("no_trust", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_agent_pricing_json_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test agent_pricing_json check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = AgentPricingJsonCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_stripe_checkout_hints_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test stripe_checkout_hints check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = StripeCheckoutHintsCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_crypto_payment_hints_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test crypto_payment_hints check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = CryptoPaymentHintsCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_usage_metering_api_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test usage_metering_api check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = UsageMeteringApiCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_trial_freemium_signals_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test trial_freemium_signals check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = TrialFreemiumSignalsCheck()
        result = await check.run(ctx)
        assert result.status == expected_status
