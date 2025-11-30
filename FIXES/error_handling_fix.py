"""
PATCH 3: Error Handling & Logging
Fixes:
  - ADD custom exception hierarchy
  - ADD proper exception handling in all critical paths
  - ADD structured logging with context
  - ADD error recovery mechanisms
  - ADD circuit breaker pattern for external API calls
  - ADD proper cleanup on errors
"""

import logging
import functools
import time
from typing import Optional, Dict, Any, Callable, TypeVar, cast
from datetime import datetime, timezone, timedelta
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


# ============ CUSTOM EXCEPTION HIERARCHY ============

class AngelMemoryException(Exception):
    """Base exception for Angel Memory system"""

    def __init__(self, message: str, error_code: str, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dict for logging/API responses"""
        return {
            "error": self.error_code,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp
        }


class OMIAPIError(AngelMemoryException):
    """OMI API communication error"""
    pass


class OMIAuthenticationError(OMIAPIError):
    """OMI authentication/authorization error"""
    pass


class OMIRateLimitError(OMIAPIError):
    """OMI rate limit exceeded"""
    pass


class GeminiAPIError(AngelMemoryException):
    """Gemini API error"""
    pass


class MemoryStoreError(AngelMemoryException):
    """Memory store operation error"""
    pass


class MemoryNotFoundError(MemoryStoreError):
    """Memory not found in store"""
    pass


class ValidationError(AngelMemoryException):
    """Input validation error"""
    pass


class ConfigurationError(AngelMemoryException):
    """Configuration error"""
    pass


class WebhookError(AngelMemoryException):
    """Webhook processing error"""
    pass


# ============ CIRCUIT BREAKER PATTERN ============

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for API calls"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, success_threshold: int = 2):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before trying to recover
            success_threshold: Successful calls needed to close
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None

    def record_success(self) -> None:
        """Record successful call"""
        self.failure_count = 0

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.success_count = 0
                logger.info("Circuit breaker recovered and closed")

    def record_failure(self) -> None:
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0
            logger.warning("Circuit breaker re-opened during recovery")

    def is_available(self) -> bool:
        """Check if circuit is available for requests"""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                    logger.info("Circuit breaker entering recovery mode")
                    return True
            return False

        # HALF_OPEN - allow single request
        return True

    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


# ============ RETRY MECHANISMS ============

class RetryConfig:
    """Retry configuration"""

    def __init__(self, max_attempts: int = 3, initial_delay: float = 1.0,
                 max_delay: float = 60.0, exponential_base: float = 2.0):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff"""
        delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
        return min(delay, self.max_delay)


def with_retry(retry_config: Optional[RetryConfig] = None, retriable_exceptions: tuple = (Exception,)):
    """
    Decorator for retrying function with exponential backoff

    Args:
        retry_config: Retry configuration
        retriable_exceptions: Tuple of exceptions to retry on
    """
    if retry_config is None:
        retry_config = RetryConfig()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(1, retry_config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retriable_exceptions as e:
                    last_exception = e
                    if attempt < retry_config.max_attempts:
                        delay = retry_config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt} failed, retrying in {delay}s",
                            extra={"error": str(e), "attempt": attempt, "function": func.__name__}
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {retry_config.max_attempts} attempts failed",
                            extra={"error": str(e), "function": func.__name__}
                        )

            raise last_exception or Exception("Unknown error")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(1, retry_config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retriable_exceptions as e:
                    last_exception = e
                    if attempt < retry_config.max_attempts:
                        delay = retry_config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt} failed, retrying in {delay}s",
                            extra={"error": str(e), "attempt": attempt, "function": func.__name__}
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {retry_config.max_attempts} attempts failed",
                            extra={"error": str(e), "function": func.__name__}
                        )

            raise last_exception or Exception("Unknown error")

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


# ============ CONTEXT MANAGERS FOR ERROR HANDLING ============

class ErrorContext:
    """Context manager for error handling and cleanup"""

    def __init__(self, operation_name: str, context: Optional[Dict[str, Any]] = None):
        self.operation_name = operation_name
        self.context = context or {}
        self.start_time = datetime.now(timezone.utc)

    def __enter__(self) -> 'ErrorContext':
        logger.info(f"Starting operation: {self.operation_name}", extra=self.context)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        if exc_type is None:
            logger.info(
                f"Operation completed: {self.operation_name}",
                extra={"duration_seconds": duration, **self.context}
            )
            return False

        if isinstance(exc_val, AngelMemoryException):
            logger.error(
                f"Operation failed: {self.operation_name}",
                extra={
                    "duration_seconds": duration,
                    "error_code": exc_val.error_code,
                    "error_message": exc_val.message,
                    "error_context": exc_val.context,
                    **self.context
                }
            )
        else:
            logger.error(
                f"Operation failed with unexpected error: {self.operation_name}",
                extra={
                    "duration_seconds": duration,
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val),
                    **self.context
                },
                exc_info=True
            )

        return False  # Re-raise exception


# ============ STRUCTURED LOGGING UTILITIES ============

def log_request(method: str, url: str, user_id: Optional[str] = None, params: Optional[Dict] = None):
    """Log API request"""
    logger.debug(
        f"API Request: {method} {url}",
        extra={
            "method": method,
            "url": url,
            "user_id": user_id,
            "params_count": len(params) if params else 0
        }
    )


def log_response(status_code: int, duration_ms: float, response_size: int, user_id: Optional[str] = None):
    """Log API response"""
    logger.debug(
        f"API Response: {status_code}",
        extra={
            "status_code": status_code,
            "duration_ms": duration_ms,
            "response_size_bytes": response_size,
            "user_id": user_id
        }
    )


def log_error_with_context(error: Exception, context: Dict[str, Any], severity: str = "error"):
    """Log error with structured context"""
    logger.log(
        logging.ERROR if severity == "error" else logging.WARNING,
        f"{severity.upper()}: {str(error)}",
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            **context
        },
        exc_info=True if severity == "error" else False
    )


# ============ GRACEFUL DEGRADATION ============

class FallbackHandler:
    """Handles fallback operations when primary service fails"""

    @staticmethod
    def get_cached_result(cache_key: str, cache: Dict[str, Any]) -> Optional[Any]:
        """Get cached result from previous successful operation"""
        if cache_key in cache:
            logger.info(f"Using cached result for {cache_key}")
            return cache[cache_key]
        return None

    @staticmethod
    def get_default_response(operation: str) -> Dict[str, Any]:
        """Get sensible default response for degraded mode"""
        defaults = {
            "memory_analysis": {
                "status": "degraded",
                "message": "Analysis unavailable, using cached insights",
                "analysis": None,
                "cached": True
            },
            "memory_creation": {
                "status": "queued",
                "message": "Creating memory in background",
                "queued": True
            },
            "api_call": {
                "status": "unavailable",
                "message": "Service temporarily unavailable",
                "retry_after": 60
            }
        }
        return defaults.get(operation, {"status": "degraded"})
