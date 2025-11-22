"""
FastAPI Webhook Server
Receives webhooks from OMI app and triggers processing pipeline
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import json
from datetime import datetime
import re
from typing import Optional

from modules.orchestrator import OMIGeminiOrchestrator
from modules.security import WebhookValidator, RateLimiter, InputValidator
from modules.monitoring import monitoring
from config.settings import AppSettings, WebhookConfig, SecurityConfig

# Setup structured logging
AppSettings.setup_logging()

logger = logging.getLogger(__name__)

# Global instances
orchestrator: Optional[OMIGeminiOrchestrator] = None
webhook_validator: Optional[WebhookValidator] = None
rate_limiter: Optional[RateLimiter] = None

class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for headers, request size limits, and input validation"""

    async def dispatch(self, request: Request, call_next):
        # Check request size limit (10MB default)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                max_size = 10 * 1024 * 1024  # 10MB
                if size > max_size:
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Request too large"}
                    )
            except ValueError:
                pass

        # Security headers
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "media-src 'none'; "
            "object-src 'none'; "
            "frame-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp

        # HSTS (HTTP Strict Transport Security) - only if HTTPS is enabled
        if SecurityConfig.ENFORCE_HTTPS:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting request metrics"""

    async def dispatch(self, request: Request, call_next):
        import time
        start_time = time.time()

        # Extract user ID from query params if available
        user_id = request.query_params.get("uid")

        try:
            response = await call_next(request)
            response_time = time.time() - start_time

            # Record successful request
            monitoring.record_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                response_time=response_time,
                user_id=user_id
            )

            return response

        except Exception as e:
            response_time = time.time() - start_time

            # Record error
            monitoring.record_error(
                error_type=type(e).__name__,
                error_message=str(e),
                endpoint=request.url.path,
                user_id=user_id
            )

            # Record failed request
            monitoring.record_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=500,  # Assume 500 for unhandled exceptions
                response_time=response_time,
                user_id=user_id
            )

            raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI"""
    global orchestrator, webhook_validator, rate_limiter

    # Startup
    logger.info("Starting OMI-Gemini Webhook Server", extra={
        "host": WebhookConfig.HOST,
        "port": WebhookConfig.PORT,
        "debug": AppSettings.DEBUG
    })

    try:
        orchestrator = OMIGeminiOrchestrator()
        monitoring.set_orchestrator(orchestrator)
        logger.info("Orchestrator initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize orchestrator", exc_info=True, extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise

    # Initialize security components
    try:
        if SecurityConfig.ENABLE_WEBHOOK_SIGNATURE_VALIDATION:
            webhook_validator = WebhookValidator(SecurityConfig.WEBHOOK_SECRET or "")
            logger.info("Webhook signature validation enabled", extra={
                "signature_validation": True
            })

        if SecurityConfig.ENABLE_RATE_LIMITING:
            rate_limiter = RateLimiter(SecurityConfig.RATE_LIMIT_PER_MINUTE)
            logger.info("Rate limiting enabled", extra={
                "rate_limit_per_minute": SecurityConfig.RATE_LIMIT_PER_MINUTE
            })

        # Start monitoring system
        await monitoring.start_monitoring()
        logger.info("Monitoring system started")

        logger.info("Server ready", extra={
            "host": WebhookConfig.HOST,
            "port": WebhookConfig.PORT
        })

    except Exception as e:
        logger.error("Failed to initialize security components", exc_info=True, extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise

    yield

    # Shutdown
    logger.info("Shutting down server")
    try:
        await monitoring.stop_monitoring()
        logger.info("Monitoring system stopped")
    except Exception as e:
        logger.error("Error stopping monitoring system", exc_info=True, extra={
            "error": str(e),
            "error_type": type(e).__name__
        })

    try:
        if orchestrator:
            await orchestrator.close()
            logger.info("Orchestrator closed successfully")
    except Exception as e:
        logger.error("Error during orchestrator shutdown", exc_info=True, extra={
            "error": str(e),
            "error_type": type(e).__name__
        })

# Create FastAPI app
app = FastAPI(
    title="OMI-Gemini Integration Server",
    description="Webhook server for OMI app integration with Gemini AI and Google Workspace",
    version="1.0.0",
    lifespan=lifespan
)

# Add monitoring middleware (must be first)
app.add_middleware(MonitoringMiddleware)

# Add security middleware
app.add_middleware(SecurityMiddleware)

# HTTPS redirect not needed on Railway (already provides HTTPS)
# if SecurityConfig.ENFORCE_HTTPS:
#     app.add_middleware(HTTPSRedirectMiddleware)

# TrustedHostMiddleware disabled for Railway (causes redirect loops)
# if SecurityConfig.ALLOWED_HOSTS:
#     app.add_middleware(
#         TrustedHostMiddleware,
#         allowed_hosts=SecurityConfig.ALLOWED_HOSTS
#     )

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "OMI-Gemini Integration",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    health_data = await monitoring.get_health_status()
    return health_data

@app.get("/metrics")
async def metrics_endpoint():
    """Comprehensive metrics endpoint"""
    metrics_data = monitoring.get_metrics()
    return metrics_data

@app.get("/alerts")
async def alerts_endpoint():
    """Active alerts endpoint"""
    alerts_data = monitoring.get_alerts()
    return alerts_data

@app.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve an alert"""
    monitoring.resolve_alert(alert_id)
    return {"status": "resolved", "alert_id": alert_id}

@app.get("/performance")
async def performance_stats():
    """Performance monitoring endpoint (legacy compatibility)"""
    if not orchestrator:
        return JSONResponse(status_code=503, content={"error": "Orchestrator not initialized"})

    stats = orchestrator.get_performance_stats()
    return {
        "performance_stats": stats,
        "timestamp": datetime.utcnow().isoformat()
    }

async def _check_rate_limit(client_id: str):
    """Check rate limit for client"""
    if rate_limiter and SecurityConfig.ENABLE_RATE_LIMITING:
        if not rate_limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )

async def _validate_webhook_signature(request: Request):
    """Validate webhook signature if enabled"""
    if webhook_validator and SecurityConfig.ENABLE_WEBHOOK_SIGNATURE_VALIDATION:
        signature = request.headers.get("X-OMI-Signature")
        timestamp = request.headers.get("X-OMI-Timestamp")

        if not signature:
            logger.warning("Missing webhook signature")
            raise HTTPException(status_code=401, detail="Missing signature")

        # Read body for validation
        body = await request.body()

        # Validate timestamp if present
        if timestamp and not webhook_validator.is_timestamp_valid(timestamp):
            raise HTTPException(status_code=401, detail="Request timestamp too old")

        # Validate signature
        if not webhook_validator.validate_signature(body, signature, timestamp):
            raise HTTPException(status_code=401, detail="Invalid signature")

        return body
    return None

@app.post("/webhook")
async def generic_webhook(request: Request):
    """
    Generic Webhook Handler
    Logs the request body for debugging/testing purposes.
    """
    try:
        body = await request.json()
        logger.info(f"Received generic webhook (v1.1): {json.dumps(body, indent=2)}")
        return {"status": "received", "version": "1.1", "body": body}
    except Exception as e:
        logger.error(f"Error processing generic webhook: {e}")
        # Try to read as text if JSON fails
        try:
            body = await request.body()
            logger.info(f"Received generic webhook (text): {body.decode()}")
            return {"status": "received", "body": body.decode()}
        except Exception as inner_e:
             return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/webhook/memory")
async def memory_creation_webhook(request: Request):
    """
    Memory Creation Trigger Webhook

    Called by OMI app when a new memory is created
    Query params: uid (user identifier)
    Body: Complete memory object
    """
    uid = None
    memory_id = None

    try:
        # Get user ID from query params and validate
        uid = request.query_params.get("uid")
        if not uid or not InputValidator.validate_uid(uid):
            logger.warning("Memory webhook missing or invalid 'uid' query parameter", extra={
                "uid": uid,
                "client_host": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent")
            })
            raise HTTPException(status_code=400, detail="Missing or invalid 'uid' query parameter")

        # Check rate limit
        client_id = uid or (request.client.host if request.client else "unknown")
        await _check_rate_limit(client_id)

        # Validate signature (optional, reads body if enabled)
        validated_body = await _validate_webhook_signature(request)

        # Parse memory data (use validated body if available)
        try:
            if validated_body:
                memory_data = json.loads(validated_body)
            else:
                memory_data = await request.json()
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in webhook body", exc_info=True, extra={
                "uid": uid,
                "error": str(e),
                "body_length": len(validated_body) if validated_body else "unknown"
            })
            raise HTTPException(status_code=400, detail="Invalid JSON in request body")
        except Exception as e:
            logger.error("Error parsing webhook body", exc_info=True, extra={
                "uid": uid,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(status_code=400, detail="Unable to parse request body")

        # Validate and sanitize memory data structure
        try:
            memory_data = InputValidator.validate_memory_data(memory_data)
        except ValueError as e:
            logger.error("Invalid memory data structure", extra={
                "uid": uid,
                "error": str(e),
                "data_keys": list(memory_data.keys()) if isinstance(memory_data, dict) else None
            })
            raise HTTPException(status_code=400, detail=f"Invalid memory data: {str(e)}")

        memory_id = memory_data.get("id")
        if not memory_id:
            logger.warning("Memory data missing 'id' field", extra={
                "uid": uid,
                "memory_keys": list(memory_data.keys()) if isinstance(memory_data, dict) else None
            })
            # Not blocking as some webhooks might not have IDs yet

        logger.info("Received memory webhook", extra={
            "uid": uid,
            "memory_id": memory_id,
            "client_host": request.client.host if request.client else "unknown",
            "content_length": len(validated_body) if validated_body else request.headers.get("content-length")
        })

        # Process with orchestrator
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Service not initialized")
    
        result = await orchestrator.process_memory_webhook(memory_data, uid)

        # Record processing metrics
        from typing import Dict, Any, cast
        monitoring.record_processing_result(cast(Dict[str, Any], result))

        # Return response based on processing result
        if result["success"]:
            status_code = 200
            status_msg = "success"
        elif len(result["steps_completed"]) > 0:
            status_code = 207  # Multi-Status for partial success
            status_msg = "partial_success"
        else:
            status_code = 500
            status_msg = "failed"

        logger.info("Memory webhook processed", extra={
            "uid": uid,
            "memory_id": memory_id,
            "status": status_msg,
            "steps_completed": len(result.get('steps_completed', [])),
            "errors": len(result.get('errors', [])),
            "processing_time": result.get('processing_time_seconds')
        })

        return JSONResponse(
            status_code=status_code,
            content={
                "status": status_msg,
                "message": f"Processed {len(result['steps_completed'])} steps, {len(result['errors'])} errors",
                "details": result
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error("Unexpected error in memory webhook", exc_info=True, extra={
            "uid": uid,
            "memory_id": memory_id,
            "error": str(e),
            "error_type": type(e).__name__,
            "client_host": request.client.host if request.client else "unknown"
        })
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/webhook/realtime")
async def realtime_transcript_webhook(request: Request):
    """
    Real-Time Transcript Processor Webhook

    Called by OMI app during active conversations
    Query params: session_id, uid
    Body: Array of transcript segments
    """
    try:
        # Get and validate parameters
        session_id = request.query_params.get("session_id")
        uid = request.query_params.get("uid")

        if not session_id or not uid or not InputValidator.validate_session_id(session_id) or not InputValidator.validate_uid(uid):
            logger.warning("Realtime webhook missing or invalid required query parameters", extra={
                "session_id": session_id,
                "uid": uid
            })
            raise HTTPException(status_code=400, detail="Missing or invalid required query parameters: session_id and uid")

        # Validate signature (optional, reads body if enabled)
        validated_body = await _validate_webhook_signature(request)

        # Parse segments (use validated body if available)
        try:
            if validated_body:
                segments = json.loads(validated_body)
            else:
                segments = await request.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in realtime webhook body: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid JSON in request body")
        except Exception as e:
            logger.error(f"Error parsing realtime webhook body: {str(e)}")
            raise HTTPException(status_code=400, detail="Unable to parse request body")

        # Validate and sanitize segments
        try:
            segments = InputValidator.validate_transcript_segments(segments)
        except ValueError as e:
            logger.error("Invalid transcript segments", extra={
                "session_id": session_id,
                "uid": uid,
                "error": str(e)
            })
            raise HTTPException(status_code=400, detail=f"Invalid transcript segments: {str(e)}")

        logger.info(f"Received realtime transcript - session: {session_id}, uid: {uid}, segments: {len(segments)}")

        # Process
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Service not initialized")

        result = await orchestrator.process_realtime_transcript(segments, session_id, uid)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "result": result
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in realtime webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/webhook/audio")
async def audio_streaming_webhook(request: Request):
    """
    Real-Time Audio Streaming Webhook

    Receives raw audio bytes from OMI device
    Query params: sample_rate, uid
    Body: Raw PCM16 audio bytes
    """
    try:
        sample_rate_str = request.query_params.get("sample_rate")
        uid = request.query_params.get("uid")

        if not sample_rate_str or not uid or not InputValidator.validate_uid(uid):
            logger.warning("Audio webhook missing or invalid required query parameters", extra={
                "sample_rate": sample_rate_str,
                "uid": uid
            })
            raise HTTPException(status_code=400, detail="Missing or invalid required query parameters: sample_rate and uid")

        # Validate sample_rate
        try:
            sample_rate = InputValidator.validate_sample_rate(sample_rate_str)
        except ValueError as e:
            logger.error(f"Invalid sample_rate parameter: {sample_rate_str} - {str(e)}")
            raise HTTPException(status_code=400, detail="sample_rate must be a valid integer between 8000 and 48000")

        # Validate signature (optional, reads body if enabled)
        validated_body = await _validate_webhook_signature(request)

        # Read audio bytes (use validated body if available)
        if validated_body:
            audio_bytes = validated_body
        else:
            audio_bytes = await request.body()

        logger.info(f"Received audio stream - uid: {uid}, sample_rate: {sample_rate}, bytes: {len(audio_bytes)}")

        # Process audio stream (save to buffer for potential future transcription)
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Service not initialized")

        return orchestrator.process_audio_stream(audio_bytes, sample_rate, uid)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in audio webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/analyze")
async def manual_analysis(limit: int = 5):
    """
    Manual trigger for analyzing recent conversations

    Query params: limit (number of conversations to analyze, max 50)
    """
    try:
        # Validate limit parameter
        if not isinstance(limit, int) or limit < 1 or limit > 50:
            raise HTTPException(status_code=400, detail="limit must be an integer between 1 and 50")

        if not orchestrator:
            raise HTTPException(status_code=503, detail="Service not initialized")

        results = await orchestrator.manual_conversation_analysis(limit=limit)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "conversations_analyzed": len(results),
                "results": results
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manual analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/login")
async def google_auth_login():
    """Initiate Google OAuth2 flow"""
    try:
        if not orchestrator or not orchestrator.workspace_automation:
            raise HTTPException(status_code=503, detail="Workspace automation not initialized")

        auth_url = orchestrator.workspace_automation.get_authorization_url()
        if not auth_url:
            raise HTTPException(status_code=500, detail="Failed to generate authorization URL")

        return {"authorization_url": auth_url, "message": "Visit this URL to authorize"}

    except Exception as e:
        logger.error(f"Error initiating OAuth: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/callback")
async def google_auth_callback(code: str = None, state: str = None, error: str = None):
    """Handle Google OAuth2 callback"""
    try:
        if error:
            logger.error(f"OAuth error: {error}")
            return JSONResponse(
                status_code=400,
                content={"error": error, "message": "Authorization failed"}
            )

        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing authorization code or state")

        if not orchestrator or not orchestrator.workspace_automation:
            raise HTTPException(status_code=503, detail="Workspace automation not initialized")

        success = orchestrator.workspace_automation.complete_authentication(code, state)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to complete authentication")

        return {
            "status": "success",
            "message": "Successfully authenticated with Google Workspace",
            "email": "michele.biology@gmail.com"
        }

    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "webhook_server:app",
        host=WebhookConfig.HOST,
        port=WebhookConfig.PORT,
        reload=AppSettings.DEBUG,
        log_level=AppSettings.LOG_LEVEL.lower()
    )
