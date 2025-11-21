"""
API Utilities for Rate Limiting and Retry Logic
Provides rate limiting and exponential backoff for external API calls
"""
import time
import threading
import logging
from typing import Callable, Any, Optional
from functools import wraps
from config.settings import GeminiConfig, AppSettings

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class RateLimiter:
    """Token bucket rate limiter for API calls"""

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Token buckets
        self.minute_tokens = requests_per_minute
        self.hour_tokens = requests_per_hour

        # Last refill times
        self.last_minute_refill = time.time()
        self.last_hour_refill = time.time()

        # Thread safety
        self.lock = threading.Lock()

    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()

        # Refill minute tokens
        minute_elapsed = now - self.last_minute_refill
        minute_tokens_to_add = minute_elapsed * (self.requests_per_minute / 60.0)
        self.minute_tokens = min(self.requests_per_minute, self.minute_tokens + minute_tokens_to_add)
        self.last_minute_refill = now

        # Refill hour tokens
        hour_elapsed = now - self.last_hour_refill
        hour_tokens_to_add = hour_elapsed * (self.requests_per_hour / 3600.0)
        self.hour_tokens = min(self.requests_per_hour, self.hour_tokens + hour_tokens_to_add)
        self.last_hour_refill = now

    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the rate limiter

        Args:
            tokens: Number of tokens to acquire (default 1)

        Returns:
            True if tokens acquired, False if rate limited
        """
        with self.lock:
            self._refill_tokens()

            if self.minute_tokens >= tokens and self.hour_tokens >= tokens:
                self.minute_tokens -= tokens
                self.hour_tokens -= tokens
                return True

            return False

    def wait_for_tokens(self, tokens: int = 1, timeout: float = 300.0) -> bool:
        """
        Wait until tokens are available or timeout

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait in seconds

        Returns:
            True if tokens acquired, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.acquire(tokens):
                return True

            # Wait a bit before checking again
            time.sleep(0.1)

        return False

class ExponentialBackoff:
    """Exponential backoff retry logic"""

    def __init__(self, max_retries: int = 3, initial_delay: float = 1.0,
                 max_delay: float = 60.0, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with exponential backoff retry

        Args:
            func: Function to retry
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = min(self.initial_delay * (self.backoff_factor ** attempt), self.max_delay)
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {str(e)}")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed: {str(e)}")
                    raise last_exception

# Global rate limiter instance for Gemini API
_gemini_rate_limiter = RateLimiter(
    requests_per_minute=GeminiConfig.RATE_LIMIT_REQUESTS_PER_MINUTE,
    requests_per_hour=GeminiConfig.RATE_LIMIT_REQUESTS_PER_HOUR
)

# Global backoff instance for Gemini API
_gemini_backoff = ExponentialBackoff(
    max_retries=GeminiConfig.MAX_RETRIES,
    initial_delay=GeminiConfig.INITIAL_RETRY_DELAY,
    max_delay=GeminiConfig.MAX_RETRY_DELAY
)

def with_gemini_rate_limit(func: Callable) -> Callable:
    """
    Decorator to apply Gemini API rate limiting

    Args:
        func: Function to decorate

    Returns:
        Decorated function with rate limiting
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _gemini_rate_limiter.wait_for_tokens(tokens=1, timeout=300.0):
            raise Exception("Rate limit timeout exceeded")

        logger.debug("Rate limit acquired for Gemini API call")
        return func(*args, **kwargs)

    return wrapper

def with_gemini_retry(func: Callable) -> Callable:
    """
    Decorator to apply exponential backoff retry for Gemini API calls

    Args:
        func: Function to decorate

    Returns:
        Decorated function with retry logic
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return _gemini_backoff.retry(func, *args, **kwargs)

    return wrapper

def with_gemini_rate_limit_and_retry(func: Callable) -> Callable:
    """
    Decorator to apply both rate limiting and retry logic for Gemini API calls

    Args:
        func: Function to decorate

    Returns:
        Decorated function with rate limiting and retry
    """
    return with_gemini_rate_limit(with_gemini_retry(func))

# Utility functions for manual use
def wait_for_gemini_rate_limit(tokens: int = 1, timeout: float = 300.0) -> bool:
    """Wait for Gemini API rate limit tokens"""
    return _gemini_rate_limiter.wait_for_tokens(tokens=tokens, timeout=timeout)

def retry_gemini_call(func: Callable, *args, **kwargs) -> Any:
    """Retry a Gemini API call with exponential backoff"""
    return _gemini_backoff.retry(func, *args, **kwargs)

# HTTP retry utilities for OMI API
class HTTPRetry:
    """HTTP retry logic with exponential backoff"""

    def __init__(self, max_retries: int = 3, initial_delay: float = 1.0,
                 max_delay: float = 30.0, backoff_factor: float = 2.0,
                 retry_status_codes: Optional[set] = None):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retry_status_codes = retry_status_codes or {429, 500, 502, 503, 504}

    def retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute HTTP function with exponential backoff retry

        Args:
            func: Function that returns a requests.Response object
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result (requests.Response)

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                response = func(*args, **kwargs)

                # Check if we should retry based on status code
                if response.status_code in self.retry_status_codes:
                    if attempt < self.max_retries:
                        delay = min(self.initial_delay * (self.backoff_factor ** attempt), self.max_delay)
                        logger.warning(f"HTTP {response.status_code} on attempt {attempt + 1}, retrying in {delay:.2f}s")
                        time.sleep(delay)
                        continue

                # For successful responses or non-retryable errors, return immediately
                return response

            except Exception as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = min(self.initial_delay * (self.backoff_factor ** attempt), self.max_delay)
                    logger.warning(f"HTTP request failed on attempt {attempt + 1}, retrying in {delay:.2f}s: {str(e)}")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"All {self.max_retries + 1} HTTP attempts failed: {str(e)}")
                    raise last_exception

# Global HTTP retry instance for OMI API
_omi_http_retry = HTTPRetry()

def with_omi_retry(func: Callable) -> Callable:
    """
    Decorator to apply HTTP retry logic for OMI API calls

    Args:
        func: Function to decorate

    Returns:
        Decorated function with retry logic
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return _omi_http_retry.retry(func, *args, **kwargs)

    return wrapper