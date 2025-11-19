"""
Security utilities for webhook validation and rate limiting
"""
import hashlib
import hmac
import time
from typing import Optional
from functools import wraps
from collections import defaultdict
import logging

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
        self.requests = defaultdict(list)
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
