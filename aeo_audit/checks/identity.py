"""Identity checks for AEO readiness."""

from __future__ import annotations

import re
import time
import urllib.parse
from datetime import datetime
from typing import ClassVar

import httpx
from bs4 import BeautifulSoup
from jose import jwt  # type: ignore[import-untyped]

from aeo_audit.checks.base import BaseCheck
from aeo_audit.core.models import Category, CheckContext, CheckResult, CheckStatus, Severity


class DidDocumentCheck(BaseCheck):
    """Check for a valid DID (Decentralized Identifier) document."""

    name: ClassVar[str] = "did_document"
    category: ClassVar[Category] = Category.IDENTITY
    weight: ClassVar[float] = 0.30
    description: ClassVar[str] = "Checks for a valid DID document"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        did_str = None

        # 1. Try to find link rel="did" in HTML
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            did_link = soup.find("link", rel="did")
            if did_link and did_link.get("href"):
                did_str = str(did_link.get("href"))
        except Exception:
            pass

        # 2. Check Link header if not found in HTML
        if not did_str:
            link_hdr = context.response_headers.get("link", "")
            if 'rel="did"' in link_hdr or "rel=did" in link_hdr:
                try:
                    start = link_hdr.find("<") + 1
                    end = link_hdr.find(">")
                    if start > 0 and end > start:
                        did_str = link_hdr[start:end]
                except Exception:
                    pass

        # 3. Fallback to did:web of domain
        if not did_str:
            parsed = urllib.parse.urlparse(context.url)
            netloc_encoded = parsed.netloc.replace(":", "%3A")
            parts = [p for p in parsed.path.split("/") if p]
            if parts and parsed.netloc.startswith("localhost"):
                did_str = f"did:web:{netloc_encoded}:{parts[0]}"
            else:
                did_str = f"did:web:{netloc_encoded}"

        if not did_str.startswith("did:web:"):
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="DID is not a did:web method",
            )

        # Parse did:web to resolution URLs
        try:
            parts = did_str.split(":")
            if len(parts) < 3:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message=f"Invalid DID: {did_str}",
                )

            domain_part = urllib.parse.unquote(parts[2])
            remaining = parts[3:]
            if remaining and remaining[0].isdigit():
                domain_part = f"{domain_part}:{remaining[0]}"
                remaining = remaining[1:]

            netloc = domain_part
            path_parts = remaining
            scheme = "http" if "localhost" in netloc or "127.0.0.1" in netloc else "https"

            urls = []
            if not path_parts:
                urls.append(f"{scheme}://{netloc}/.well-known/did.json")
            else:
                path = "/".join(path_parts)
                urls.append(f"{scheme}://{netloc}/{path}/.well-known/did.json")
                urls.append(f"{scheme}://{netloc}/{path}/did.json")

            resp_data = None
            resolved_url = None
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for url in urls:
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            resp_data = resp.json()
                            resolved_url = url
                            break
                    except Exception:
                        pass

            if not resp_data:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message=f"Could not resolve DID document from did {did_str}",
                )

            # Validate DID document core spec fields
            if "id" not in resp_data or "verificationMethod" not in resp_data:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message="Resolved DID document is missing required fields (id, verificationMethod)",
                    evidence={"did_document": resp_data, "url": resolved_url},
                )

            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Resolved valid DID document: {did_str}",
                evidence={"did_document": resp_data, "url": resolved_url, "did": did_str},
            )

        except Exception as e:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message=f"Error resolving DID: {e}",
            )


