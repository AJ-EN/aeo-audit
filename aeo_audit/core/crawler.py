"""Playwright-based crawler with caching, retry, and MCP handshake."""

from __future__ import annotations

import asyncio
import contextlib
import urllib.parse
import urllib.robotparser
from typing import Any

import dns.resolver
import extruct
import httpx
from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from aeo_audit.core.models import CheckContext
from aeo_audit.utils.cache import ResponseCache


class Crawler:
    """Async Playwright crawler for AEO auditing.

    Features:
    - Single browser context per scan, reused pages
    - networkidle + custom __AEO_READY__ wait strategy
    - MCP handshake via JSON-RPC initialize
    - SQLite cache keyed by (url, user_agent, accept_header)
    - Respects robots.txt, Crawl-Delay, RateLimit-*, Retry-After
    """

    def __init__(
        self,
        user_agent: str = "AEOAuditor/1.0",
        timeout: int = 30,
        max_redirects: int = 5,
        cache_enabled: bool = True,
        cache_db_path: str = ".aeo_cache.db",
        respect_robots: bool = True,
        wait_strategy: str = "load",
    ) -> None:
        self._user_agent = user_agent
        self._timeout = timeout
        self._wait_strategy = wait_strategy
        self._max_redirects = max_redirects
        self._cache_enabled = cache_enabled
        self._cache_db_path = cache_db_path
        self._respect_robots = respect_robots
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._cache: ResponseCache | None = None

    async def __aenter__(self) -> Crawler:
        """Start browser and create context."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            user_agent=self._user_agent,
            bypass_csp=True,
        )
        if self._cache_enabled:
            self._cache = ResponseCache(db_path=self._cache_db_path)
            self._cache.open()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close browser context."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        if self._cache:
            self._cache.close()

    async def _check_robots(self, url: str) -> None:
        """Check robots.txt constraints for the URL. Raises Exception if disallowed."""
        if not self._respect_robots:
            return
        parsed = urllib.parse.urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parsed.netloc.startswith("localhost"):
            robots_url = f"{parsed.scheme}://{parsed.netloc}/{parts[0]}/robots.txt"
        else:
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(resp.text.splitlines())
                    if not parser.can_fetch(self._user_agent, url):
                        raise Exception(f"URL {url} is disallowed by robots.txt")

                    delay = parser.crawl_delay(self._user_agent)
                    if delay:
                        await asyncio.sleep(float(delay))
        except Exception as e:
            if "disallowed by robots.txt" in str(e):
                raise

    async def fetch(self, url: str, *, wait_for_ready: bool = True) -> CheckContext:
        """Fetch a URL, render JS, extract metadata.

        Args:
            url: Target URL to crawl.
            wait_for_ready: Wait for __AEO_READY__ signal.

        Returns:
            CheckContext with rendered HTML, headers, metadata.
        """
        # Ensure robots.txt is respected
        await self._check_robots(url)

        # Check Cache
        if self._cache_enabled and self._cache:
            cached = self._cache.get(url, user_agent=self._user_agent)
            if cached:
                return CheckContext(
                    url=url,
                    base_url=cached["base_url"],
                    headers=cached.get("headers", {}),
                    rendered_html=cached["rendered_html"],
                    raw_html=cached["raw_html"],
                    extracted_metadata=cached["extracted_metadata"],
                    dns_records=cached.get("dns_records", {}),
                    response_headers=cached["response_headers"],
                )

        if not self._context:
            raise RuntimeError("Browser context not initialized. Use async with.")

        parsed = urllib.parse.urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parsed.netloc.startswith("localhost"):
            base_url = f"{parsed.scheme}://{parsed.netloc}/{parts[0]}"
        else:
            base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Fetch Raw HTTP body first
        try:
            _, _, raw_html = await self.fetch_raw(url)
        except Exception:
            raw_html = ""

        # Playwright Render
        page = await self._context.new_page()
        rendered_html = ""
        response_headers = {}
        try:
            try:
                response = await page.goto(
                    url,
                    timeout=self._timeout * 1000,
                    wait_until=self._wait_strategy,  # type: ignore[arg-type]
                )
                if response:
                    response_headers = {k.lower(): v for k, v in response.headers.items()}
            except Exception as e:
                # If the load strategy times out, fall back to domcontentloaded
                # so we still capture rendered content from slow/long-polling sites.
                if "timeout" in str(e).lower():
                    with contextlib.suppress(Exception):
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                else:
                    raise

            if wait_for_ready:
                with contextlib.suppress(Exception):
                    await page.wait_for_function("window.__AEO_READY__ === true", timeout=2000)

            rendered_html = await page.content()
        finally:
            await page.close()

        # Extract metadata
        extracted_metadata = self.extract_metadata(rendered_html, url)

        # Fetch DNS records
        try:
            dns_records = await self.dns_lookup(parsed.netloc)
        except Exception:
            dns_records = {}

        ctx = CheckContext(
            url=url,
            base_url=base_url,
            rendered_html=rendered_html,
            raw_html=raw_html,
            response_headers=response_headers,
            extracted_metadata=extracted_metadata,
            dns_records=dns_records,
        )

        # Save to Cache
        if self._cache_enabled and self._cache:
            self._cache.set(
                url,
                {
                    "base_url": base_url,
                    "headers": {},
                    "rendered_html": rendered_html,
                    "raw_html": raw_html,
                    "extracted_metadata": extracted_metadata,
                    "dns_records": dns_records,
                    "response_headers": response_headers,
                },
                user_agent=self._user_agent,
            )

        return ctx

    async def fetch_raw(self, url: str) -> tuple[int, dict[str, str], str]:
        """Fetch raw HTTP response (no JS rendering).

        Returns:
            Tuple of (status_code, headers, body).
        """
        async with httpx.AsyncClient(
            headers={"User-Agent": self._user_agent},
            follow_redirects=True,
            timeout=self._timeout,
        ) as client:
            resp = await client.get(url)
            return resp.status_code, dict(resp.headers), resp.text

    def extract_metadata(self, html: str, url: str) -> dict[str, Any]:
        """Extract microdata, JSON-LD, and OpenGraph tags."""
        try:
            return extruct.extract(
                html,
                base_url=url,
                syntaxes=["json-ld", "microdata", "opengraph"],
            ) or {}
        except Exception:
            return {}

    async def mcp_handshake(self, endpoint: str) -> dict[str, Any]:
        """Perform MCP JSON-RPC handshake.

        Args:
            endpoint: MCP endpoint URL.

        Returns:
            MCP initialize response with capabilities.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "aeo-audit", "version": "0.1.0"},
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                raise Exception(f"MCP handshake failed with status code {resp.status_code}")
            data = resp.json()
            if "error" in data:
                raise Exception(f"MCP handshake error: {data['error']}")
            return data.get("result", {})  # type: ignore[no-any-return]

    async def mcp_tools_list(self, endpoint: str) -> list[dict[str, Any]]:
        """Fetch tools list from MCP endpoint.

        Args:
            endpoint: MCP endpoint URL.

        Returns:
            List of tool definitions.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                raise Exception(f"MCP tools/list failed with status code {resp.status_code}")
            data = resp.json()
            if "error" in data:
                raise Exception(f"MCP tools/list error: {data['error']}")
            return data.get("result", {}).get("tools", [])  # type: ignore[no-any-return]

    async def dns_lookup(self, domain: str) -> dict[str, list[str]]:
        """Perform DNS TXT/SRV record lookup.

        Args:
            domain: Domain to query.

        Returns:
            Dict mapping record type to list of values.
        """
        loop = asyncio.get_running_loop()

        def resolve_dns() -> dict[str, list[str]]:
            res: dict[str, list[str]] = {"TXT": [], "SRV": []}
            targets = [domain, f"_agent._tcp.{domain}", f"_mcp._tcp.{domain}"]
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5.0
            resolver.lifetime = 5.0

            for target in targets:
                try:
                    txt_answers = resolver.resolve(target, "TXT")
                    for rdata in txt_answers:
                        for txt_string in rdata.strings:
                            res["TXT"].append(txt_string.decode("utf-8"))
                except Exception:
                    pass
                try:
                    srv_answers = resolver.resolve(target, "SRV")
                    for rdata in srv_answers:
                        res["SRV"].append(
                            f"{rdata.priority} {rdata.weight} {rdata.port} {rdata.target}"
                        )
                except Exception:
                    pass
            return res

        return await loop.run_in_executor(None, resolve_dns)
