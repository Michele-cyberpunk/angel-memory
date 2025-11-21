"""
Security utilities for webhook validation, rate limiting, and input sanitization
"""
import hashlib
import hmac
import time
import re
from typing import Optional, Any, Dict, List, Union
from functools import wraps
from collections import defaultdict
import logging
from config.settings import AppSettings

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class WebhookValidator:
    """Validate webhook signatures from OMI"""
    
    def __init__(self, secret: str):
        self.secret = secret.encode('utf-8') if isinstance(secret, str) else secret
    
    def validate_signature(self, payload: bytes, signature: str, 
                          timestamp: Optional[str] = None) -> bool:
        """
        Validate webhook signature using HMAC-SHA256
        
        Args:
            payload: Raw request body bytes
            signature: Signature from X-OMI-Signature header
            timestamp: Optional timestamp from X-OMI-Timestamp header
            
        Returns:
            True if signature is valid
        """
        try:
            # Construct signed message
            if timestamp:
                signed_payload = f"{timestamp}.".encode() + payload
            else:
                signed_payload = payload
            
            # Compute expected signature
            expected_signature = hmac.new(
                self.secret,
                signed_payload,
                hashlib.sha256
            ).hexdigest()
            
            # Constant-time comparison
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if not is_valid:
                logger.warning("Invalid webhook signature")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Signature validation error: {str(e)}")
            return False
    
    def is_timestamp_valid(self, timestamp: str, tolerance_seconds: int = 300) -> bool:
        """
        Check if timestamp is within acceptable range (prevents replay attacks)
        
        Args:
            timestamp: Unix timestamp string
            tolerance_seconds: Maximum age of request (default 5 minutes)
            
        Returns:
            True if timestamp is recent enough
        """
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            age = abs(current_time - request_time)
            
            is_valid = age <= tolerance_seconds
            
            if not is_valid:
                logger.warning(f"Webhook timestamp too old: {age}s")
            
            return is_valid
            
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid timestamp format: {str(e)}")
            return False


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.cleanup_interval = 60  # Clean old entries every 60 seconds
        self.last_cleanup = time.time()
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Check if client is within rate limits
        
        Args:
            client_id: Unique identifier (IP, user_id, etc.)
            
        Returns:
            True if request is allowed
        """
        current_time = time.time()
        
        # Cleanup old entries periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup()
        
        # Get recent requests for this client
        client_requests = self.requests[client_id]
        
        # Remove requests older than 1 minute
        cutoff_time = current_time - 60
        client_requests[:] = [t for t in client_requests if t > cutoff_time]
        
        # Check limit
        if len(client_requests) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return False
        
        # Add current request
        client_requests.append(current_time)
        return True
    
    def _cleanup(self):
        """Remove old client entries"""
        current_time = time.time()
        cutoff_time = current_time - 120  # Keep last 2 minutes
        
        clients_to_remove = []
        for client_id, requests in self.requests.items():
            requests[:] = [t for t in requests if t > cutoff_time]
            if not requests:
                clients_to_remove.append(client_id)
        
        for client_id in clients_to_remove:
            del self.requests[client_id]
        
        self.last_cleanup = current_time
        logger.debug(f"Cleaned up rate limiter, {len(self.requests)} active clients")


class InputValidator:
    """Comprehensive input validation and sanitization"""

    # Patterns for validation
    UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', re.IGNORECASE)
    ALPHA_NUMERIC_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    SAFE_TEXT_PATTERN = re.compile(r'^[a-zA-Z0-9\s\.,!?\-_:;\'\"()]+$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    @staticmethod
    def validate_uid(uid: str) -> bool:
        """Validate user ID format"""
        if not isinstance(uid, str):
            return False
        if not uid.strip():
            return False
        if len(uid) > 100:  # Reasonable length limit
            return False
        return InputValidator.ALPHA_NUMERIC_PATTERN.match(uid) is not None

    @staticmethod
    def validate_session_id(session_id: str) -> bool:
        """Validate session ID format"""
        if not isinstance(session_id, str):
            return False
        if not session_id.strip():
            return False
        if len(session_id) > 200:  # Reasonable length limit
            return False
        return InputValidator.ALPHA_NUMERIC_PATTERN.match(session_id) is not None

    @staticmethod
    def validate_memory_data(memory_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize memory data structure"""
        if not isinstance(memory_data, dict):
            raise ValueError("Memory data must be a dictionary")

        # Check for required fields and validate types
        validated_data: Dict[str, Any] = {}
        
        # Validate ID if present
        if "id" in memory_data:
            memory_id = memory_data["id"]
            if not isinstance(memory_id, (str, int)):
                raise ValueError("Memory ID must be string or integer")
            if isinstance(memory_id, str) and len(memory_id) > 200:
                raise ValueError("Memory ID too long")
            validated_data["id"] = str(memory_id)

        # Validate text content
        if "text" in memory_data:
            text = memory_data["text"]
            if not isinstance(text, str):
                raise ValueError("Memory text must be string")
            if len(text) > 100000:  # 100KB limit
                raise ValueError("Memory text too long")
            validated_data["text"] = InputValidator.sanitize_text(text)

        # Validate transcript segments
        if "transcript_segments" in memory_data:
            segments = memory_data["transcript_segments"]
            if not isinstance(segments, list):
                raise ValueError("Transcript segments must be a list")
            if len(segments) > 1000:  # Reasonable limit
                raise ValueError("Too many transcript segments")
            validated_segments = []
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                validated_segment = {}
                if "text" in segment:
                    text = segment["text"]
                    if isinstance(text, str) and len(text) < 10000:  # 10KB per segment
                        validated_segment["text"] = InputValidator.sanitize_text(text)
                if "timestamp" in segment:
                    # Allow timestamp as number or string
                    validated_segment["timestamp"] = segment["timestamp"]
                validated_segments.append(validated_segment)
            validated_data["transcript_segments"] = validated_segments

        # Validate structured data
        if "structured" in memory_data:
            structured = memory_data["structured"]
            if isinstance(structured, dict):
                validated_data["structured"] = InputValidator.sanitize_dict(structured)

        return validated_data

    @staticmethod
    def validate_transcript_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate transcript segments array"""
        if not isinstance(segments, list):
            raise ValueError("Transcript segments must be a list")

        if len(segments) > 1000:  # Reasonable limit
            raise ValueError("Too many transcript segments")

        validated_segments = []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            validated_segment = {}
            if "text" in segment:
                text = segment["text"]
                if isinstance(text, str) and len(text) < 10000:  # 10KB per segment
                    validated_segment["text"] = InputValidator.sanitize_text(text)
            if "timestamp" in segment:
                validated_segment["timestamp"] = segment["timestamp"]
            validated_segments.append(validated_segment)

        return validated_segments

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitize text input to prevent XSS and other attacks"""
        if not isinstance(text, str):
            return ""

        # Remove null bytes and other control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        # Limit length to prevent DoS
        if len(text) > 100000:  # 100KB limit
            text = text[:100000] + "..."

        return text

    @staticmethod
    def sanitize_dict(data: Dict[str, Any], max_depth: int = 5, max_keys: int = 100) -> Dict[str, Any]:
        """Recursively sanitize dictionary values"""
        if max_depth <= 0 or not isinstance(data, dict):
            return {}

        sanitized: Dict[str, Any] = {}
        key_count = 0

        for key, value in data.items():
            if key_count >= max_keys:
                break
            if not isinstance(key, str) or len(key) > 100:
                continue

            if isinstance(value, str):
                sanitized[key] = InputValidator.sanitize_text(value)
            elif isinstance(value, dict):
                sanitized[key] = InputValidator.sanitize_dict(value, max_depth - 1, max_keys)
            elif isinstance(value, list):
                sanitized[key] = InputValidator.sanitize_list(value, max_depth - 1, max_keys)
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            # Skip other types for security

            key_count += 1

        return sanitized

    @staticmethod
    def sanitize_list(data: List[Any], max_depth: int = 5, max_items: int = 100) -> List[Any]:
        """Recursively sanitize list values"""
        if max_depth <= 0 or not isinstance(data, list):
            return []

        sanitized: List[Any] = []
        for item in data[:max_items]:  # Limit items
            if isinstance(item, str):
                sanitized.append(InputValidator.sanitize_text(item))
            elif isinstance(item, dict):
                sanitized.append(InputValidator.sanitize_dict(item, max_depth - 1, max_items))
            elif isinstance(item, list):
                sanitized.append(InputValidator.sanitize_list(item, max_depth - 1, max_items))
            elif isinstance(item, (int, float, bool)):
                sanitized.append(item)
            # Skip other types

        return sanitized

    @staticmethod
    def validate_sample_rate(sample_rate: Union[str, int]) -> int:
        """Validate audio sample rate"""
        try:
            rate = int(sample_rate)
            if rate < 8000 or rate > 48000:  # Reasonable audio range
                raise ValueError("Sample rate out of range")
            return rate
        except (ValueError, TypeError):
            raise ValueError("Invalid sample rate")

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        if not isinstance(filename, str):
            return "unknown"

        # Remove path separators and dangerous characters
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)

        # Remove leading/trailing dots and spaces
        filename = filename.strip(' .')

        # Limit length
        if len(filename) > 255:
            filename = filename[:255]

        # Ensure it's not empty
        if not filename:
            filename = "unknown"

        return filename