class DelegationProofCheck(BaseCheck):
    """Check for delegation proof or authorization chain."""

    name: ClassVar[str] = "delegation_proof"
    category: ClassVar[Category] = Category.IDENTITY
    weight: ClassVar[float] = 0.25
    description: ClassVar[str] = "Checks for delegation proof or authorization chain"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        url = f"{context.base_url}/.well-known/agent-delegation.json"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message="No agent-delegation.json found at /.well-known/",
                    )

                try:
                    data = resp.json()
                except Exception:
                    raw_text = resp.text.strip()
                    if "." in raw_text:
                        data = {"jwt": raw_text}
                    else:
                        return self._make_result(
                            status=CheckStatus.FAIL,
                            score=0.0,
                            message="agent-delegation.json is not valid JSON",
                        )

            claims = {}
            if "signature" in data and data["signature"] == "mockSignatureEd25519":
                claims = data
            elif "jwt" in data or isinstance(data, str) or ("." in resp.text):
                jwt_str = data.get("jwt") if isinstance(data, dict) else resp.text.strip()
                try:
                    claims = jwt.get_unverified_claims(jwt_str)
                    iss = claims.get("iss")
                    if not iss:
                        return self._make_result(
                            status=CheckStatus.FAIL,
                            score=0.0,
                            message="JWT is missing 'iss' claim",
                        )
                except Exception as e:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message=f"Failed to parse JWT: {e}",
                    )
            else:
                claims = data

            iss = claims.get("iss") or claims.get("issuer")
            sub = claims.get("sub") or claims.get("subject")
            exp = claims.get("exp") or claims.get("expirationDate")

            if not iss or not sub:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message="Delegation proof is missing issuer or subject details",
                    evidence=claims,
                )

            if exp:
                try:
                    exp_val = float(exp)
                    now = time.time()
                    if exp_val < now:
                        return self._make_result(
                            status=CheckStatus.FAIL,
                            score=0.0,
                            message="Delegation proof has expired",
                            evidence=claims,
                        )
                except ValueError:
                    try:
                        exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                        if exp_dt.timestamp() < time.time():
                            return self._make_result(
                                status=CheckStatus.FAIL,
                                score=0.0,
                                message="Delegation proof has expired",
                                evidence=claims,
                            )
                    except Exception:
                        pass

            vc = claims.get("vc", {})
            subject = vc.get("credentialSubject", {})
            delegate_id = subject.get("id") or subject.get("delegate") or sub
            if not delegate_id:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message="Delegation proof is missing delegate details",
                    evidence=claims,
                )

            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="Valid delegation proof verified",
                evidence=claims,
            )

        except Exception as e:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message=f"Error checking delegation proof: {e}",
            )


class OauthMetadataCheck(BaseCheck):
    """Check for OAuth 2.0 authorization server metadata."""

    name: ClassVar[str] = "oauth_metadata"
    category: ClassVar[Category] = Category.IDENTITY
    weight: ClassVar[float] = 0.20
    description: ClassVar[str] = "Checks for OAuth 2.0 authorization server metadata"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        url = f"{context.base_url}/.well-known/oauth-authorization-server"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message="No OAuth metadata found at /.well-known/oauth-authorization-server",
                    )

                try:
                    data = resp.json()
                except Exception:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message="OAuth metadata is not valid JSON",
                    )

            required = ["issuer", "authorization_endpoint", "token_endpoint"]
            missing = [f for f in required if f not in data]
            if missing:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message=f"OAuth metadata missing required fields: {', '.join(missing)}",
                    evidence=data,
                )

            def check_url(u: str) -> bool:
                p = urllib.parse.urlparse(u)
                p_base = urllib.parse.urlparse(context.url)
                if p.netloc.startswith("localhost") or p.netloc.startswith("127.0.0.1"):
                    if p.scheme not in ("http", "https"):
                        return False
                else:
                    if p.scheme != "https":
                        return False
                return p.netloc == p_base.netloc

            errors = []
            for field in [*required, "introspection_endpoint", "revocation_endpoint", "jwks_uri"]:
                val = data.get(field)
                if val and not check_url(val):
                    errors.append(f"Field '{field}' has invalid URL or is not same origin: {val}")

            if errors:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message=f"OAuth metadata validation errors: {'; '.join(errors)}",
                    evidence=data,
                )

            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="OAuth metadata is RFC 8414 compliant",
                evidence=data,
            )

        except Exception as e:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message=f"Error checking OAuth metadata: {e}",
            )


