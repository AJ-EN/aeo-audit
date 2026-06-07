"""Mock AEO Server for integration testing.

Serves static and dynamic endpoints for test sites on port 8765.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import yaml

PORT = 8765
MOCK_SITES_DIR = Path(__file__).parent / "mock_sites"


class MockAEOHandler(BaseHTTPRequestHandler):
    """HTTP Handler representing the mock AEO server."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress stdout logs from the server during tests."""
        pass

    def _send_response(self, status: int, headers: dict[str, str], body: bytes) -> None:
        """Helper to send HTTP response."""
        self.send_response(status)
        for key, val in headers.items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(body)

    def _get_site_and_endpoint(self) -> tuple[str, str]:
        """Extract site name and inner endpoint from path."""
        parts = [p for p in self.path.split("/") if p]
        if not parts:
            return "", ""
        site = parts[0]
        endpoint = "/" + "/".join(parts[1:]) if len(parts) > 1 else "/"
        return site, endpoint

    def _load_config(self, site: str) -> dict[str, Any]:
        """Load site config.yaml if it exists."""
        config_path = MOCK_SITES_DIR / site / "config.yaml"
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {}

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS request for CORS."""
        self._send_response(
            204,
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Link",
            },
            b"",
        )

    def do_GET(self) -> None:
        """Handle GET requests."""
        site, endpoint = self._get_site_and_endpoint()
        if not site:
            self._send_response(
                200,
                {"Content-Type": "text/html"},
                b"<html><body><h1>Mock AEO Server</h1></body></html>",
            )
            return

        config = self._load_config(site)

        # Check for matching config rule first
        endpoints_config = config.get("endpoints", {})
        if endpoint in endpoints_config:
            rule = endpoints_config[endpoint]
            if rule.get("method", "GET").upper() == "GET":
                self._serve_config_rule(site, rule)
                return

        # Attempt to serve static files
        clean_endpoint = endpoint.lstrip("/")
        if clean_endpoint == "":
            clean_endpoint = "index.html"
        static_file = MOCK_SITES_DIR / site / clean_endpoint

        if static_file.exists() and static_file.is_file():
            content_type = "text/plain"
            if static_file.suffix == ".html":
                content_type = "text/html"
            elif static_file.suffix == ".json":
                content_type = "application/json"
            elif static_file.suffix == ".xml":
                content_type = "application/xml"
            elif static_file.suffix == ".txt":
                content_type = "text/plain"

            # Check if there are default headers for this site
            resp_headers = {
                "Content-Type": content_type,
                "Access-Control-Allow-Origin": "*",
            }
            # Add custom site headers if perfect site etc.
            if site in ("perfect", "broken_mcp", "no_pricing", "no_trust") and endpoint == "/":
                resp_headers["Link"] = f'<http://localhost:{PORT}/{site}/mcp>; rel="mcp"'

            # Also allow config to override headers for static files
            if endpoint in endpoints_config:
                resp_headers.update(endpoints_config[endpoint].get("headers", {}))

            try:
                body = static_file.read_bytes()
                if static_file.suffix == ".html" and site in ("broken_mcp", "no_pricing", "no_trust", "missing_manifest"):
                    html_str = body.decode("utf-8")
                    
                    # 1. Inject Discovery & Identity tags
                    # ONLY inject DID and wallet hints for non-missing_manifest sites
                    discovery_identity_inject = ""
                    if site != "missing_manifest":
                        discovery_identity_inject = f"""
    <!-- Identity: DID Link and Wallet Hints -->
    <link rel="did" href="did:web:localhost:8765:{site}">
    <meta name="ethereum-address" content="0x1234567890123456789012345678901234567890">
    <meta name="solana-address" content="SolanaAddress111111111111111111111111111">
    <meta name="payment-pointer" content="$ilp.uphold.com/{site}-pointer">
"""
                    
                    # Inject MCP and DescribedBy (which are capabilities / discovery)
                    capabilities_inject = ""
                    if site != "missing_manifest":
                        capabilities_inject = f"""
    <!-- Capabilities: MCP and DescribedBy Link headers -->
    <link rel="mcp" href="/{site}/mcp">
    <link rel="describedby" href="/{site}/schemas/order.json">
"""
                    
                    head_inject = discovery_identity_inject + capabilities_inject
                    if "</head>" in html_str:
                        html_str = html_str.replace("</head>", f"{head_inject}</head>")
                    else:
                        html_str = html_str + head_inject

                    # Inject commerce info in body
                    commerce_inject = ""
                    if site in ("broken_mcp", "no_pricing", "no_trust"):
                        commerce_inject = """
    <!-- Commerce: Stripe Checkout Hints, Trial, and Crypto Hints -->
    <div id="pricing">
        <h2>Pricing &amp; Checkout</h2>
        <p>Start a 14-day free trial (no credit card required). Free tier includes 100 free requests.</p>
        <p>Upgrade to Pro using stripe.checkout.session.create with price_id: "price_123".</p>
        <p>Crypto payments accepted at ethereum-address 0x1234567890123456789012345678901234567890 or USDC Address.</p>
        <span class="free-tier-signal" data-free-tier="true" data-trial-days="14" data-credit-grant="10.0"></span>
    </div>
