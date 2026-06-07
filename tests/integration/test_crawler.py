"""Integration tests for the Playwright crawler."""

from __future__ import annotations

import pytest

from aeo_audit.core.crawler import Crawler
from aeo_audit.core.models import CheckContext


@pytest.mark.asyncio
class TestCrawlerIntegration:
    """Crawler integration tests using mock server."""

    async def test_fetch_site_html_and_headers(self, mock_server: str) -> None:
        """Test that fetching a site returns HTML, headers, and timing."""
        async with Crawler(cache_enabled=False) as crawler:
            ctx = await crawler.fetch(f"{mock_server}/perfect/")
            assert ctx.url == f"{mock_server}/perfect/"
            assert "Perfect AEO Site" in ctx.rendered_html
            assert "localhost" in ctx.base_url
            assert len(ctx.response_headers) > 0
            assert ctx.response_headers.get("content-type", "").startswith("text/html")

    async def test_extract_metadata(self, mock_server: str) -> None:
        """Test metadata extraction for JSON-LD and OG tags."""
        async with Crawler(cache_enabled=False) as crawler:
            ctx = await crawler.fetch(f"{mock_server}/perfect/")
            # Extracted metadata should be populated
            assert isinstance(ctx.extracted_metadata, dict)
            # Extruct syntaxes: json-ld, microdata, opengraph
            json_ld = ctx.extracted_metadata.get("json-ld", [])
            assert isinstance(json_ld, list)

    async def test_mcp_handshake_and_tools_list(self, mock_server: str) -> None:
        """Test MCP JSON-RPC handshake and tools list fetching."""
        async with Crawler(cache_enabled=False) as crawler:
            mcp_endpoint = f"{mock_server}/perfect/mcp"
            
            # Handshake
            init_result = await crawler.mcp_handshake(mcp_endpoint)
            assert "protocolVersion" in init_result
            
            # Tools listing
            tools = await crawler.mcp_tools_list(mcp_endpoint)
            assert len(tools) == 3
            assert tools[0]["name"] == "search_products"
            assert "inputSchema" in tools[0]

    async def test_mcp_handshake_broken(self, mock_server: str) -> None:
        """Test broken MCP endpoints handle error scenarios properly."""
        async with Crawler(cache_enabled=False) as crawler:
            mcp_endpoint = f"{mock_server}/broken_mcp/mcp"
            with pytest.raises(Exception):
                await crawler.mcp_handshake(mcp_endpoint)

    async def test_sqlite_cache_hits_and_misses(self, mock_server: str, tmp_path: str) -> None:
        """Test SQLite caching middleware works for repeated fetches."""
        db_path = str(Path(tmp_path) / "test_cache.db")
        async with Crawler(cache_enabled=True, cache_db_path=db_path) as crawler:
            url = f"{mock_server}/perfect/"
            
            # First fetch (miss)
            ctx1 = await crawler.fetch(url)
            assert "Perfect AEO Site" in ctx1.rendered_html
            
            # Second fetch (hit)
            ctx2 = await crawler.fetch(url)
            assert "Perfect AEO Site" in ctx2.rendered_html

    async def test_respect_robots_txt(self, mock_server: str) -> None:
        """Test crawl respect constraints in robots.txt."""
        # perfect allows 'agent'
        async with Crawler(cache_enabled=False, user_agent="agent") as crawler:
            ctx = await crawler.fetch(f"{mock_server}/perfect/")
            assert "Perfect AEO Site" in ctx.rendered_html
            
        # missing_manifest disallows all
        async with Crawler(cache_enabled=False, user_agent="agent") as crawler:
            with pytest.raises(Exception, match="disallowed by robots.txt"):
                await crawler.fetch(f"{mock_server}/missing_manifest/")


from pathlib import Path
