"""Commerce checks for AEO readiness."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, ClassVar

import base58
import httpx
from bs4 import BeautifulSoup
from eth_utils.address import is_address

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


async def _get_pricing_json(context: CheckContext, timeout: float) -> dict[str, Any] | None:
    """Helper to fetch agent pricing JSON from manifest endpoint or well-known fallback."""
    manifest = await _get_manifest(context.base_url, timeout)
    url = None
    if manifest:
        url = manifest.get("pricing_url")

    if not url:
        url = f"{context.base_url}/.well-known/agent-pricing.json"

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


def is_sol_address(addr: str) -> bool:
    """Check if address matches mock Solana format or decodes to valid 32-byte base58 public key."""
    if addr.startswith("SolanaAddress"):
        return True
    try:
        decoded = base58.b58decode(addr)
        return len(decoded) == 32
    except Exception:
        return False


class AgentPricingJsonCheck(BaseCheck):
    """Check for agent-readable pricing information."""

    name: ClassVar[str] = "agent_pricing_json"
    category: ClassVar[Category] = Category.COMMERCE
    weight: ClassVar[float] = 0.30
    description: ClassVar[str] = "Checks for agent-readable pricing information"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        data = await _get_pricing_json(context, self.timeout)
        if not data:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No agent pricing JSON found",
            )

        currency = data.get("currency")
        plans = data.get("plans")

        if not currency and not plans:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="agent-pricing.json is empty or invalid",
                evidence=data,
            )

        if isinstance(currency, str) and isinstance(plans, list) and len(plans) >= 1:
            valid_plans = []
            for plan in plans:
                if isinstance(plan, dict) and ("name" in plan or "id" in plan) and "price" in plan:
                    valid_plans.append(plan)

            if len(valid_plans) >= 1:
                return self._make_result(
                    status=CheckStatus.PASS,
                    score=1.0,
                    message=f"Valid agent-pricing.json found with {len(valid_plans)} plans",
                    evidence=data,
                )

        return self._make_result(
            status=CheckStatus.PASS,
            score=0.5,
            message="agent-pricing.json is minimal (missing plans or currency details)",
            evidence=data,
        )


class StripeCheckoutHintsCheck(BaseCheck):
    """Check for Stripe checkout integration hints."""

    name: ClassVar[str] = "stripe_checkout_hints"
    category: ClassVar[Category] = Category.COMMERCE
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Checks for Stripe checkout integration hints"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        html_lower = context.rendered_html.lower()

        has_stripe = "stripe" in html_lower
        has_price_id = bool(re.search(r"price_[a-zA-Z0-9]+", context.rendered_html)) or "price_id" in html_lower
        has_session_flow = "stripe.checkout.session.create" in html_lower or "success_url" in html_lower or "cancel_url" in html_lower

        if has_stripe and has_price_id and has_session_flow:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="Stripe checkout integration hints found in HTML (session flow and price IDs)",
                evidence={"has_stripe": True, "has_price_id": True, "has_session_flow": True},
            )
        elif has_stripe or has_price_id:
            return self._make_result(
                status=CheckStatus.PASS,
                score=0.5,
                message="Partial Stripe checkout hints found in HTML",
                evidence={"has_stripe": has_stripe, "has_price_id": has_price_id, "has_session_flow": has_session_flow},
            )
        else:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No Stripe checkout integration hints found in HTML",
            )


class CryptoPaymentHintsCheck(BaseCheck):
    """Check for cryptocurrency payment hints and wallet addresses."""

    name: ClassVar[str] = "crypto_payment_hints"
    category: ClassVar[Category] = Category.COMMERCE
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks for cryptocurrency payment hints and wallet addresses"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        methods = []

        # 1. Check HTML meta tags and link tags
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for meta in soup.find_all("meta"):
                name = meta.get("name", "")
                if isinstance(name, list):
                    name = " ".join(name)
                name = str(name).lower()
                content = meta.get("content", "")
                if isinstance(content, list):
                    content = " ".join(content)
                content = str(content).strip()
                if not content:
                    continue

                if name == "ethereum-address" and (is_address(content) or re.match(r"^0x[0-9a-fA-F]{40}$", content)):
                    methods.append({"type": "ethereum", "address": content, "source": "meta"})
                elif name == "solana-address" and (is_sol_address(content) or re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", content)):
                    methods.append({"type": "solana", "address": content, "source": "meta"})
                elif name == "payment-pointer" and (content.startswith("$") or content.startswith("https://")):
                    methods.append({"type": "payment-pointer", "address": content, "source": "meta"})

            for link in soup.find_all("link", rel="payment-pointer"):
                href = link.get("href")
                if href:
                    if isinstance(href, list):
                        href = " ".join(href)
                    href = str(href).strip()
                    methods.append({"type": "payment-pointer", "address": href, "source": "link"})
        except Exception:
            pass

        # 2. Check Link header
        link_hdr = context.response_headers.get("link", "")
        if "payment-pointer" in link_hdr:
            try:
                start = link_hdr.find("<") + 1
                end = link_hdr.find(">")
                if start > 0 and end > start:
                    ptr = link_hdr[start:end]
                    methods.append({"type": "payment-pointer", "address": ptr, "source": "header"})
            except Exception:
                pass

        # 3. Check X-402 headers
        for k, v in context.response_headers.items():
            if k.startswith("x-402") or k == "payment-address":
                methods.append({"type": "custom-header", "address": v, "source": k})

        # 4. Check manifest crypto payment hints
        manifest = await _get_manifest(context.base_url, self.timeout)
        if manifest and "payment_methods" in manifest:
            pm = manifest["payment_methods"]
            if isinstance(pm, dict) and ("crypto" in pm or "ethereum" in pm or "solana" in pm):
                methods.append({"type": "manifest-crypto", "address": str(pm), "source": "manifest"})

        seen = set()
        unique_methods = []
        for m in methods:
            key = (m["type"], m["address"])
            if key not in seen:
                seen.add(key)
                unique_methods.append(m)

        if len(unique_methods) >= 2:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Found {len(unique_methods)} crypto/payment methods with valid formats",
                evidence={"methods": unique_methods},
            )
        elif len(unique_methods) >= 1:
            return self._make_result(
                status=CheckStatus.PASS,
                score=0.5,
                message=f"Found only {len(unique_methods)} crypto/payment method (requires >= 2)",
                evidence={"methods": unique_methods},
            )
        else:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No cryptocurrency payment hints or wallet addresses found",
            )


class UsageMeteringApiCheck(BaseCheck):
    """Check for usage metering API availability."""

    name: ClassVar[str] = "usage_metering_api"
    category: ClassVar[Category] = Category.COMMERCE
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Checks for usage metering API availability"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        urls = []

        # 1. Check manifest
        manifest = await _get_manifest(context.base_url, self.timeout)
        if manifest and "capabilities" in manifest:
            endpoint = manifest["capabilities"].get("metering_endpoint")
            if endpoint:
                urls.append(urllib.parse.urljoin(context.url, endpoint))

        # 2. Fallbacks
        base_url_slash = context.base_url if context.base_url.endswith("/") else context.base_url + "/"
        urls.append(urllib.parse.urljoin(base_url_slash, "usage"))
        urls.append(urllib.parse.urljoin(base_url_slash, "billing/meters"))
        urls.append(urllib.parse.urljoin(base_url_slash, "api/v1/usage"))

        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        metering_data = None
        resolved_url = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for u in unique_urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict):
                            metering_data = data
                            resolved_url = u
                            break
                except Exception:
                    pass

        if not metering_data:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No usage metering API endpoint found or resolved",
            )

        has_usage = "usage" in metering_data or "current_usage" in metering_data
        has_limits = "limits" in metering_data
        has_pricing = "overage_pricing" in metering_data or "pricing" in metering_data

        if has_usage and has_limits and has_pricing:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Valid usage metering API verified at {resolved_url}",
                evidence=metering_data,
            )
        elif has_usage or has_limits or has_pricing:
            return self._make_result(
                status=CheckStatus.PASS,
                score=0.5,
                message=f"Partial usage metering API verified at {resolved_url} (missing some fields)",
                evidence=metering_data,
            )
        else:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="Usage metering endpoint returned invalid schema",
                evidence=metering_data,
            )


class TrialFreemiumSignalsCheck(BaseCheck):
    """Check for trial or freemium access signals."""

    name: ClassVar[str] = "trial_freemium_signals"
    category: ClassVar[Category] = Category.COMMERCE
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks for trial or freemium access signals"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        has_free_tier = False
        has_trial = False
        has_no_cc = False

        # 1. Check manifest pricing
        manifest = await _get_manifest(context.base_url, self.timeout)
        if manifest and "pricing" in manifest:
            pricing = manifest["pricing"]
            if isinstance(pricing, dict):
                if "free_tier" in pricing or pricing.get("price") == 0.0:
                    has_free_tier = True
                if "trial" in pricing or "trial_days" in pricing:
                    has_trial = True

        # 2. Check HTML class structure
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            sig = soup.find(class_="free-tier-signal")
            if sig:
                if sig.get("data-free-tier") == "true":
                    has_free_tier = True
                if sig.get("data-trial-days") or sig.get("data-trial"):
                    has_trial = True
                if sig.get("data-credit-grant") or sig.get("data-no-cc") == "true":
                    has_no_cc = True
        except Exception:
            pass

        # 3. Check HTML text keywords
        html_lower = context.rendered_html.lower()
        if "free tier" in html_lower or "free plan" in html_lower or "freemium" in html_lower:
            has_free_tier = True
        if "free trial" in html_lower or "trial days" in html_lower or "day trial" in html_lower:
            has_trial = True
        if "no credit card" in html_lower or "no cc required" in html_lower:
            has_no_cc = True

        if has_free_tier and has_trial:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="Both free tier and trial signals detected",
                evidence={"free_tier": has_free_tier, "trial": has_trial, "no_credit_card_required": has_no_cc},
            )
        elif has_free_tier or has_trial:
            return self._make_result(
                status=CheckStatus.PASS,
                score=0.5,
                message="Only free tier or trial signals detected",
                evidence={"free_tier": has_free_tier, "trial": has_trial, "no_credit_card_required": has_no_cc},
            )
        else:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No trial or freemium access signals detected",
            )
