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
        self._load_keys()

    def _load_keys(self):
        """Load API keys from environment"""
        api_key = os.getenv("API_KEY")
        if api_key:
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
        if not isinstance(value, str):
            raise ValueError("Expected string")

        if len(value) > max_length:
            raise ValueError(f"String exceeds max length of {max_length}")

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
        if len(str(data)) > max_size:
            raise ValueError(f"Dictionary exceeds max size of {max_size} bytes")

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
        value = re.sub(r"sk-[a-zA-Z0-9]+", "[API_KEY]", value)
        # Redact email addresses
        value = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", value
        )
        # Redact phone numbers
        value = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", value)

        return value