"""

                    # Inject webhook / api docs info in body
                    body_inject = ""
                    if site != "missing_manifest":
                        body_inject = f"""
    <!-- Capabilities: Webhooks and API info -->
    <div id="developer-docs">
        <h2>Developer API</h2>
        <p>API docs: <a href="/{site}/openapi.json">OpenAPI Spec</a></p>
        <p>GraphQL endpoint: <a href="/{site}/graphql">GraphQL Playground</a></p>
        <p>We support asynchronous webhooks. Register your endpoint at `/webhooks`. Supported event types: `order.created`, `payment.succeeded`. All webhooks include a signature verification header `X-Webhook-Signature`. If your webhook fails, we retry up to 5 times with exponential backoff.</p>
    </div>
"""
                    body_inject = commerce_inject + body_inject
                    if "</body>" in html_str:
                        html_str = html_str.replace("</body>", f"{body_inject}</body>")
                    else:
                        html_str = html_str + body_inject

                    body = html_str.encode("utf-8")
                self._send_response(200, resp_headers, body)
                return
            except Exception as e:
                self._send_response(
                    500,
                    {"Content-Type": "text/plain"},
                    f"Internal Server Error: {e}".encode("utf-8"),
                )
                return

        # Dynamic fallback endpoints
        self._serve_dynamic_fallback(site, endpoint, "GET")

    def do_POST(self) -> None:
        """Handle POST requests."""
        site, endpoint = self._get_site_and_endpoint()
        if not site:
            self._send_response(404, {"Content-Type": "text/plain"}, b"Not Found")
            return

        config = self._load_config(site)
        endpoints_config = config.get("endpoints", {})

        # Check config rule
        if endpoint in endpoints_config:
            rule = endpoints_config[endpoint]
            if rule.get("method", "GET").upper() == "POST":
                self._serve_config_rule(site, rule)
                return

        # Read POST request body
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""

        # Intercept MCP requests
        if endpoint == "/mcp":
            self._handle_mcp_post(site, post_data)
            return

        # Dynamic fallback endpoints
        self._serve_dynamic_fallback(site, endpoint, "POST", post_data)

    def _serve_config_rule(self, site: str, rule: dict[str, Any]) -> None:
        """Serve responses defined in site config.yaml."""
        status = rule.get("status", 200)
        headers = rule.get("headers", {})
        if "Access-Control-Allow-Origin" not in headers:
            headers["Access-Control-Allow-Origin"] = "*"

        body = b""
        if "body" in rule:
            body = rule["body"].encode("utf-8")
        elif "body_file" in rule:
            body_file_path = MOCK_SITES_DIR / site / rule["body_file"]
            if body_file_path.exists():
                body = body_file_path.read_bytes()

        self._send_response(status, headers, body)

    def _handle_mcp_post(self, site: str, post_data: bytes) -> None:
        """Handle dynamic MCP JSON-RPC protocol requests."""
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        }

        # If site is broken_mcp, return 500 or malformed JSON
        if site == "broken_mcp":
            self._send_response(500, headers, b"Internal Server Error: MCP endpoint broken")
            return

        try:
            req = json.loads(post_data.decode("utf-8"))
            msg_id = req.get("id")
            method = req.get("method")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                        },
                        "serverInfo": {
                            "name": "Mock AEO Server",
                            "version": "1.0.0",
                        },
                    },
                }
                self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
                return

            elif method == "tools/list":
                # If site doesn't support capabilities, return empty tools list
                if site in ("minimal",):
                    resp = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "tools": [],
                        },
                    }
                    self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
                    return

                # Normal tools list (>= 3 tools with inputSchema, description)
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [
                          {
                            "name": "search_products",
                            "description": "Search for products by query",
                            "inputSchema": {
                              "type": "object",
                              "properties": {
                                "query": {"type": "string"}
                              },
                              "required": ["query"]
                            },
                          },
                          {
                            "name": "get_pricing",
                            "description": "Get current pricing plans",
                            "inputSchema": {
                              "type": "object",
                              "properties": {}
                            },
                          },
                          {
                            "name": "create_order",
                            "description": "Create a new purchase order",
                            "inputSchema": {
                              "type": "object",
                              "properties": {
                                "product_id": {"type": "string"},
                                "quantity": {"type": "integer"}
                              },
                              "required": ["product_id", "quantity"]
                            },
                          }
                        ]
                    }
                }
                self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
                return

            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                }
                self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
                return

        except Exception as e:
            self._send_response(
                400,
                headers,
                json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}}).encode("utf-8"),
            )

    def _serve_dynamic_fallback(
        self, site: str, endpoint: str, method: str, post_data: bytes = b""
    ) -> None:
        """Default dynamic behaviors for AEO A11y / Trust / Introspection endpoints."""
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        }

        # If site is minimal, everything is 404
        if site == "minimal":
            self._send_response(404, headers, b'{"error": "Not Found"}')
            return

        # Discovery robots.txt
        if endpoint == "/robots.txt":
            body = "User-agent: *\nDisallow:\n"
            if site in ("perfect", "broken_mcp", "no_pricing", "no_trust"):
                body = "User-agent: agent\nAllow: /\nUser-agent: GPTBot\nAllow: /\n"
            elif site == "missing_manifest":
                body = "User-agent: *\nDisallow: /\n"
            self._send_response(200, {"Content-Type": "text/plain"}, body.encode("utf-8"))
            return

        # Discovery sitemap.xml
        if endpoint == "/sitemap.xml":
            if site in ("perfect", "broken_mcp", "no_pricing", "no_trust"):
                body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <url>
      <loc>http://localhost:8765/{site}/</loc>
      <lastmod>2026-06-07</lastmod>
   </url>
   <url>
      <loc>http://localhost:8765/{site}/api</loc>
      <lastmod>2026-06-07</lastmod>
   </url>
</urlset>"""
            else:
                body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <url>
      <loc>http://localhost:8765/{site}/</loc>
      <lastmod>2026-06-07</lastmod>
   </url>
