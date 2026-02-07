"""Security utilities: authentication, authorization, secrets"""

import os
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Header

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manage API keys for authentication"""

    def __init__(self):
        self.valid_keys = set()
        self.api_key: Optional[str] = None
        self._load_keys()

    def _load_keys(self):
        """Load API keys from environment"""
        api_key = os.getenv("API_KEY")
        if api_key:
            self.api_key = api_key
            self.valid_keys.add(api_key)
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

    def add_key(self, key: str) -> None:
        """Add a new API key to the valid set."""
        if key:
            self.valid_keys.add(key)


_api_key_manager = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create the global API key manager"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """FastAPI dependency for API key verification
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        The verified API key
        
    Raises:
        HTTPException: 401 if key is missing or invalid
    """
    if not x_api_key:
        logger.warning("Request without API key")
        raise HTTPException(status_code=401, detail="Missing API key in X-API-Key header")

    manager = get_api_key_manager()
    if not manager.verify_key(x_api_key):
        logger.warning("Invalid API key attempted")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return x_api_key


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
