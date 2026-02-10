"""Security utilities: authentication, authorization, secrets"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
import base64
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Depends, Header, Request

logger = logging.getLogger(__name__)
from agent_sdk.secrets import default_secrets_manager


class APIKeyManager:
    """Manage API keys for authentication"""

    def __init__(self):
        self.valid_keys = set()
        self.api_key: Optional[str] = None
        self.key_metadata: Dict[str, "APIKeyInfo"] = {}
        self._rate_limiter = APIKeyRateLimiter()
        self._load_keys()

    def _load_keys(self):
        """Load API keys from environment"""
        secrets = default_secrets_manager()
        api_key = secrets.get("API_KEY")
        if api_key:
            role = secrets.get("API_KEY_ROLE", "admin")
            scopes = secrets.get("API_KEY_SCOPES", "")
            scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
            rate_limit = secrets.get("API_KEY_RATE_LIMIT")
            ip_allowlist = secrets.get("API_KEY_IP_ALLOWLIST", "")
            allowlist = [ip.strip() for ip in ip_allowlist.split(",") if ip.strip()]
            self.api_key = api_key
            self.add_key(
                api_key,
                role=role,
                scopes=scope_list,
                rate_limit_per_minute=int(rate_limit) if rate_limit else None,
                ip_allowlist=allowlist,
            )
            logger.debug("API keys loaded from environment")

    def verify_key(self, key: str) -> bool:
        """Verify if key is valid
        
        Args:
            key: API key to verify
            
        Returns:
            True if key is valid, False otherwise
        """
        if not key:
            return False
        return key in self.valid_keys

    def verify(self, key: str) -> bool:
        """Compatibility alias for verify_key."""
        return self.verify_key(key)

    def add_key(
        self,
        key: str,
        role: str = "developer",
        scopes: Optional[List[str]] = None,
        org_id: str = "default",
        project_id: Optional[str] = None,
        expires_at: Optional[str] = None,
        rate_limit_per_minute: Optional[int] = None,
        ip_allowlist: Optional[List[str]] = None,
    ) -> None:
        """Add a new API key to the valid set."""
        if key:
            self.valid_keys.add(key)
        if scopes:
            effective_scopes = scopes
        else:
            effective_scopes = default_scopes_for_role(role)
        info = APIKeyInfo(
            key=key,
            role=role,
            scopes=effective_scopes,
            org_id=org_id,
            project_id=project_id,
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            ip_allowlist=ip_allowlist or [],
        )
        self.key_metadata[key] = info

    def remove_key(self, key: str) -> None:
        self.valid_keys.discard(key)
        self.key_metadata.pop(key, None)

    def get_key_info(self, key: str) -> Optional["APIKeyInfo"]:
        return self.key_metadata.get(key)

    @staticmethod
    def _is_expired(expires_at: Optional[str]) -> bool:
        if not expires_at:
            return False
        try:
            exp = datetime.fromisoformat(expires_at)
        except ValueError:
            return False
        return exp.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)

    def is_key_active(self, key: str) -> bool:
        info = self.key_metadata.get(key)
        if info is None:
            return False
        return not self._is_expired(info.expires_at)


@dataclass(frozen=True)
class APIKeyInfo:
    key: str
    role: str
    scopes: List[str]
    org_id: str
    project_id: Optional[str] = None
    expires_at: Optional[str] = None
    rate_limit_per_minute: Optional[int] = None
    ip_allowlist: List[str] = field(default_factory=list)


class APIKeyRateLimiter:
    def __init__(self):
        self._window_start: Dict[str, datetime] = {}
        self._counts: Dict[str, int] = {}

    def allow(self, key: str, limit_per_minute: Optional[int]) -> bool:
        if not limit_per_minute or limit_per_minute <= 0:
            return True
        now = datetime.now(timezone.utc)
        window = self._window_start.get(key)
        if window is None or (now - window).total_seconds() >= 60:
            self._window_start[key] = now
            self._counts[key] = 0
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key] <= limit_per_minute


SCOPE_ADMIN = "admin"
SCOPE_RUN_READ = "runs:read"
SCOPE_RUN_WRITE = "runs:write"
SCOPE_SESSION_READ = "sessions:read"
SCOPE_SESSION_WRITE = "sessions:write"
SCOPE_TOOLS_READ = "tools:read"
SCOPE_DEVICE_MANAGE = "devices:manage"
SCOPE_CHANNEL_WRITE = "channels:write"


ROLE_ADMIN = "admin"
ROLE_DEVELOPER = "developer"
ROLE_VIEWER = "viewer"


def default_scopes_for_role(role: str) -> List[str]:
    if role == ROLE_ADMIN:
        return ["*"]
    if role == ROLE_VIEWER:
        return [SCOPE_RUN_READ, SCOPE_SESSION_READ, SCOPE_TOOLS_READ]
    return [
        SCOPE_RUN_READ,
        SCOPE_RUN_WRITE,
        SCOPE_SESSION_READ,
        SCOPE_SESSION_WRITE,
        SCOPE_TOOLS_READ,
        SCOPE_DEVICE_MANAGE,
        SCOPE_CHANNEL_WRITE,
    ]


_api_key_manager = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create the global API key manager"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _verify_jwt(token: str, secret: str) -> Dict[str, Any]:
    header_b64, payload_b64, signature_b64 = token.split(".")
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = _b64url_decode(signature_b64)
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid JWT signature")
    payload = json.loads(_b64url_decode(payload_b64))
    exp = payload.get("exp")
    if exp is not None:
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        if exp_dt <= datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="JWT expired")
    return payload


def _jwt_enabled() -> bool:
    return os.getenv("AGENT_SDK_JWT_ENABLED", "").lower() in {"1", "true", "yes", "on"}


def _get_jwt_secret() -> Optional[str]:
    return os.getenv("AGENT_SDK_JWT_SECRET")


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
) -> str:
    """FastAPI dependency for API key verification
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        The verified API key
        
    Raises:
        HTTPException: 401 if key is missing or invalid
    """
    if _jwt_enabled() and authorization and authorization.lower().startswith("bearer "):
        secret = _get_jwt_secret()
        if not secret:
            raise HTTPException(status_code=500, detail="JWT secret not configured")
        payload = _verify_jwt(authorization.split(" ", 1)[1], secret)
        info = APIKeyInfo(
            key=payload.get("sub", "jwt"),
            role=payload.get("role", ROLE_DEVELOPER),
            scopes=payload.get("scopes") or default_scopes_for_role(payload.get("role", ROLE_DEVELOPER)),
            org_id=payload.get("org_id", "default"),
            project_id=payload.get("project_id"),
            rate_limit_per_minute=payload.get("rate_limit_per_minute"),
            ip_allowlist=payload.get("ip_allowlist") or [],
        )
        if info.ip_allowlist:
            client_ip = request.client.host if request.client else ""
            if client_ip not in info.ip_allowlist:
                raise HTTPException(status_code=403, detail="IP not allowed")
        if not get_api_key_manager()._rate_limiter.allow(info.key, info.rate_limit_per_minute):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return "jwt"

    if not x_api_key:
        logger.warning("Request without API key")
        raise HTTPException(status_code=401, detail="Missing API key in X-API-Key header")

    manager = get_api_key_manager()
    if not manager.verify_key(x_api_key) or not manager.is_key_active(x_api_key):
        logger.warning("Invalid API key attempted")
        raise HTTPException(status_code=401, detail="Invalid API key")
    info = manager.get_key_info(x_api_key)
    if info:
        if info.ip_allowlist:
            client_ip = request.client.host if request.client else ""
            if client_ip not in info.ip_allowlist:
                raise HTTPException(status_code=403, detail="IP not allowed")
        if not manager._rate_limiter.allow(info.key, info.rate_limit_per_minute):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return x_api_key


async def get_api_key_info(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
) -> APIKeyInfo:
    if _jwt_enabled() and authorization and authorization.lower().startswith("bearer "):
        secret = _get_jwt_secret()
        if not secret:
            raise HTTPException(status_code=500, detail="JWT secret not configured")
        payload = _verify_jwt(authorization.split(" ", 1)[1], secret)
        role = payload.get("role", ROLE_DEVELOPER)
        scopes = payload.get("scopes") or default_scopes_for_role(role)
        if isinstance(scopes, str):
            scopes = [s.strip() for s in scopes.split(",") if s.strip()]
        return APIKeyInfo(
            key=payload.get("sub", "jwt"),
            role=role,
            scopes=scopes,
            org_id=payload.get("org_id", "default"),
            project_id=payload.get("project_id"),
            expires_at=None,
            rate_limit_per_minute=payload.get("rate_limit_per_minute"),
            ip_allowlist=payload.get("ip_allowlist") or [],
        )
    if not x_api_key:
        logger.warning("Request without API key")
        raise HTTPException(status_code=401, detail="Missing API key in X-API-Key header")

    manager = get_api_key_manager()
    if not manager.verify_key(x_api_key) or not manager.is_key_active(x_api_key):
        logger.warning("Invalid API key attempted")
        raise HTTPException(status_code=401, detail="Invalid API key")

    info = manager.get_key_info(x_api_key)
    if info is None:
        info = APIKeyInfo(
            key=x_api_key,
            role=ROLE_DEVELOPER,
            scopes=default_scopes_for_role(ROLE_DEVELOPER),
            org_id="default",
            project_id=None,
        )
    return info


def require_scopes(
    scopes: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
):
    async def _dependency(
        key_info: APIKeyInfo = Depends(get_api_key_info),
    ) -> APIKeyInfo:
        if roles and key_info.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        if scopes:
            if "*" in key_info.scopes:
                return key_info
            missing = [scope for scope in scopes if scope not in key_info.scopes]
            if missing:
                raise HTTPException(status_code=403, detail="Forbidden")
        return key_info

    return _dependency


class InputSanitizer:
    """Sanitize inputs to prevent injection"""

    def __init__(self, max_string_length: int = 10000, max_dict_size: int = 100000):
        self.max_string_length = max_string_length
        self.max_dict_size = max_dict_size

    def sanitize(self, value: Any) -> Any:
        """Sanitize input value based on type."""
        from agent_sdk.exceptions import ValidationError

        if isinstance(value, str):
            return self.sanitize_string(value, max_length=self.max_string_length)
        if isinstance(value, dict):
            return self.sanitize_dict(value, max_size=self.max_dict_size)

        raise ValidationError("Unsupported input type", code="VALIDATION_ERROR")

    @staticmethod
    def sanitize_string(value: str, max_length: int = 10000) -> str:
        """Sanitize string input
        
        Args:
            value: String to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
            
        Raises:
            ValueError: If value is invalid
        """
        from agent_sdk.exceptions import ValidationError

        if not isinstance(value, str):
            raise ValidationError("Expected string", code="VALIDATION_ERROR")

        if len(value) > max_length:
            raise ValidationError(
                f"String exceeds max length of {max_length}",
                code="VALIDATION_ERROR",
            )

        # Remove null bytes
        value = value.replace("\x00", "")

        return value.strip()

    @staticmethod
    def sanitize_dict(data: Dict[str, Any], max_size: int = 100000) -> Dict[str, Any]:
        """Sanitize dictionary input
        
        Args:
            data: Dictionary to sanitize
            max_size: Maximum allowed size in bytes
            
        Returns:
            Sanitized dictionary
        """
        from agent_sdk.exceptions import ValidationError

        if len(data) > max_size:
            raise ValidationError(
                f"Dictionary exceeds max size of {max_size} entries",
                code="VALIDATION_ERROR",
            )

        return data


class PIIFilter:
    """Filter out PII from logs and responses"""

    SENSITIVE_FIELDS = {"password", "key", "token", "secret", "api_key", "apikey"}

    @staticmethod
    def filter_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove PII from dictionary
        
        Args:
            data: Dictionary to filter
            
        Returns:
            Dictionary with sensitive fields redacted
        """
        filtered = {}

        for key, value in data.items():
            key_lower = key.lower()

            # Redact sensitive fields
            if any(sensitive in key_lower for sensitive in PIIFilter.SENSITIVE_FIELDS):
                filtered[key] = "[REDACTED]"
            elif isinstance(value, dict):
                filtered[key] = PIIFilter.filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [
                    PIIFilter.filter_dict(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                filtered[key] = value

        return filtered

    @staticmethod
    def filter_string(value: str) -> str:
        """Redact common PII patterns from string
        
        Args:
            value: String to filter
            
        Returns:
            String with PII redacted
        """
        # Simple redaction for common patterns (can be extended)
        import re

        # Redact API keys
        value = re.sub(r"\bsk[-_][a-zA-Z0-9_]+\b", "[API_KEY_REDACTED]", value)
        # Redact email addresses
        value = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "[EMAIL_REDACTED]",
            value,
        )
        # Redact phone numbers
        value = re.sub(
            r"\b\+?\d{1,3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
            "[PHONE_REDACTED]",
            value,
        )

        return value

    def filter_pii(self, value: Any) -> Any:
        """Filter PII in strings and dicts."""
        if isinstance(value, str):
            return self.filter_string(value)
        if isinstance(value, dict):
            filtered = self.filter_dict(value)
            for key, val in list(filtered.items()):
                if isinstance(val, str):
                    filtered[key] = self.filter_string(val)
                elif isinstance(val, dict):
                    filtered[key] = self.filter_pii(val)
                elif isinstance(val, list):
                    filtered[key] = [
                        self.filter_pii(item) if isinstance(item, (dict, str)) else item
                        for item in val
                    ]
            return filtered
        return value