</urlset>"""
            self._send_response(200, {"Content-Type": "application/xml"}, body.encode("utf-8"))
            return

        # Discovery and Identity well-known files fallback
        if endpoint in (
            "/.well-known/agent-identity.json",
            "/.well-known/mcp.json",
            "/.well-known/agent-pricing.json",
            "/.well-known/did.json",
            "/.well-known/agent-delegation.json",
            "/.well-known/oauth-authorization-server",
            "/openapi.json"
        ):
            allowed_sites = ("perfect", "broken_mcp", "no_pricing", "no_trust")

            if site in allowed_sites:
                filename = endpoint.split("/")[-1]
                if filename == "oauth-authorization-server":
                    filename = "oauth-authorization-server.json"
                file_path = MOCK_SITES_DIR / site / filename
                if not file_path.exists():
                    file_path = MOCK_SITES_DIR / "perfect" / filename
                if file_path.exists():
                    body = file_path.read_bytes()
                    body_str = body.decode("utf-8").replace("perfect", site)
                    self._send_response(200, headers, body_str.encode("utf-8"))
                    return

        # Capabilities GraphQL Introspection
        if endpoint == "/graphql":
            resp = {
                "data": {
                    "__schema": {
                        "types": [
                            {
                                "name": "Query",
                                "kind": "OBJECT",
                                "description": "Root query",
                                "fields": [],
                            }
                        ]
                    }
                }
            }
            self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
            return

        # JSON Schema fallback
        if endpoint == "/schemas/order.json":
            if site in ("perfect", "broken_mcp", "no_pricing", "no_trust"):
                resp = {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": "Order",
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "quantity": {"type": "integer"}
                    }
                }
                self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
                return

        # Commerce /usage fallback
        if endpoint in ("/usage", "/api/v1/usage"):
            if site in ("perfect", "broken_mcp", "no_pricing", "no_trust"):
                resp = {
                    "usage": {
                        "requests": 1500,
                        "tokens": 450000
                    },
                    "limits": {
                        "requests_limit": 5000,
                        "tokens_limit": 1000000
                    },
                    "overage_pricing": {
                        "requests_per_1k": 0.10,
                        "tokens_per_1m": 2.00
                    }
                }
                self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
                return

        # Trust /health
        if endpoint == "/health" or endpoint == "/ready":
            if site == "no_trust":
                self._send_response(500, headers, b'{"status": "unhealthy"}')
                return
            resp = {
                "status": "healthy",
                "checks": {"database": "up", "cache": "up"},
                "latency_p99": 45.2,
                "error_rate": 0.001,
            }
            self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
            return

        # Trust /audit-log
        if endpoint == "/audit-log":
            if site == "no_trust":
                # Return unstructured / non-problem details error if trust failures
                self._send_response(500, {"Content-Type": "text/html"}, b"Error 500")
                return
            resp = {
                "entries": [
                    {
                        "id": 1,
                        "action": "payment",
                        "amount": 100,
                        "hash": "abc123hash",
                        "signature": "sig123",
                    }
                ],
                "merkle_root": "merkle123root",
                "next_page": None,
            }
            self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
            return

        # Trust /receipts/verify
        if endpoint == "/receipts/verify":
            if site == "no_trust":
                self._send_response(404, headers, b"Not Found")
                return
            resp = {
                "valid": True,
                "proof": ["sibling1", "sibling2"],
            }
            self._send_response(200, headers, json.dumps(resp).encode("utf-8"))
            return

        # Fallback 404
        self._send_response(404, headers, b'{"error": "Not Found"}')


def run_server(port: int = PORT) -> None:
    """Run the mock server (blocking)."""
    server = ThreadingHTTPServer(("localhost", port), MockAEOHandler)
    server.serve_forever()


if __name__ == "__main__":
    print(f"Starting AEO Mock Server on http://localhost:{PORT}/")
    run_server()
