"""Discovery checks for AEO readiness."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import ClassVar

import httpx

from aeo_audit.checks.base import BaseCheck
from aeo_audit.core.models import Category, CheckContext, CheckResult, CheckStatus, Severity


class AgentManifestCheck(BaseCheck):
    """Check for the presence and validity of an agent manifest (/.well-known/agent-manifest.json)."""

    name: ClassVar[str] = "agent_manifest"
    category: ClassVar[Category] = Category.DISCOVERY
    weight: ClassVar[float] = 0.25
    description: ClassVar[str] = "Checks for a valid agent manifest at /.well-known/agent-manifest.json"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        url = f"{context.base_url}/.well-known/agent-manifest.json"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    # Try agent.json as a fallback
                    url = f"{context.base_url}/.well-known/agent.json"
                    resp = await client.get(url)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception:
                        return self._make_result(
                            status=CheckStatus.FAIL,
                            score=0.0,
                            message="Agent manifest exists but is not valid JSON",
                        )

                    errors = []
                    required = ["name", "version", "capabilities", "auth", "pricing_url"]
                    for field in required:
                        if field not in data:
                            errors.append(f"Missing required field: {field}")

                    if not errors:
                        return self._make_result(
                            status=CheckStatus.PASS,
                            score=1.0,
                            message="Found valid agent manifest",
                            evidence={"manifest": data, "url": url},
                        )
                    else:
                        findings = [
                            self._make_finding(
                                title="Invalid Agent Manifest Schema",
                                description=f"The agent manifest is missing required fields: {', '.join(errors)}",
                                severity=Severity.HIGH,
                                recommendation="Update agent-manifest.json to include name, version, capabilities, auth, and pricing_url.",
                            )
                        ]
                        return self._make_result(
                            status=CheckStatus.FAIL,
                            score=0.0,
                            message="Agent manifest has invalid schema",
                            evidence={"manifest": data, "url": url, "errors": errors},
                            findings=findings,
                        )
                else:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message="No agent-manifest.json or agent.json found at /.well-known/",
                        findings=[
                            self._make_finding(
                                title="Missing Agent Manifest",
                                description="No agent-manifest.json found at /.well-known/",
                                severity=Severity.HIGH,
                                recommendation="Create /.well-known/agent-manifest.json",
                            )
                        ],
                    )
        except Exception as e:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message=f"Error checking agent manifest: {e}",
            )


class McpEndpointCheck(BaseCheck):
    """Check for a discoverable MCP (Model Context Protocol) endpoint."""

    name: ClassVar[str] = "mcp_endpoint"
    category: ClassVar[Category] = Category.DISCOVERY
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Checks for a discoverable MCP endpoint"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        mcp_url = None
        # 1. Check Link header
        link_hdr = context.response_headers.get("link", "")
        if 'rel="mcp"' in link_hdr or "rel=mcp" in link_hdr:
            try:
                start = link_hdr.find("<") + 1
                end = link_hdr.find(">")
                if start > 0 and end > start:
                    mcp_url = link_hdr[start:end]
            except Exception:
                pass

        # 2. Check /.well-known/mcp.json
        if not mcp_url:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(f"{context.base_url}/.well-known/mcp.json")
                    if resp.status_code == 200:
                        data = resp.json()
                        mcp_url = data.get("mcp_endpoint")
            except Exception:
                pass

        # 3. Check /.well-known/agent-manifest.json
        if not mcp_url:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(f"{context.base_url}/.well-known/agent-manifest.json")
                    if resp.status_code == 200:
                        data = resp.json()
                        mcp_url = data.get("capabilities", {}).get("mcp_endpoint")
            except Exception:
                pass

        if not mcp_url:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No MCP endpoint found in Link header, mcp.json, or agent-manifest.json",
            )

        # MCP handshake + tools/list
        try:
            from aeo_audit.core.crawler import Crawler
            async with Crawler(cache_enabled=False) as crawler:
                init_res = await crawler.mcp_handshake(mcp_url)
                tools = await crawler.mcp_tools_list(mcp_url)

                return self._make_result(
                    status=CheckStatus.PASS,
                    score=1.0,
                    message=f"MCP endpoint active: {mcp_url}",
                    evidence={"endpoint": mcp_url, "initialize": init_res, "tools": tools},
                )
        except Exception as e:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message=f"MCP endpoint found at {mcp_url} but handshake failed: {e}",
                findings=[
                    self._make_finding(
                        title="MCP Handshake Failure",
                        description=f"The MCP endpoint at {mcp_url} failed to respond: {e}",
                        severity=Severity.HIGH,
                        recommendation="Verify the MCP service is running and complies with the JSON-RPC spec.",
                    )
                ],
            )


class RobotsAgentCheck(BaseCheck):
    """Check robots.txt for agent-friendly directives."""

    name: ClassVar[str] = "robots_agent"
    category: ClassVar[Category] = Category.DISCOVERY
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks robots.txt for agent-friendly directives"
    timeout: ClassVar[float] = 10.0

    # User-agent tokens that identify AI agents / LLM crawlers.
    AGENT_UAS: ClassVar[frozenset[str]] = frozenset(
        {"agent", "gptbot", "claudebot", "anthropic-ai", "oai-searchbot", "chatgpt-user", "perplexitybot"}
    )

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check.

        Scores agent crawlability on a tiered scale rather than demanding an
        explicit agent allow-list (which almost no site has yet):

        - 1.00 PASS  - robots.txt explicitly allows a named agent (Allow: /)
        - 0.75 PASS  - allows all crawlers (``User-agent: *`` not blocking ``/``)
        - 0.00 FAIL  - blocks agents (``Disallow: /`` for an agent or ``*``)
        - 0.00 FAIL  - no robots.txt at all (no crawl guidance published)
        """
        robots_text = context.robots_txt
        # Self-fetch fallback: the crawler does not populate robots_txt, so
        # fetch it directly (mirrors SitemapXmlCheck) to work in production.
        if not robots_text:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(f"{context.base_url}/robots.txt")
                    if resp.status_code == 200:
                        robots_text = resp.text
            except Exception:
                pass
        robots_text = robots_text or ""

        if not robots_text.strip():
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No robots.txt found",
                findings=[
                    self._make_finding(
                        title="Missing robots.txt",
                        description="No robots.txt is published, so the site offers no crawl guidance to agents.",
                        severity=Severity.MEDIUM,
                        recommendation="Publish a robots.txt that allows agents, e.g. 'User-agent: GPTBot\\nAllow: /'.",
                    )
                ],
            )

        agent_named_allow = False
        agent_named_block = False
        star_present = False
        star_block_root = False
        saw_user_agent = False
        current_uas: list[str] = []

        for raw in robots_text.splitlines():
            line = raw.strip().lower()
            if not line or line.startswith("#"):
                continue
            if line.startswith("user-agent:"):
                ua = line.split(":", 1)[1].strip()
                # robots.txt groups consecutive user-agent lines together.
                current_uas.append(ua)
                saw_user_agent = True
                if ua == "*":
                    star_present = True
            else:
                if line.startswith("allow:"):
                    path = line.split(":", 1)[1].strip()
                    if path == "/" and any(ua in self.AGENT_UAS for ua in current_uas):
                        agent_named_allow = True
                elif line.startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path == "/":
                        if any(ua in self.AGENT_UAS for ua in current_uas):
                            agent_named_block = True
                        if "*" in current_uas:
                            star_block_root = True
                current_uas = []

        if not saw_user_agent:
            # No valid robots directives (e.g. an error page or HTML body).
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No valid robots.txt found",
                findings=[
                    self._make_finding(
                        title="Missing robots.txt",
                        description="No valid robots.txt is published, so the site offers no crawl guidance to agents.",
                        severity=Severity.MEDIUM,
                        recommendation="Publish a robots.txt that allows agents, e.g. 'User-agent: GPTBot\\nAllow: /'.",
                    )
                ],
            )

        if agent_named_block or (star_block_root and not agent_named_allow):
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="robots.txt blocks agents from crawling the site",
                findings=[
                    self._make_finding(
                        title="Robots.txt Blocks Agents",
                        description="robots.txt disallows '/' for agents or all crawlers.",
                        severity=Severity.HIGH,
                        recommendation="Allow agents to crawl: add 'User-agent: GPTBot\\nAllow: /'.",
                    )
                ],
            )
        if agent_named_allow:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="robots.txt explicitly allows AI agents",
            )
        if star_present:
            return self._make_result(
                status=CheckStatus.PASS,
                score=0.75,
                message="robots.txt allows all crawlers (agents permitted, but not explicitly welcomed)",
                findings=[
                    self._make_finding(
                        title="No Explicit Agent Allow",
                        description="Agents are permitted via 'User-agent: *' but not explicitly named.",
                        severity=Severity.LOW,
                        recommendation="Add explicit 'User-agent: GPTBot\\nAllow: /' directives to signal agent-readiness.",
                    )
                ],
            )
        return self._make_result(
            status=CheckStatus.WARN,
            score=0.5,
            message="robots.txt does not address agents or all crawlers",
        )


