"""Integration tests for capabilities checks."""

from __future__ import annotations

import pytest

from aeo_audit.checks.capabilities import (
    AsyncWebhooksCheck,
    GraphqlIntrospectionCheck,
    JsonSchemaEndpointsCheck,
    McpToolsListCheck,
    OpenApiSpecCheck,
)
from aeo_audit.core.crawler import Crawler
from aeo_audit.core.models import CheckStatus


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_openapi_spec_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test openapi_spec check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = OpenApiSpecCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.FAIL),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_mcp_tools_list_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test mcp_tools_list check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = McpToolsListCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_json_schema_endpoints_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test json_schema_endpoints check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = JsonSchemaEndpointsCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_graphql_introspection_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test graphql_introspection check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = GraphqlIntrospectionCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_async_webhooks_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test async_webhooks check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = AsyncWebhooksCheck()
        result = await check.run(ctx)
        assert result.status == expected_status
