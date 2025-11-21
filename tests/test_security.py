"""
Unit tests for security.py module
Tests webhook validation, rate limiting, and input sanitization
"""
import pytest
import time
import hmac
import hashlib
from unittest.mock import patch, MagicMock
from freezegun import freeze_time

from modules.security import WebhookValidator, RateLimiter, InputValidator


class TestWebhookValidator:
    """Test webhook signature validation"""

    @pytest.fixture
    def validator(self):
        """Create webhook validator with test secret"""
        return WebhookValidator("test_secret_key")

    def test_init_with_string_secret(self):
        """Test initialization with string secret"""
        validator = WebhookValidator("test_secret")
        assert validator.secret == b"test_secret"

    def test_init_with_bytes_secret(self):
        """Test initialization with bytes secret"""
        secret_bytes = b"test_secret_bytes"
        validator = WebhookValidator(secret_bytes)
        assert validator.secret == secret_bytes

    def test_validate_signature_valid(self, validator):
        """Test valid signature validation"""
        payload = b'{"test": "data"}'
        # Create valid signature
        expected_sig = hmac.new(validator.secret, payload, hashlib.sha256).hexdigest()

        assert validator.validate_signature(payload, expected_sig) == True

    def test_validate_signature_with_timestamp(self, validator):
        """Test signature validation with timestamp"""
        payload = b'{"test": "data"}'
        timestamp = "1640995200"  # 2022-01-01 00:00:00 UTC
        signed_payload = f"{timestamp}.".encode() + payload

        expected_sig = hmac.new(validator.secret, signed_payload, hashlib.sha256).hexdigest()

        assert validator.validate_signature(payload, expected_sig, timestamp) == True

    def test_validate_signature_invalid(self, validator):
        """Test invalid signature rejection"""
        payload = b'{"test": "data"}'
        invalid_sig = "invalid_signature"

        assert validator.validate_signature(payload, invalid_sig) == False

    def test_validate_signature_timestamp_mismatch(self, validator):
        """Test signature validation with wrong timestamp"""
        payload = b'{"test": "data"}'
        wrong_timestamp = "1640995200"
        correct_timestamp = "1640995201"

        # Create signature with correct timestamp
        signed_payload = f"{correct_timestamp}.".encode() + payload
        expected_sig = hmac.new(validator.secret, signed_payload, hashlib.sha256).hexdigest()

        # Validate with wrong timestamp
        assert validator.validate_signature(payload, expected_sig, wrong_timestamp) == False

    def test_is_timestamp_valid_recent(self, validator):
        """Test timestamp validation for recent timestamps"""
        current_time = int(time.time())
        recent_timestamp = str(current_time - 100)  # 100 seconds ago

        assert validator.is_timestamp_valid(recent_timestamp) == True

    def test_is_timestamp_valid_too_old(self, validator):
        """Test timestamp validation for old timestamps"""
        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago (> 300s tolerance)

        assert validator.is_timestamp_valid(old_timestamp) == False

    def test_is_timestamp_valid_future(self, validator):
        """Test timestamp validation for future timestamps"""
        future_timestamp = str(int(time.time()) + 100)  # 100 seconds in future

        assert validator.is_timestamp_valid(future_timestamp) == True

    def test_is_timestamp_valid_invalid_format(self, validator):
        """Test timestamp validation with invalid format"""
        assert validator.is_timestamp_valid("invalid") == False
        assert validator.is_timestamp_valid("") == False
        assert validator.is_timestamp_valid(None) == False