class SitemapXmlCheck(BaseCheck):
    """Check for a valid sitemap.xml with agent-relevant entries."""

    name: ClassVar[str] = "sitemap_xml"
    category: ClassVar[Category] = Category.DISCOVERY
    weight: ClassVar[float] = 0.10
    description: ClassVar[str] = "Checks for a valid sitemap.xml with agent-relevant entries"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        xml_text = context.sitemap_xml
        if not xml_text:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(f"{context.base_url}/sitemap.xml")
                    if resp.status_code == 200:
                        xml_text = resp.text
            except Exception:
                pass

        if not xml_text:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No sitemap.xml found",
            )

        try:
            root = ET.fromstring(xml_text)
            locs = []
            for elem in root.iter():
                if elem.tag.endswith("loc") and elem.text:
                    locs.append(elem.text.lower())

            keywords = ["/api", "/docs", "/openapi", "/swagger", "/graphql", "/mcp"]
            found_docs = [loc for loc in locs if any(kw in loc for kw in keywords)]

            if found_docs:
                return self._make_result(
                    status=CheckStatus.PASS,
                    score=1.0,
                    message=f"Sitemap is valid XML and contains {len(found_docs)} API/docs URLs",
                    evidence={"locs": locs, "docs_urls": found_docs},
                )
            else:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message="Sitemap is valid XML but contains no API/docs URLs",
                    findings=[
                        self._make_finding(
                            title="Sitemap Missing API/Docs",
                            description="Sitemap does not include links to API documentation or schemas.",
                            severity=Severity.LOW,
                            recommendation="Add API and documentation URLs to sitemap.xml",
                        )
                    ],
                )
        except Exception as e:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message=f"sitemap.xml is not valid XML: {e}",
            )


