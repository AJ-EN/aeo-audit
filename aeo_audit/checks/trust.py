"""Trust checks for AEO readiness."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, ClassVar

import httpx
from bs4 import BeautifulSoup

from aeo_audit.checks.base import BaseCheck
from aeo_audit.core.models import Category, CheckContext, CheckResult, CheckStatus, Severity


class AuditLogEndpointCheck(BaseCheck):
    """Check for an audit log endpoint."""

    name: ClassVar[str] = "audit_log_endpoint"
    category: ClassVar[Category] = Category.TRUST
    weight: ClassVar[float] = 0.25
    description: ClassVar[str] = "Checks for an audit log endpoint"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        urls = []

        # 1. Parse HTML anchors for audit log link
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href")
                if not href:
                    continue
                text = a.get_text().strip().lower()
                href_str = str(href).lower()
                if "audit-log" in href_str or "audit_log" in href_str or "audit log" in text:
                    urls.append(urllib.parse.urljoin(context.url, str(href)))
        except Exception:
            pass

        # 2. Add standard fallbacks
        base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
        urls.append(urllib.parse.urljoin(base_url_slash, "audit-log"))
        urls.append(urllib.parse.urljoin(base_url_slash, "audit_log"))

        # Deduplicate preserving order
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        resolved_url = None
        data = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in unique_urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, dict) and "entries" in data:
                                resolved_url = u
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

        if resolved_url:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Valid audit log endpoint found at {resolved_url}",
                evidence={"audit_log_url": resolved_url, "data": data},
            )

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="No valid audit log endpoint found",
            findings=[
                self._make_finding(
                    title="Missing Audit Log Endpoint",
                    description="No discoverable or valid audit log endpoint was found at standard locations (e.g. /audit-log).",
                    severity=Severity.MEDIUM,
                    recommendation="Implement a machine-readable audit log endpoint at /audit-log returning JSON with entries.",
                )
            ],
        )


class ReceiptVerificationCheck(BaseCheck):
    """Check for receipt verification capability."""

    name: ClassVar[str] = "receipt_verification"
    category: ClassVar[Category] = Category.TRUST
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Checks for receipt verification capability"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        urls = []

        # 1. Parse HTML anchors for receipt verification links
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href")
                if not href:
                    continue
                text = a.get_text().strip().lower()
                href_str = str(href).lower()
                if "receipt" in href_str or "receipt" in text:
                    urls.append(urllib.parse.urljoin(context.url, str(href)))
        except Exception:
            pass

        # 2. Add standard fallbacks
        base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
        urls.append(urllib.parse.urljoin(base_url_slash, "receipts/verify"))
        urls.append(urllib.parse.urljoin(base_url_slash, "receipt-verification"))

        # Deduplicate preserving order
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        resolved_url = None
        data = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in unique_urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, dict) and ("valid" in data or "proof" in data):
                                resolved_url = u
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

        if resolved_url:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Valid receipt verification endpoint found at {resolved_url}",
                evidence={"receipt_verification_url": resolved_url, "data": data},
            )

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="No valid receipt verification endpoint found",
            findings=[
                self._make_finding(
                    title="Missing Receipt Verification",
                    description="No discoverable or valid receipt verification endpoint was found at standard locations (e.g. /receipts/verify).",
                    severity=Severity.MEDIUM,
                    recommendation="Implement a receipt verification endpoint at /receipts/verify returning JSON proof validation details.",
                )
            ],
        )


class HealthCheckCheck(BaseCheck):
    """Check for a health check endpoint."""

    name: ClassVar[str] = "health_check"
    category: ClassVar[Category] = Category.TRUST
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Checks for a health check endpoint"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        urls = []

        # 1. Parse HTML anchors for health check links
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href")
                if not href:
                    continue
                text = a.get_text().strip().lower()
                href_str = str(href).lower()
                if "health" in href_str or "ready" in href_str or "health" in text or "ready" in text:
                    urls.append(urllib.parse.urljoin(context.url, str(href)))
        except Exception:
            pass

        # 2. Add standard fallbacks
        base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
        urls.append(urllib.parse.urljoin(base_url_slash, "health"))
        urls.append(urllib.parse.urljoin(base_url_slash, "ready"))
        urls.append(urllib.parse.urljoin(base_url_slash, "healthz"))

        # Deduplicate preserving order
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        resolved_url = None
        data = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in unique_urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, dict):
                                status_val = data.get("status")
                                if isinstance(status_val, str) and status_val.lower() in ("healthy", "ok", "operational", "up"):
                                    resolved_url = u
                                    break
                        except Exception:
                            text = resp.text.strip().lower()
                            if text in ("healthy", "ok", "operational", "up"):
                                resolved_url = u
                                break
                except Exception:
                    pass

        if resolved_url:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Valid health check endpoint found at {resolved_url}",
                evidence={"health_check_url": resolved_url, "data": data},
            )

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="No valid or healthy health check endpoint found",
            findings=[
                self._make_finding(
                    title="Missing Health Check",
                    description="No active or healthy health check endpoint was found at standard locations (e.g. /health).",
                    severity=Severity.HIGH,
                    recommendation="Implement a machine-readable health check endpoint at /health returning status: healthy.",
                )
            ],
        )


class StructuredErrorsCheck(BaseCheck):
    """Check for structured error responses."""

    name: ClassVar[str] = "structured_errors"
    category: ClassVar[Category] = Category.TRUST
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Checks for structured error responses"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
        error_urls = [
            urllib.parse.urljoin(base_url_slash, "api/error-rfc7807"),
            urllib.parse.urljoin(base_url_slash, "audit-log"),
            urllib.parse.urljoin(base_url_slash, "health"),
        ]

        active_apis = 0
        unstructured_errors_encountered = 0
        structured_errors_encountered = 0
        evidence_collected: dict[str, Any] = {}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in error_urls:
                try:
                    resp = await client.get(u)
                    status_code = resp.status_code
                    content_type = resp.headers.get("content-type", "").lower()

                    if status_code == 404:
                        # 404 means the endpoint is not present, so we don't count it as a validated error response
                        continue

                    if status_code < 400:
                        # 200 OK means this is an active API endpoint
                        active_apis += 1
                        continue

                    body_text = resp.text
                    is_json = False
                    parsed_json = None
                    try:
                        parsed_json = json.loads(body_text)
                        is_json = True
                    except Exception:
                        pass

                    # RFC 7807 error format checks
                    is_problem_json = "problem+json" in content_type or "problem+yaml" in content_type
                    has_problem_keys = False
                    if is_json and isinstance(parsed_json, dict):
                        keys_to_check = ["type", "title", "detail", "instance", "error", "message", "code"]
                        status_val = parsed_json.get("status")
                        if status_val is not None and not isinstance(status_val, str):
                            keys_to_check.append("status")
                        has_problem_keys = any(k in parsed_json for k in keys_to_check)

                    if is_problem_json or (is_json and has_problem_keys):
                        structured_errors_encountered += 1
                        evidence_collected[u] = {
                            "status_code": status_code,
                            "content_type": content_type,
                            "body": parsed_json,
                            "type": "structured",
                        }
                    else:
                        unstructured_errors_encountered += 1
                        evidence_collected[u] = {
                            "status_code": status_code,
                            "content_type": content_type,
                            "body": body_text[:200],
                            "type": "unstructured",
                        }
                except Exception:
                    pass

        if unstructured_errors_encountered > 0:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="API returned unstructured error responses (non-JSON or missing error metadata)",
                evidence=evidence_collected,
                findings=[
                    self._make_finding(
                        title="Unstructured Error Responses",
                        description="API error endpoints returned unstructured HTML or raw text instead of standard problem details.",
                        severity=Severity.HIGH,
                        recommendation="Update error responses to return application/problem+json matching RFC 7807 specifications.",
                    )
                ],
            )

        if structured_errors_encountered > 0:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Verified structured error responses on {structured_errors_encountered} endpoint(s)",
                evidence=evidence_collected,
            )

        if active_apis > 0:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="No unstructured errors encountered; active API endpoints are operational",
                evidence={"active_apis": active_apis},
            )

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="No API endpoints or structured error responses could be verified",
            findings=[
                self._make_finding(
                    title="No API Error Formatting Verified",
                    description="No active APIs or error responses could be scanned to verify structured error handling.",
                    severity=Severity.MEDIUM,
                    recommendation="Enable API endpoints or mock error responses matching RFC 7807 format for verification.",
                )
            ],
        )


class SlaStatusPageCheck(BaseCheck):
    """Check for an SLA or status page."""

    name: ClassVar[str] = "sla_status_page"
    category: ClassVar[Category] = Category.TRUST
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks for an SLA or status page"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        urls = []

        # 1. Parse HTML anchors for status links
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href")
                if not href:
                    continue
                text = a.get_text().strip().lower()
                href_str = str(href).lower()
                if "status" in href_str or "status" in text:
                    urls.append(urllib.parse.urljoin(context.url, str(href)))
        except Exception:
            pass

        # 2. Add standard fallbacks
        base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
        urls.append(urllib.parse.urljoin(base_url_slash, "status"))
        urls.append(urllib.parse.urljoin(base_url_slash, "status.json"))

        # Deduplicate preserving order
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        resolved_url = None
        data = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in unique_urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, dict) and any(k in data for k in ("status", "incidents", "operational", "state")):
                                resolved_url = u
                                break
                        except Exception:
                            text = resp.text.strip().lower()
                            if any(w in text for w in ("operational", "healthy", "up")):
                                resolved_url = u
                                break
                except Exception:
                    pass

        if resolved_url:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Valid status page found at {resolved_url}",
                evidence={"status_url": resolved_url, "data": data},
            )

        # Fallback to health endpoint status check if status page not found
        health_url = urllib.parse.urljoin(base_url_slash, "health")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(health_url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("status") in ("healthy", "ok", "operational", "up"):
                        return self._make_result(
                            status=CheckStatus.PASS,
                            score=1.0,
                            message="Status page not found, but service health is operational",
                            evidence={"health_fallback": True, "health_data": data},
                        )
        except Exception:
            pass

        return self._make_result(
            status=CheckStatus.FAIL,
            score=0.0,
            message="No SLA status page or active service health endpoint found",
            findings=[
                self._make_finding(
                    title="Missing Uptime and SLA Status Page",
                    description="No discoverable or valid status page or healthy service health check was found.",
                    severity=Severity.MEDIUM,
                    recommendation="Create a public SLA/status JSON page at /status containing uptime or incident details.",
                )
            ],
        )