class TestRateLimiter:
    """Test rate limiting functionality"""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing"""
        return RateLimiter(requests_per_minute=10)

    def test_init(self, rate_limiter):
        """Test rate limiter initialization"""
        assert rate_limiter.requests_per_minute == 10
        assert len(rate_limiter.requests) == 0

    def test_is_allowed_under_limit(self, rate_limiter):
        """Test allowing requests under rate limit"""
        client_id = "test_client"

        # Should allow all requests under limit
        for i in range(10):
            assert rate_limiter.is_allowed(client_id) == True

    def test_is_allowed_over_minute_limit(self, rate_limiter):
        """Test blocking requests over minute limit"""
        client_id = "test_client"

        # Use up minute tokens
        for i in range(10):
            assert rate_limiter.is_allowed(client_id) == True

        # Next request should be blocked
        assert rate_limiter.is_allowed(client_id) == False

    def test_is_allowed_over_hour_limit(self, rate_limiter):
        """Test blocking requests over hour limit"""
        client_id = "test_client"

        # Simulate using up hour tokens over time
        with freeze_time("2024-01-01 00:00:00") as frozen_time:
            # Use up minute tokens
            for i in range(10):
                assert rate_limiter.is_allowed(client_id) == True

            # Advance time to refill minute tokens but keep hour tokens low
            frozen_time.move_to("2024-01-01 00:01:00")

            # Should be able to make more requests, but eventually hit hour limit
            # This is simplified - in practice hour limit would be hit after many more requests
            for i in range(40):  # 10 + 40 = 50, should hit hour limit
                rate_limiter.is_allowed(client_id)

            # Should now be rate limited by hour limit
            assert rate_limiter.is_allowed(client_id) == False

    def test_multiple_clients(self, rate_limiter):
        """Test rate limiting works independently per client"""
        client1 = "client1"
        client2 = "client2"

        # Both clients should be able to make requests
        for i in range(5):
            assert rate_limiter.is_allowed(client1) == True
            assert rate_limiter.is_allowed(client2) == True

        # Client1 hits limit
        for i in range(5):
            assert rate_limiter.is_allowed(client1) == True
        assert rate_limiter.is_allowed(client1) == False

        # Client2 should still work
        assert rate_limiter.is_allowed(client2) == True

    def test_cleanup_old_entries(self, rate_limiter):
        """Test cleanup of old client entries"""
        client1 = "client1"
        client2 = "client2"

        # Add some requests
        rate_limiter.is_allowed(client1)
        rate_limiter.is_allowed(client2)

        initial_count = len(rate_limiter.requests)
        assert initial_count >= 2

        # Advance time past cleanup threshold
        with freeze_time("2024-01-01 00:00:00") as frozen_time:
            frozen_time.move_to("2024-01-01 00:03:00")  # Advance 3 minutes

            # Trigger cleanup by making a request
            rate_limiter.is_allowed("new_client")

            # Cleanup should have been triggered (last_cleanup should be updated)
            assert rate_limiter.last_cleanup > 0


class TestInputValidator:
    """Test input validation and sanitization"""

    def test_validate_uid_valid(self):
        """Test valid UID validation"""
        assert InputValidator.validate_uid("user123") == True
        assert InputValidator.validate_uid("test_user_123") == True
        assert InputValidator.validate_uid("user-name") == True

    def test_validate_uid_invalid(self):
        """Test invalid UID validation"""
        assert InputValidator.validate_uid("") == False
        assert InputValidator.validate_uid("   ") == False
        assert InputValidator.validate_uid(None) == False
        assert InputValidator.validate_uid(123) == False
        assert InputValidator.validate_uid("user@domain.com") == False  # Invalid chars
        assert InputValidator.validate_uid("a" * 101) == False  # Too long

    def test_validate_session_id_valid(self):
        """Test valid session ID validation"""
        assert InputValidator.validate_session_id("session_123") == True
        assert InputValidator.validate_session_id("abc123def456") == True

    def test_validate_session_id_invalid(self):
        """Test invalid session ID validation"""
        assert InputValidator.validate_session_id("") == False
        assert InputValidator.validate_session_id("   ") == False
        assert InputValidator.validate_session_id(None) == False
        assert InputValidator.validate_session_id(123) == False
        assert InputValidator.validate_session_id("session@domain.com") == False
        assert InputValidator.validate_session_id("a" * 201) == False  # Too long

    def test_validate_memory_data_valid(self):
        """Test valid memory data validation"""
        valid_data = {
            "id": "mem123",
            "text": "This is a test memory",
            "transcript_segments": [
                {"text": "Hello", "timestamp": "2024-01-01T00:00:00Z"},
                {"text": "World", "timestamp": "2024-01-01T00:00:05Z"}
            ],
            "structured": {"key": "value"}
        }

        result = InputValidator.validate_memory_data(valid_data)
        assert "id" in result
        assert "text" in result
        assert "transcript_segments" in result
        assert "structured" in result

    def test_validate_memory_data_invalid_type(self):
        """Test memory data validation with invalid types"""
        with pytest.raises(ValueError, match="must be a dictionary"):
            InputValidator.validate_memory_data("invalid")

    def test_validate_memory_data_too_long_text(self):
        """Test memory data validation with overly long text"""
        long_text = "a" * 100001  # Over 100KB limit
        data = {"text": long_text}

        with pytest.raises(ValueError, match="too long"):
            InputValidator.validate_memory_data(data)

    def test_validate_memory_data_too_many_segments(self):
        """Test memory data validation with too many transcript segments"""
        segments = [{"text": f"segment {i}", "timestamp": f"2024-01-01T00:{i:02d}:00Z"} for i in range(1001)]
        data = {"transcript_segments": segments}

        with pytest.raises(ValueError, match="Too many transcript segments"):
            InputValidator.validate_memory_data(data)

    def test_validate_transcript_segments_valid(self):
        """Test valid transcript segments validation"""
        segments = [
            {"text": "Hello world", "timestamp": "2024-01-01T00:00:00Z"},
            {"text": "How are you?", "timestamp": "2024-01-01T00:00:05Z"}
        ]

        result = InputValidator.validate_transcript_segments(segments)
        assert len(result) == 2
        assert result[0]["text"] == "Hello world"

    def test_validate_transcript_segments_invalid_type(self):
        """Test transcript segments validation with invalid type"""
        with pytest.raises(ValueError, match="must be a list"):
            InputValidator.validate_transcript_segments("invalid")

    def test_validate_transcript_segments_too_many(self):
        """Test transcript segments validation with too many segments"""
        segments = [{"text": f"text {i}"} for i in range(1001)]

        with pytest.raises(ValueError, match="too many"):
            InputValidator.validate_transcript_segments(segments)

    def test_sanitize_text_basic(self):
        """Test basic text sanitization"""
        text = "Hello world"
        assert InputValidator.sanitize_text(text) == text

    def test_sanitize_text_null_bytes(self):
        """Test sanitization of null bytes and control characters"""
        text = "Hello\x00world\x01test"
        sanitized = InputValidator.sanitize_text(text)
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized

    def test_sanitize_text_length_limit(self):
        """Test text length limiting"""
        long_text = "a" * 100001
        sanitized = InputValidator.sanitize_text(long_text)
        assert len(sanitized) <= 100000
        assert sanitized.endswith("...")

    def test_sanitize_text_invalid_type(self):
        """Test sanitization with invalid input type"""
        assert InputValidator.sanitize_text(None) == ""
        assert InputValidator.sanitize_text(123) == ""

    def test_sanitize_dict_basic(self):
        """Test basic dictionary sanitization"""
        data = {"key1": "value1", "key2": "value2"}
        sanitized = InputValidator.sanitize_dict(data)
        assert sanitized == data

    def test_sanitize_dict_nested(self):
        """Test nested dictionary sanitization"""
        data = {
            "text": "Hello world",
            "nested": {"inner": "value"},
            "list": ["item1", "item2"]
        }
        sanitized = InputValidator.sanitize_dict(data)
        assert sanitized["text"] == "Hello world"
        assert sanitized["nested"]["inner"] == "value"
        assert sanitized["list"] == ["item1", "item2"]

    def test_sanitize_dict_depth_limit(self):
        """Test dictionary depth limiting"""
        # Create deeply nested dict
        data = {"level1": {"level2": {"level3": {"level4": {"level5": {"level6": "deep"}}}}}}
        sanitized = InputValidator.sanitize_dict(data, max_depth=3)
        # Should be truncated at depth 3
        assert isinstance(sanitized, dict)
        assert "level1" in sanitized

    def test_sanitize_list_basic(self):
        """Test basic list sanitization"""
        data = ["item1", "item2", "item3"]
        sanitized = InputValidator.sanitize_list(data)
        assert sanitized == data

    def test_sanitize_list_mixed_types(self):
        """Test list sanitization with mixed types"""
        data = ["text", 123, {"key": "value"}, ["nested"]]
        sanitized = InputValidator.sanitize_list(data)
        assert sanitized[0] == "text"
        assert sanitized[1] == 123
        assert isinstance(sanitized[2], dict)
        assert isinstance(sanitized[3], list)

    def test_validate_sample_rate_valid(self):
        """Test valid sample rate validation"""
        assert InputValidator.validate_sample_rate(44100) == 44100
        assert InputValidator.validate_sample_rate("22050") == 22050
        assert InputValidator.validate_sample_rate(8000) == 8000

    def test_validate_sample_rate_invalid(self):
        """Test invalid sample rate validation"""
        with pytest.raises(ValueError):
            InputValidator.validate_sample_rate(7000)  # Too low

        with pytest.raises(ValueError):
            InputValidator.validate_sample_rate(50000)  # Too high

        with pytest.raises(ValueError):
            InputValidator.validate_sample_rate("invalid")

        with pytest.raises(ValueError):
            InputValidator.validate_sample_rate(None)

    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization"""
        filename = "test_file.txt"
        assert InputValidator.sanitize_filename(filename) == filename

    def test_sanitize_filename_dangerous_chars(self):
        """Test sanitization of dangerous filename characters"""
        dangerous = "test<file>.txt|dangerous*name"
        sanitized = InputValidator.sanitize_filename(dangerous)
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert "|" not in sanitized
        assert "*" not in sanitized

    def test_sanitize_filename_path_traversal(self):
        """Test prevention of path traversal attacks"""
        traversal = "../../../etc/passwd"
        sanitized = InputValidator.sanitize_filename(traversal)
        assert ".." not in sanitized
        assert "/" not in sanitized

    def test_sanitize_filename_empty(self):
        """Test sanitization resulting in empty filename"""
        dangerous = "<>|?*"
        sanitized = InputValidator.sanitize_filename(dangerous)
        assert sanitized == "unknown"  # Default for empty result

    def test_sanitize_filename_too_long(self):
        """Test filename length limiting"""
        long_name = "a" * 300
        sanitized = InputValidator.sanitize_filename(long_name)
        assert len(sanitized) <= 255