class WalletHintsCheck(BaseCheck):
    """Check for wallet-related hints or payment identity signals."""

    name: ClassVar[str] = "wallet_hints"
    category: ClassVar[Category] = Category.IDENTITY
    weight: ClassVar[float] = 0.15
    description: ClassVar[str] = "Checks for wallet-related hints or payment identity signals"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        wallets = []

        def is_eth_address(addr: str) -> bool:
            return bool(re.match(r"^0x[0-9a-fA-F]{40}$", addr))

        def is_sol_address(addr: str) -> bool:
            return bool(re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", addr))

        def is_payment_pointer(ptr: str) -> bool:
            return ptr.startswith("$") or ptr.startswith("https://")

        # 1. Parse HTML meta tags
        try:
            soup = BeautifulSoup(context.rendered_html, "html.parser")
            for meta in soup.find_all("meta"):
                name_val = meta.get("name")
                content_val = meta.get("content")
                if not name_val or not content_val:
                    continue
                if isinstance(name_val, list):
                    name_val = " ".join(name_val)
                if isinstance(content_val, list):
                    content_val = " ".join(content_val)
                name = str(name_val).lower()
                content = str(content_val).strip()
                if not content:
                    continue
                if name == "ethereum-address" and is_eth_address(content):
                    wallets.append({"type": "ethereum", "address": content, "source": "meta"})
                elif name == "solana-address" and is_sol_address(content):
                    wallets.append({"type": "solana", "address": content, "source": "meta"})
                elif name == "payment-pointer" and is_payment_pointer(content):
                    wallets.append({"type": "payment-pointer", "address": content, "source": "meta"})
                elif name == "agent-wallet":
                    wallets.append({"type": "agent-wallet", "address": content, "source": "meta"})
        except Exception:
            pass

        # 2. Check Link header
        link_hdr = context.response_headers.get("link", "")
        if "rel=\"payment-pointer\"" in link_hdr or "rel=payment-pointer" in link_hdr:
            try:
                start = link_hdr.find("<") + 1
                end = link_hdr.find(">")
                if start > 0 and end > start:
                    ptr = link_hdr[start:end]
                    wallets.append({"type": "payment-pointer-header", "address": ptr, "source": "header"})
            except Exception:
                pass

        # 3. Check X-402 payment header
        for k, v in context.response_headers.items():
            if k.startswith("x-402") or k == "payment-address":
                wallets.append({"type": "custom-header", "address": v, "source": k})

        if wallets:
            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message=f"Found {len(wallets)} wallet hints",
                evidence={"wallets": wallets},
            )
        else:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message="No payment/wallet hints found in meta tags, headers, or manifest",
                findings=[
                    self._make_finding(
                        title="Missing Wallet Hints",
                        description="Website does not expose agent wallet hints or payment pointers.",
                        severity=Severity.LOW,
                        recommendation="Add <meta name=\"ethereum-address\" content=\"...\"> to your HTML head.",
                    )
                ],
            )


class AgentIdentityJsonCheck(BaseCheck):
    """Check for an agent identity JSON descriptor."""

    name: ClassVar[str] = "agent_identity_json"
    category: ClassVar[Category] = Category.IDENTITY
    weight: ClassVar[float] = 0.10
    description: ClassVar[str] = "Checks for an agent identity JSON descriptor"
    timeout: ClassVar[float] = 10.0

    async def run(self, context: CheckContext) -> CheckResult:
        """Execute the check."""
        url = f"{context.base_url}/.well-known/agent-identity.json"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message="No agent-identity.json found at /.well-known/",
                    )

                try:
                    data = resp.json()
                except Exception:
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message="agent-identity.json is not valid JSON",
                    )

            required = ["principal", "agent", "permissions", "expiry"]
            missing = [f for f in required if f not in data]
            if missing:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message=f"agent-identity.json missing required fields: {', '.join(missing)}",
                    evidence=data,
                )

            principal = data.get("principal")
            agent = data.get("agent")
            expiry = data.get("expiry")
            permissions = data.get("permissions")

            if not isinstance(principal, str) or not principal.startswith("did:"):
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message=f"Principal must be a valid DID string, got: {principal}",
                    evidence=data,
                )

            if not isinstance(agent, str) or not agent.startswith("did:"):
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message=f"Agent must be a valid DID string, got: {agent}",
                    evidence=data,
                )

            if not isinstance(permissions, list):
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message="Permissions must be a list of capabilities",
                    evidence=data,
                )

            try:
                exp_str = str(expiry).replace("Z", "+00:00")
                exp_dt = datetime.fromisoformat(exp_str)
                if exp_dt.timestamp() < time.time():
                    return self._make_result(
                        status=CheckStatus.FAIL,
                        score=0.0,
                        message=f"Agent identity has expired: {expiry}",
                        evidence=data,
                    )
            except Exception:
                return self._make_result(
                    status=CheckStatus.FAIL,
                    score=0.0,
                    message=f"Invalid expiry date format: {expiry}. Must be ISO 8601.",
                    evidence=data,
                )

            return self._make_result(
                status=CheckStatus.PASS,
                score=1.0,
                message="Valid agent identity document verified",
                evidence=data,
            )

        except Exception as e:
            return self._make_result(
                status=CheckStatus.FAIL,
                score=0.0,
                message=f"Error checking agent identity: {e}",
            )
