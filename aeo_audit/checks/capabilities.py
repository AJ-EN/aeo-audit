"""Capabilities checks for AEO readiness."""

from __future__ import annotations

import contextlib
import json
import urllib.parse
from typing import Any, ClassVar

import httpx
import yaml
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from openapi_spec_validator import validate_spec

from aeo_audit.checks.base import BaseCheck
from aeo_audit.core.models import Category, CheckContext, CheckResult, CheckStatus


async def _get_manifest(base_url: str, timeout: float) -> dict[str, Any] | None:
    """Helper to fetch agent manifest if it exists."""
    for url in [f"{base_url}/.well-known/agent-manifest.json", f"{base_url}/.well-known/agent.json"]:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
    return None


class OpenApiSpecCheck(BaseCheck):
    """Check for a valid OpenAPI specification."""

    name: ClassVar[str] = "openapi_spec"
    category: ClassVar[Category] = Category.CAPABILITIES
    weight: ClassVar[float] = 0.25
    description: ClassVar[str] = "Checks for a valid OpenAPI specification"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        urls = []

        # 1. Check Link header describedby
        link_hdr = context.response_headers.get("link", "")
        if "describedby" in link_hdr:
            parts = link_hdr.split(",")
            for part in parts:
                if 'rel="describedby"' in part or "rel=describedby" in part:
                    try:
                        start = part.find("<") + 1
                        end = part.find(">")
                        if start > 0 and end > start:
                            urls.append(urllib.parse.urljoin(context.url, part[start:end]))
                    except Exception:
                        pass

        # 2. Check HTML link rel="describedby" or anchors
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for link in soup.find_all("link", rel="describedby"):
                if link.get("href"):
                    urls.append(urllib.parse.urljoin(context.url, str(link.get("href"))))

            for a in soup.find_all("a"):
                href_val = a.get("href")
                if not href_val:
                    continue
                if isinstance(href_val, list):
                    href_val = " ".join(href_val)
                href = str(href_val)
                if "openapi" in href.lower() or "swagger" in href.lower() or "api-docs" in href.lower() or a.get_text().strip().lower() == "openapi spec":
                    urls.append(urllib.parse.urljoin(context.url, href))
        except Exception:
            pass

        # 3. Check manifest capabilities
        manifest = await _get_manifest(context.base_url, self.timeout)
        if manifest and "capabilities" in manifest:
            spec_url = manifest["capabilities"].get("openapi_spec")
            if spec_url:
                urls.append(urllib.parse.urljoin(context.url, spec_url))

        # 4. Fallbacks
        base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
        urls.append(urllib.parse.urljoin(base_url_slash, "openapi.json"))
        urls.append(urllib.parse.urljoin(base_url_slash, "swagger.json"))
        urls.append(urllib.parse.urljoin(base_url_slash, "api-docs"))

        # Deduplicate preserving order
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        validated_spec = None
        resolved_url = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in unique_urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code != 200:
                        continue
                    text = resp.text
                    spec_dict = None
                    with contextlib.suppress(Exception):
                        spec_dict = json.loads(text)
                    if spec_dict is None:
                        with contextlib.suppress(Exception):
                            spec_dict = yaml.safe_load(text)

                    if isinstance(spec_dict, dict) and "openapi" in spec_dict:
                        validate_spec(spec_dict)
                        validated_spec = spec_dict
                        resolved_url = u
                        break
                except Exception:
                    pass

        if validated_spec:
            components = validated_spec.get("components", {})
            has_schemas = "schemas" in components
            has_security = "security" in validated_spec or "securitySchemes" in components

            if has_schemas and has_security:
                return self._make_result(
                    status=CheckStatus.PASS,
                    score=1.0,
                    message=f"Valid OpenAPI specification found at {resolved_url}",
                    evidence={"openapi_url": resolved_url, "spec": validated_spec},
                )
            else:
                return self._make_result(
                    status=CheckStatus.PASS,
                    score=0.5,
                    message=f"Valid OpenAPI specification found at {resolved_url} but missing schemas or security definitions",
                    evidence={"openapi_url": resolved_url, "spec": validated_spec},
                )

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="No valid OpenAPI specification found",
        )


