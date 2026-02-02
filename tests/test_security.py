"""Tests for security module"""

import pytest
from agent_sdk.security import APIKeyManager, InputSanitizer, PIIFilter
from agent_sdk.exceptions import ValidationError as AgentValidationError


def test_api_key_manager_valid_key(monkeypatch):
    """Test APIKeyManager with valid API key"""
    monkeypatch.setenv("API_KEY", "test-key-12345")
    manager = APIKeyManager()
    assert manager.api_key == "test-key-12345"


def test_api_key_manager_missing_key(monkeypatch):
    """Test APIKeyManager when API key not set"""
    monkeypatch.delenv("API_KEY", raising=False)
    manager = APIKeyManager()
    assert manager.api_key is None


def test_api_key_manager_verify_success(monkeypatch):
    """Test successful API key verification"""
    monkeypatch.setenv("API_KEY", "test-key-12345")
    manager = APIKeyManager()
    assert manager.verify("test-key-12345") is True


def test_api_key_manager_verify_failure(monkeypatch):
    """Test failed API key verification"""
    monkeypatch.setenv("API_KEY", "test-key-12345")
    manager = APIKeyManager()
    assert manager.verify("wrong-key") is False


def test_input_sanitizer_valid_string():
    """Test sanitizer with valid string"""
    sanitizer = InputSanitizer(max_string_length=1000)
    result = sanitizer.sanitize("Hello, world!")
    assert result == "Hello, world!"


def test_input_sanitizer_string_too_long():
    """Test sanitizer rejects overly long string"""
    sanitizer = InputSanitizer(max_string_length=10)
    with pytest.raises(AgentValidationError):
        sanitizer.sanitize("x" * 100)


def test_input_sanitizer_removes_null_bytes():
    """Test sanitizer removes null bytes"""
    sanitizer = InputSanitizer(max_string_length=1000)
    result = sanitizer.sanitize("Hello\x00World")
    assert "\x00" not in result
    assert "HelloWorld" == result


def test_input_sanitizer_dict_valid():
    """Test sanitizer with valid dict"""
    sanitizer = InputSanitizer(max_string_length=1000, max_dict_size=10)
    data = {"key": "value", "count": 42}
    result = sanitizer.sanitize(data)
    assert result == data


def test_input_sanitizer_dict_too_large():
    """Test sanitizer rejects overly large dict"""
    sanitizer = InputSanitizer(max_string_length=1000, max_dict_size=2)
    data = {f"key{i}": f"value{i}" for i in range(10)}
    with pytest.raises(AgentValidationError):
        sanitizer.sanitize(data)


def test_pii_filter_redact_email():
    """Test PII filter redacts email addresses"""
    filter_obj = PIIFilter()
    text = "Contact me at john@example.com for details"
    result = filter_obj.filter_pii(text)
    assert "john@example.com" not in result
    assert "[EMAIL_REDACTED]" in result


def test_pii_filter_redact_phone():
    """Test PII filter redacts phone numbers"""
    filter_obj = PIIFilter()
    text = "Call me at +1-555-0123 anytime"
    result = filter_obj.filter_pii(text)
    assert "555-0123" not in result
    assert "[PHONE_REDACTED]" in result


def test_pii_filter_redact_api_key():
    """Test PII filter redacts API keys"""
    filter_obj = PIIFilter()
    text = "My API key is sk_live_abc123def456"
    result = filter_obj.filter_pii(text)
    assert "sk_live_abc123def456" not in result
    assert "[API_KEY_REDACTED]" in result


def test_pii_filter_redact_dict_field():
    """Test PII filter redacts sensitive fields in dict"""
    filter_obj = PIIFilter()
    data = {
        "username": "john_doe",
        "password": "secret123",
        "api_key": "sk_live_xyz",
        "email": "john@example.com"
    }
    result = filter_obj.filter_pii(data)
    # Sensitive fields should be redacted
    assert result.get("password") == "[REDACTED]"
    assert result.get("api_key") == "[REDACTED]"
    assert "[EMAIL_REDACTED]" in str(result.get("email", ""))


def test_pii_filter_preserve_normal_content():
    """Test PII filter preserves non-sensitive content"""
    filter_obj = PIIFilter()
    text = "The project uses Python and has 50 stars on GitHub"
    result = filter_obj.filter_pii(text)
    assert "Python" in result
    assert "50 stars" in result
