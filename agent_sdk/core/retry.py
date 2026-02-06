"""Retry logic with exponential backoff for resilience"""

import asyncio
import inspect
import logging
from typing import Callable, Any, TypeVar, Optional
import time

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    *args,
    **kwargs
) -> Any:
    """Retry function with exponential backoff
    
    Args:
        func: Async or sync function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff (e.g., 2.0 for doubling)
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
        
    Returns:
        Result from successful function call
        
    Raises:
        Exception: Original exception if all retries exhausted
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            
            if attempt < max_retries - 1:
                # Calculate delay with exponential backoff
                wait_time = min(base_delay * (exponential_base ** attempt), max_delay)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    f"All {max_retries} retry attempts failed. "
                    f"Last error: {str(e)}"
                )

    raise last_error or Exception("Max retries exceeded")


def sync_retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    *args,
    **kwargs
) -> Any:
    """Synchronous retry with exponential backoff
    
    Args:
        func: Sync function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
        
    Returns:
        Result from successful function call
        
    Raises:
        Exception: Original exception if all retries exhausted
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            
            if attempt < max_retries - 1:
                # Calculate delay with exponential backoff
                wait_time = min(base_delay * (exponential_base ** attempt), max_delay)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                
                time.sleep(wait_time)
            else:
                logger.error(
                    f"All {max_retries} retry attempts failed. "
                    f"Last error: {str(e)}"
                )

    raise last_error or Exception("Max retries exceeded")


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retryable_exceptions: Optional[tuple] = None,
    ):
        """Initialize retry configuration
        
        Args:
            max_retries: Maximum number of retries
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            retryable_exceptions: Tuple of exception types to retry on (None = all)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions

    def is_retryable(self, exception: Exception) -> bool:
        """Check if exception should be retried
        
        Args:
            exception: Exception to check
            
        Returns:
            True if exception is retryable
        """
        if self.retryable_exceptions is None:
            return True
        return isinstance(exception, self.retryable_exceptions)
