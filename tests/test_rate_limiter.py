"""Tests for rate limiter"""

import pytest
import time
from threading import Thread
from agent_sdk.config.rate_limit import RateLimiter
from agent_sdk.exceptions import RateLimitError


def test_rate_limiter_allows_requests_within_limit():
    """Test rate limiter allows requests within limit"""
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    
    # Should allow 5 requests
    for i in range(5):
        result = limiter.check()
        assert result is True


def test_rate_limiter_rejects_requests_exceeding_limit():
    """Test rate limiter rejects requests exceeding limit"""
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    
    # Allow 3 requests
    for i in range(3):
        limiter.check()
    
    # Fourth request should raise RateLimitError
    with pytest.raises(RateLimitError):
        limiter.check()


def test_rate_limiter_window_resets():
    """Test rate limiter resets after window expires"""
    limiter = RateLimiter(max_requests=2, window_seconds=1)
    
    # Use up limit
    limiter.check()
    limiter.check()
    
    # Should be rate limited
    with pytest.raises(RateLimitError):
        limiter.check()
    
    # Wait for window to expire
    time.sleep(1.1)
    
    # Should allow request again
    result = limiter.check()
    assert result is True


def test_rate_limiter_get_remaining():
    """Test get_remaining reports correct count"""
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    
    limiter.check()
    limiter.check()
    
    remaining = limiter.get_remaining()
    assert remaining == 3


def test_rate_limiter_thread_safe():
    """Test rate limiter is thread-safe with concurrent requests"""
    limiter = RateLimiter(max_requests=100, window_seconds=60)
    results = []
    errors = []
    
    def make_request():
        try:
            limiter.check()
            results.append(True)
        except RateLimitError:
            errors.append(True)
    
    # Create 50 threads making requests concurrently
    threads = [Thread(target=make_request) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All 50 requests should succeed (within limit of 100)
    assert len(results) == 50
    assert len(errors) == 0


def test_rate_limiter_thread_safe_at_boundary():
    """Test rate limiter is thread-safe when hitting limit"""
    limiter = RateLimiter(max_requests=20, window_seconds=60)
    results = []
    errors = []
    
    def make_request():
        try:
            limiter.check()
            results.append(True)
        except RateLimitError:
            errors.append(True)
    
    # Create 40 threads making requests concurrently
    # Only 20 should succeed, 20 should fail
    threads = [Thread(target=make_request) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Exactly 20 should succeed, 20 should fail
    assert len(results) == 20
    assert len(errors) == 20


def test_rate_limiter_reset():
    """Test manual reset of rate limiter"""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    
    limiter.check()
    limiter.check()
    
    # Should be rate limited
    with pytest.raises(RateLimitError):
        limiter.check()
    
    # Reset
    limiter.reset()
    
    # Should allow request again
    result = limiter.check()
    assert result is True


def test_rate_limiter_get_status():
    """Test get_status returns correct info"""
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    
    limiter.check()
    limiter.check()
    
    status = limiter.get_status()
    assert status["max_requests"] == 5
    assert status["current_requests"] == 2
    assert status["remaining"] == 3
