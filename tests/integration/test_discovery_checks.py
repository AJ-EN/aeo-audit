"""Integration tests for discovery checks."""

from __future__ import annotations

import pytest

from aeo_audit.checks.discovery import (
    AgentManifestCheck,
    DnsTxtRecordsCheck,
    McpEndpointCheck,
    RobotsAgentCheck,
    SitemapXmlCheck,
    WellKnownCrawlCheck,
)
from aeo_audit.core.crawler import Crawler
from aeo_audit.core.models import CheckContext, CheckStatus


@pytest.fixture
def sample_config_benchmarks() -> dict[str, str]:
    """Provide minimal config benchmarks context."""
    return {"percentile_data": "benchmarks/percentiles_v1.json"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),  # manifest exists
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_agent_manifest_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test agent_manifest discovery check against all mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = AgentManifestCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.FAIL),  # MCP endpoint returns 500
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_mcp_endpoint_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test mcp_endpoint discovery check against all mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = McpEndpointCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_robots_agent_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test robots_agent discovery check against all mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        
        # Manually fetch and set robots.txt content in context
        _, _, text = await crawler.fetch_raw(f"{mock_server}/{site_name}/robots.txt")
        ctx.robots_txt = text
        
        check = RobotsAgentCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_sitemap_xml_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test sitemap_xml discovery check against all mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        
        # Fetch sitemap and store in context
        try:
            _, _, text = await crawler.fetch_raw(f"{mock_server}/{site_name}/sitemap.xml")
            ctx.sitemap_xml = text
        except Exception:
            ctx.sitemap_xml = None
            
        check = SitemapXmlCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_well_known_crawl_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test well_known_crawl discovery check against all mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = WellKnownCrawlCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
    ],
)
async def test_dns_txt_records_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test dns_txt_records discovery check against all mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        
        # Populate mocked DNS records
        if site_name in ("perfect", "broken_mcp", "no_pricing", "no_trust"):
            ctx.dns_records = {
                "TXT": [
                    f"aeo-agent-manifest=http://localhost:8765/{site_name}/.well-known/agent-manifest.json",
                    f"aeo-mcp-endpoint=http://localhost:8765/{site_name}/mcp"
                ],
                "SRV": [f"_agent._tcp.{site_name}", f"_mcp._tcp.{site_name}"]
            }
        else:
            ctx.dns_records = {"TXT": [], "SRV": []}
            
        check = DnsTxtRecordsCheck()
        result = await check.run(ctx)
        assert result.status == expected_status
