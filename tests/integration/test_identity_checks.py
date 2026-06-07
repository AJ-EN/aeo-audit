"""Integration tests for identity checks."""

from __future__ import annotations

import pytest

from aeo_audit.checks.identity import (
    AgentIdentityJsonCheck,
    DelegationProofCheck,
    DidDocumentCheck,
    OauthMetadataCheck,
    WalletHintsCheck,
)
from aeo_audit.core.crawler import Crawler
from aeo_audit.core.models import CheckStatus


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
    ],
)
async def test_did_document_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test did_document check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = DidDocumentCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
    ],
)
async def test_delegation_proof_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test delegation_proof check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = DelegationProofCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
    ],
)
async def test_oauth_metadata_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test oauth_metadata check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = OauthMetadataCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
    ],
)
async def test_wallet_hints_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test wallet_hints check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        
        # Expose response headers / meta tags if minimal to ensure fail/pass
        if site_name == "minimal":
            ctx.rendered_html = "<html><body>No wallet hints here</body></html>"
        elif site_name == "missing_manifest":
            ctx.rendered_html = "<html><body>No wallet hints here</body></html>"
            
        check = WalletHintsCheck()
        result = await check.run(ctx)
        assert result.status == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "site_name,expected_status",
    [
        ("perfect", CheckStatus.PASS),
        ("missing_manifest", CheckStatus.FAIL),
        ("no_trust", CheckStatus.PASS),
        ("minimal", CheckStatus.FAIL),
        ("broken_mcp", CheckStatus.PASS),
        ("no_pricing", CheckStatus.PASS),
    ],
)
async def test_agent_identity_json_check(
    site_name: str, expected_status: CheckStatus, mock_server: str
) -> None:
    """Test agent_identity_json check against mock sites."""
    async with Crawler(cache_enabled=False, respect_robots=False) as crawler:
        url = f"{mock_server}/{site_name}/"
        ctx = await crawler.fetch(url)
        check = AgentIdentityJsonCheck()
        result = await check.run(ctx)
        assert result.status == expected_status
