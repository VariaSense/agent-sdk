"""Identity provider interfaces and mock implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import json
import os

try:
    import jwt  # type: ignore
except Exception:  # pragma: no cover - optional
    jwt = None


@dataclass(frozen=True)
class IdentityClaims:
    subject: str
    email: Optional[str] = None
    issuer: Optional[str] = None
    groups: list[str] = field(default_factory=list)
    raw: Dict[str, str] = field(default_factory=dict)


class IdentityProvider:
    """Abstract identity provider interface."""

    def validate(self, token: str) -> IdentityClaims:
        raise NotImplementedError


class MockIdentityProvider(IdentityProvider):
    """Accepts tokens formatted as JSON payloads for tests."""

    def validate(self, token: str) -> IdentityClaims:
        if token.startswith("mock:"):
            token = token.split("mock:", 1)[1]
        data = json.loads(token)
        return IdentityClaims(
            subject=data.get("sub", "unknown"),
            email=data.get("email"),
            issuer=data.get("iss"),
            groups=data.get("groups", []),
            raw={k: str(v) for k, v in data.items()},
        )


class OIDCProvider(IdentityProvider):
    """OIDC provider with mockable validation."""

    def __init__(self, issuer: Optional[str] = None, audience: Optional[str] = None):
        self.issuer = issuer or os.getenv("AGENT_SDK_OIDC_ISSUER")
        self.audience = audience or os.getenv("AGENT_SDK_OIDC_AUDIENCE")
        self.shared_secret = os.getenv("AGENT_SDK_OIDC_SHARED_SECRET")

    def validate(self, token: str) -> IdentityClaims:
        if token.startswith("mock:"):
            return MockIdentityProvider().validate(token)
        if jwt is None:
            raise RuntimeError("pyjwt is required for OIDC token validation")
        options = {"verify_aud": bool(self.audience)}
        payload = jwt.decode(
            token,
            key=self.shared_secret,
            algorithms=["HS256"],
            audience=self.audience,
            options=options,
        )
        return IdentityClaims(
            subject=payload.get("sub", "unknown"),
            email=payload.get("email"),
            issuer=payload.get("iss"),
            groups=payload.get("groups", []),
            raw={k: str(v) for k, v in payload.items()},
        )


class SAMLProvider(IdentityProvider):
    """SAML provider with mockable validation."""

    def validate(self, token: str) -> IdentityClaims:
        if token.startswith("mock:"):
            return MockIdentityProvider().validate(token)
        raise RuntimeError("SAML validation requires external integration")