class WellKnownCrawlCheck(BaseCheck):
    """Check for /.well-known/ crawlability and related discovery files."""

    name: ClassVar[str] = "well_known_crawl"
    category: ClassVar[Category] = Category.DISCOVERY
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks /.well-known/ crawlability and discovery files"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        found = []
        files = {
            "agent-identity.json": "/.well-known/agent-identity.json",
            "agent-pricing.json": "/.well-known/agent-pricing.json",
            "mcp.json": "/.well-known/mcp.json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for name, path in files.items():
                try:
                    resp = await client.get(f"{context.base_url}{path}")
                    if resp.status_code == 200:
                        found.append(name)
                except Exception:
                    pass

        is_pass = len(found) == 3
        score = 1.0 if is_pass else (len(found) / 3.0)

        return self._make_result(
            status=CheckStatus.PASS if is_pass else CheckStatus.FAIL,
            score=score,
            message=f"Discovered well-known files: {', '.join(found)}",
            evidence={"discovered": found, "missing": [f for f in files if f not in found]},
        )


class DnsTxtRecordsCheck(BaseCheck):
    """Check DNS TXT records for agent discovery hints."""

    name: ClassVar[str] = "dns_txt_records"
    category: ClassVar[Category] = Category.DISCOVERY
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks DNS TXT records for agent discovery hints"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        dns_records = context.dns_records or {}
        txt_records = dns_records.get("TXT", [])
        srv_records = dns_records.get("SRV", [])

        has_agent_txt = any(
            "aeo-agent-manifest" in rec or "aeo-mcp-endpoint" in rec for rec in txt_records
        )
        has_agent_srv = len(srv_records) > 0

        if has_agent_txt or has_agent_srv:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="Discovered valid agent/mcp DNS records",
                evidence={"TXT": txt_records, "SRV": srv_records},
            )
        else:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No agent/mcp DNS TXT/SRV records discovered",
                findings=[
                    self._make_finding(
                        title="Missing DNS AEO Records",
                        description="Domain is missing _agent._tcp or _mcp._tcp TXT/SRV records.",
                        severity=Severity.MEDIUM,
                        recommendation="Configure _agent._tcp and _mcp._tcp DNS records for the domain.",
                    )
                ],
            )