class McpToolsListCheck(BaseCheck):
    """Check for a discoverable MCP tools list."""

    name: ClassVar[str] = "mcp_tools_list"
    category: ClassVar[Category] = Category.CAPABILITIES
    weight: ClassVar[float] = 0.25
    description: ClassVar[str] = "Checks for a discoverable MCP tools list"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        mcp_url = None

        # 1. Check Link header mcp
        link_hdr = context.response_headers.get("link", "")
        if "mcp" in link_hdr:
            parts = link_hdr.split(",")
            for part in parts:
                if 'rel="mcp"' in part or "rel=mcp" in part:
                    try:
                        start = part.find("<") + 1
                        end = part.find(">")
                        if start > 0 and end > start:
                            mcp_url = urllib.parse.urljoin(context.url, part[start:end])
                    except Exception:
                        pass

        # 2. Check HTML link rel="mcp"
        if not mcp_url:
            try:
                soup = BeautifulSoup(context.rendered_html, "html.parser")
                link_tag = soup.find("link", rel="mcp")
                if link_tag and link_tag.get("href"):
                    mcp_url = urllib.parse.urljoin(context.url, str(link_tag.get("href")))
            except Exception:
                pass

        # 3. Check DNS TXT records
        if not mcp_url:
            for txt in context.dns_records.get("TXT", []):
                if txt.startswith("aeo-mcp-endpoint="):
                    mcp_url = urllib.parse.urljoin(context.url, txt.split("=", 1)[1])
                    break

        # 4. Check manifest capabilities
        if not mcp_url:
            manifest = await _get_manifest(context.base_url, self.timeout)
            if manifest and "capabilities" in manifest:
                endpoint = manifest["capabilities"].get("mcp_endpoint")
                if endpoint:
                    mcp_url = urllib.parse.urljoin(context.url, endpoint)

        # 5. Fallback
        if not mcp_url:
            base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
            mcp_url = urllib.parse.urljoin(base_url_slash, "mcp")

        if not mcp_url:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No MCP endpoint found in Link header, HTML, DNS, or manifest",
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Handshake
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "aeo-audit", "version": "0.1.0"},
                    },
                }
                resp = await client.post(
                    mcp_url,
                    json=init_payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message=f"MCP handshake failed at {mcp_url} with status code {resp.status_code}",
                    )

                # Fetch Tools List
                tools_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                }
                resp = await client.post(
                    mcp_url,
                    json=tools_payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message=f"MCP tools/list call failed with status code {resp.status_code}",
                    )

                data = resp.json()
                if "error" in data:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message=f"MCP tools/list returned error: {data['error']}",
                    )

                tools = data.get("result", {}).get("tools", [])
                valid_tools = []
                for t in tools:
                    if (
                        isinstance(t, dict)
                        and "name" in t
                        and isinstance(t["name"], str)
                        and "description" in t
                        and isinstance(t["description"], str)
                        and "inputSchema" in t
                        and isinstance(t["inputSchema"], dict)
                    ):
                        valid_tools.append(t)

                if len(valid_tools) >= 3:
                    return self._make_result(
                        status=CheckStatus.PASS,
                        score=1.0,
                        message=f"Resolved MCP endpoint: {mcp_url} exposing {len(valid_tools)} valid tools",
                        evidence={"tools": valid_tools, "mcp_url": mcp_url},
                    )
                elif len(valid_tools) >= 1:
                    return self._make_result(
                        status=CheckStatus.PASS,
                        score=0.5,
                        message=f"Resolved MCP endpoint: {mcp_url} but found only {len(valid_tools)} valid tools (requires >= 3)",
                        evidence={"tools": valid_tools, "mcp_url": mcp_url},
                    )
                else:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message="MCP endpoint did not expose any valid tools",
                        evidence={"tools": tools, "mcp_url": mcp_url},
                    )

        except Exception as e:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message=f"Error communicating with MCP endpoint at {mcp_url}: {e}",
            )


class JsonSchemaEndpointsCheck(BaseCheck):
    """Check for JSON Schema-described API endpoints."""

    name: ClassVar[str] = "json_schema_endpoints"
    category: ClassVar[Category] = Category.CAPABILITIES
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Checks for JSON Schema-described API endpoints"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        schema_urls = []

        # 1. Check HTML link rel="describedby"
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for link in soup.find_all("link", rel="describedby"):
                if link.get("href"):
                    schema_urls.append(urllib.parse.urljoin(context.url, str(link.get("href"))))
        except Exception:
            pass

        # 2. Check Link header describedby
        link_hdr = context.response_headers.get("link", "")
        if "describedby" in link_hdr:
            parts = link_hdr.split(",")
            for part in parts:
                if 'rel="describedby"' in part or "rel=describedby" in part:
                    try:
                        start = part.find("<") + 1
                        end = part.find(">")
                        if start > 0 and end > start:
                            schema_urls.append(urllib.parse.urljoin(context.url, part[start:end]))
                    except Exception:
                        pass

        # Deduplicate
        seen = set()
        unique_urls = []
        for u in schema_urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        if not unique_urls:
            # If site is not minimal, let's search manifest or fallback to /schemas/order.json
            manifest = await _get_manifest(context.base_url, self.timeout)
            if manifest:
                # Non-minimal fallback
                base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
                unique_urls.append(urllib.parse.urljoin(base_url_slash, "schemas/order.json"))
            else:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message="No JSON Schema links or headers found",
                )

        valid_count = 0
        total_count = len(unique_urls)
        details = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in unique_urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code == 200:
                        schema_dict = resp.json()
                        Draft202012Validator.check_schema(schema_dict)
                        valid_count += 1
                        details.append({"url": u, "valid": True})
                    else:
                        details.append({"url": u, "valid": False, "error": f"Status code {resp.status_code}"})
                except Exception as e:
                    details.append({"url": u, "valid": False, "error": str(e)})

        score = valid_count / total_count if total_count > 0 else 0.0
        status = CheckStatus.PASS if score > 0.0 else CheckStatus.FAIL

        return self._make_result(
            status=status,
            score=score,
            message=f"Valid JSON Schemas: {valid_count}/{total_count}",
            evidence={"schemas": details},
        )


