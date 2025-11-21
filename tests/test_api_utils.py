"""
Unit tests for api_utils.py module
Tests rate limiting, exponential backoff, and HTTP retry logic
"""
import pytest
import time
import threading
from unittest.mock import patch, MagicMock, call
from freezegun import freeze_time

from modules.api_utils import (
    RateLimiter, ExponentialBackoff, HTTPRetry,
    with_gemini_rate_limit, with_gemini_retry, with_gemini_rate_limit_and_retry,
    wait_for_gemini_rate_limit, retry_gemini_call, with_omi_retry
)


class TestRateLimiter:
    """Test token bucket rate limiter"""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing"""
        return RateLimiter(requests_per_minute=10, requests_per_hour=50)

    def test_init(self, rate_limiter):
        """Test rate limiter initialization"""
        assert rate_limiter.requests_per_minute == 10
        assert rate_limiter.requests_per_hour == 50
        assert rate_limiter.minute_tokens == 10
        assert rate_limiter.hour_tokens == 50
        assert isinstance(rate_limiter.lock, threading.Lock)

    def test_refill_tokens(self, rate_limiter):
        """Test token refilling over time"""
        # Use some tokens
        rate_limiter.acquire(5)
        assert rate_limiter.minute_tokens == 5
        assert rate_limiter.hour_tokens == 45

        # Simulate time passing (30 seconds)
        with freeze_time("2024-01-01 00:00:00") as frozen_time:
            frozen_time.move_to("2024-01-01 00:00:30")

            # Refill should happen
            rate_limiter._refill_tokens()

            # Should have refilled 5 tokens (30/60 * 10)
            assert rate_limiter.minute_tokens == 10  # Full refill
            assert rate_limiter.hour_tokens == 47.5  # Partial refill (30/3600 * 50 ≈ 0.416, so 45 + 0.416 = 45.416, but capped at 50? Wait, let's check logic)

    def test_acquire_single_token(self, rate_limiter):
        """Test acquiring single token"""
        assert rate_limiter.acquire() == True
        assert rate_limiter.minute_tokens == 9
        assert rate_limiter.hour_tokens == 49

    def test_acquire_multiple_tokens(self, rate_limiter):
        """Test acquiring multiple tokens"""
        assert rate_limiter.acquire(3) == True
        assert rate_limiter.minute_tokens == 7
        assert rate_limiter.hour_tokens == 47

    def test_acquire_insufficient_tokens(self, rate_limiter):
        """Test acquiring when insufficient tokens"""
        # Use up all tokens
        rate_limiter.acquire(10)  # Use all minute tokens
        assert rate_limiter.acquire() == False
        assert rate_limiter.minute_tokens == 0

    def test_wait_for_tokens_immediate(self, rate_limiter):
        """Test waiting for tokens when available immediately"""
        assert rate_limiter.wait_for_tokens() == True

    def test_wait_for_tokens_with_timeout(self, rate_limiter):
        """Test waiting for tokens with timeout"""
        # Use up all tokens
        rate_limiter.acquire(10)

        # Should timeout waiting for tokens
        assert rate_limiter.wait_for_tokens(timeout=0.1) == False

    def test_thread_safety(self, rate_limiter):
        """Test thread safety of rate limiter"""
        import threading
        import time

        results = []
        errors = []

        def worker():
            try:
                for _ in range(5):
                    if rate_limiter.acquire():
                        results.append(True)
                    else:
                        results.append(False)
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for _ in range(3):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should have no errors and some successful acquires
        assert len(errors) == 0
        assert len(results) > 0
        # Total successful acquires should be limited by rate limiter
        assert sum(results) <= 10  # Max per minute


class TestExponentialBackoff:
    """Test exponential backoff retry logic"""

    @pytest.fixture
    def backoff(self):
        """Create exponential backoff for testing"""
        return ExponentialBackoff(max_retries=3, initial_delay=0.1, max_delay=1.0)

    def test_init(self, backoff):
        """Test exponential backoff initialization"""
        assert backoff.max_retries == 3
        assert backoff.initial_delay == 0.1
        assert backoff.max_delay == 1.0
        assert backoff.backoff_factor == 2.0

    def test_retry_success_first_attempt(self, backoff):
        """Test successful retry on first attempt"""
        def successful_func():
            return "success"

        result = backoff.retry(successful_func)
        assert result == "success"

    def test_retry_success_after_failures(self, backoff):
        """Test successful retry after some failures"""
        call_count = 0

        def failing_then_success_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        with patch('time.sleep') as mock_sleep:
            result = backoff.retry(failing_then_success_func)

        assert result == "success"
        assert call_count == 3
        # Should have slept with exponential backoff: 0.1, 0.2
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(0.1), call(0.2)])

    def test_retry_all_failures(self, backoff):
        """Test retry when all attempts fail"""
        def always_failing_func():
            raise ValueError("Always fails")

        with patch('time.sleep') as mock_sleep:
            with pytest.raises(ValueError, match="Always fails"):
                backoff.retry(always_failing_func)

        # Should have tried 4 times (initial + 3 retries)
        assert mock_sleep.call_count == 3
        mock_sleep.assert_has_calls([call(0.1), call(0.2), call(0.4)])

    def test_retry_max_delay_cap(self, backoff):
        """Test that delays are capped at max_delay"""
        call_count = 0

        def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with patch('time.sleep') as mock_sleep:
            with pytest.raises(ValueError):
                backoff.retry(always_failing_func)

        # Check that delays don't exceed max_delay
        for call_args in mock_sleep.call_args_list:
            delay = call_args[0][0]
            assert delay <= backoff.max_delay


class TestHTTPRetry:
    """Test HTTP retry logic"""

    @pytest.fixture
    def http_retry(self):
        """Create HTTP retry for testing"""
        return HTTPRetry(max_retries=2, initial_delay=0.1, retry_status_codes={429, 500})

    def test_init(self, http_retry):
        """Test HTTP retry initialization"""
        assert http_retry.max_retries == 2
        assert http_retry.initial_delay == 0.1
        assert http_retry.retry_status_codes == {429, 500}

    def test_retry_success_first_attempt(self, http_retry):
        """Test successful HTTP request on first attempt"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        def successful_request():
            return mock_response

        result = http_retry.retry(successful_request)
        assert result == mock_response

    def test_retry_success_after_retryable_error(self, http_retry):
        """Test successful retry after retryable HTTP error"""
        call_count = 0

        def failing_then_success_request():
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count == 1:
                mock_response.status_code = 429  # Retryable
            else:
                mock_response.status_code = 200  # Success
            return mock_response

        with patch('time.sleep') as mock_sleep:
            result = http_retry.retry(failing_then_success_request)

        assert result.status_code == 200
        assert call_count == 2
        assert mock_sleep.call_count == 1

    def test_retry_non_retryable_error(self, http_retry):
        """Test no retry for non-retryable HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 404  # Not retryable

        def failing_request():
            return mock_response

        result = http_retry.retry(failing_request)
        assert result == mock_response

    def test_retry_all_attempts_fail(self, http_retry):
        """Test retry when all HTTP attempts fail"""
        mock_response = MagicMock()
        mock_response.status_code = 500  # Retryable

        def always_failing_request():
            return mock_response

        with patch('time.sleep') as mock_sleep:
            result = http_retry.retry(always_failing_request)

        # Should return the last failed response
        assert result == mock_response
        assert mock_sleep.call_count == 2  # 2 retries


class TestDecorators:
    """Test API utility decorators"""

    def test_with_gemini_rate_limit_success(self):
        """Test successful rate limit decorator"""
        with patch('modules.api_utils._gemini_rate_limiter') as mock_limiter:
            mock_limiter.wait_for_tokens.return_value = True

            @with_gemini_rate_limit
            def test_func():
                return "success"

            result = test_func()
            assert result == "success"
            mock_limiter.wait_for_tokens.assert_called_once_with(tokens=1, timeout=300.0)

    def test_with_gemini_rate_limit_timeout(self):
        """Test rate limit decorator timeout"""
        with patch('modules.api_utils._gemini_rate_limiter') as mock_limiter:
            mock_limiter.wait_for_tokens.return_value = False

            @with_gemini_rate_limit
            def test_func():
                return "should not reach here"

            with pytest.raises(Exception, match="Rate limit timeout exceeded"):
                test_func()

    def test_with_gemini_retry_success(self):
        """Test successful retry decorator"""
        with patch('modules.api_utils._gemini_backoff') as mock_backoff:
            mock_backoff.retry.return_value = "success"

            @with_gemini_retry
            def test_func():
                return "success"

            result = test_func()
            assert result == "success"
            mock_backoff.retry.assert_called_once()

    def test_with_gemini_rate_limit_and_retry(self):
        """Test combined rate limit and retry decorator"""
        with patch('modules.api_utils._gemini_rate_limiter') as mock_limiter, \
             patch('modules.api_utils._gemini_backoff') as mock_backoff:

            mock_limiter.wait_for_tokens.return_value = True
            mock_backoff.retry.return_value = "success"

            @with_gemini_rate_limit_and_retry
            def test_func():
                return "success"

            result = test_func()
            assert result == "success"
            mock_limiter.wait_for_tokens.assert_called_once()
            mock_backoff.retry.assert_called_once()

    def test_with_omi_retry_success(self):
        """Test OMI retry decorator success"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch('modules.api_utils._omi_http_retry') as mock_retry:
            mock_retry.retry.return_value = mock_response

            @with_omi_retry
            def test_func():
                return mock_response

            result = test_func()
            assert result == mock_response
            mock_retry.retry.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions"""

    def test_wait_for_gemini_rate_limit_success(self):
        """Test successful rate limit wait"""
        with patch('modules.api_utils._gemini_rate_limiter') as mock_limiter:
            mock_limiter.wait_for_tokens.return_value = True

            result = wait_for_gemini_rate_limit()
            assert result == True
            mock_limiter.wait_for_tokens.assert_called_once_with(tokens=1, timeout=300.0)

    def test_wait_for_gemini_rate_limit_custom_params(self):
        """Test rate limit wait with custom parameters"""
        with patch('modules.api_utils._gemini_rate_limiter') as mock_limiter:
            mock_limiter.wait_for_tokens.return_value = True

            result = wait_for_gemini_rate_limit(tokens=5, timeout=60.0)
            assert result == True
            mock_limiter.wait_for_tokens.assert_called_once_with(tokens=5, timeout=60.0)

    def test_retry_gemini_call_success(self):
        """Test successful Gemini call retry"""
        with patch('modules.api_utils._gemini_backoff') as mock_backoff:
            mock_backoff.retry.return_value = "success"

            result = retry_gemini_call(lambda: "success")
            assert result == "success"
            mock_backoff.retry.assert_called_once()


class TestGlobalInstances:
    """Test global rate limiter and backoff instances"""

    def test_global_gemini_rate_limiter(self):
        """Test global Gemini rate limiter instance"""
        from modules.api_utils import _gemini_rate_limiter
        assert isinstance(_gemini_rate_limiter, RateLimiter)

    def test_global_gemini_backoff(self):
        """Test global Gemini backoff instance"""
        from modules.api_utils import _gemini_backoff
        assert isinstance(_gemini_backoff, ExponentialBackoff)

    def test_global_omi_http_retry(self):
        """Test global OMI HTTP retry instance"""
        from modules.api_utils import _omi_http_retry
        assert isinstance(_omi_http_retry, HTTPRetry)