class GraphqlIntrospectionCheck(BaseCheck):
    """Check for GraphQL introspection endpoint availability."""

    name: ClassVar[str] = "graphql_introspection"
    category: ClassVar[Category] = Category.CAPABILITIES
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks for GraphQL introspection endpoint availability"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        urls = []

        # 1. Check manifest
        manifest = await _get_manifest(context.base_url, self.timeout)
        if manifest and "capabilities" in manifest:
            endpoint = manifest["capabilities"].get("graphql_endpoint")
            if endpoint:
                urls.append(urllib.parse.urljoin(context.url, endpoint))

        # 2. Check HTML for graphql links
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for a in soup.find_all("a"):
                href_val = a.get("href")
                if not href_val:
                    continue
                if isinstance(href_val, list):
                    href_val = " ".join(href_val)
                href = str(href_val)
                if "graphql" in href.lower():
                    urls.append(urllib.parse.urljoin(context.url, href))
        except Exception:
            pass

        # 3. Fallback
        base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
        urls.append(urllib.parse.urljoin(base_url_slash, "graphql"))

        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        introspection_query = {
            "query": "{ __schema { types { name description fields { name type { kind name } } } } }"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in unique_urls:
                try:
                    resp = await client.post(
                        u,
                        json=introspection_query,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if "data" in data and "__schema" in data["data"]:
                            schema = data["data"]["__schema"]
                            types = schema.get("types", [])
                            has_descriptions = any(
                                isinstance(t, dict) and t.get("description")
                                for t in types
                            )

                            score = 1.0 if has_descriptions else 0.5
                            msg = (
                                f"GraphQL Introspection succeeded at {u} with type descriptions"
                                if has_descriptions
                                else f"GraphQL Introspection succeeded at {u} but missing type descriptions"
                            )
                            return self._make_result(
                                status=CheckStatus.PASS,
                                score=score,
                                message=msg,
                                evidence={"graphql_url": u, "response": data},
                            )
                except Exception:
                    pass

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="GraphQL introspection endpoint not found or query blocked",
        )


class AsyncWebhooksCheck(BaseCheck):
    """Check for async webhook support and configuration."""

    name: ClassVar[str] = "async_webhooks"
    category: ClassVar[Category] = Category.CAPABILITIES
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks for async webhook support and configuration"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        # 1. Check manifest webhooks field
        manifest = await _get_manifest(context.base_url, self.timeout)
        if manifest and "webhooks" in manifest:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="Webhooks documented in agent manifest",
                evidence={"webhooks": manifest["webhooks"]},
            )

        # 2. Check HTML for webhook documentation
        html_lower = context.rendered_html.lower()
        if "webhook" in html_lower:
            has_events = "event" in html_lower or "order.created" in html_lower
            has_retry = "retry" in html_lower or "backoff" in html_lower
            has_sig = (
                "signature" in html_lower
                or "hmac" in html_lower
                or "x-webhook-signature" in html_lower
            )

            if has_events and has_retry and has_sig:
                return self._make_result(
                    status=CheckStatus.PASS,
                    score=1.0,
                    message="Webhooks fully documented in HTML (event types, retry policy, and signature)",
                    evidence={"html_contains_webhooks": True},
                )
            elif has_events or has_retry or has_sig:
                return self._make_result(
                    status=CheckStatus.PASS,
                    score=0.5,
                    message="Webhooks partially documented in HTML",
                    evidence={"events": has_events, "retry": has_retry, "signature": has_sig},
                )

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="No async webhook support or documentation found",
        )
