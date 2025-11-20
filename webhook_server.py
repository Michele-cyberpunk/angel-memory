"""
FastAPI Webhook Server
Receives webhooks from OMI app and triggers processing pipeline
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys
from datetime import datetime

from modules.orchestrator import OMIGeminiOrchestrator
from modules.security import WebhookValidator, RateLimiter
from config.settings import AppSettings, WebhookConfig, SecurityConfig

# Configure logging
logging.basicConfig(
    level=getattr(logging, AppSettings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(AppSettings.LOG_DIR / "webhook_server.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Global instances
orchestrator: OMIGeminiOrchestrator = None
webhook_validator: WebhookValidator = None
rate_limiter: RateLimiter = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI"""
    global orchestrator, webhook_validator, rate_limiter

    # Startup
    logger.info("Starting OMI-Gemini Webhook Server")
    orchestrator = OMIGeminiOrchestrator()

    # Initialize security components
    if SecurityConfig.ENABLE_WEBHOOK_VALIDATION:
        webhook_validator = WebhookValidator(SecurityConfig.WEBHOOK_SECRET)
        logger.info("Webhook signature validation enabled")

    if SecurityConfig.ENABLE_RATE_LIMITING:
        rate_limiter = RateLimiter(SecurityConfig.RATE_LIMIT_PER_MINUTE)
        logger.info(f"Rate limiting enabled: {SecurityConfig.RATE_LIMIT_PER_MINUTE} req/min")

    logger.info(f"Server ready on {WebhookConfig.HOST}:{WebhookConfig.PORT}")

    yield

    # Shutdown
    logger.info("Shutting down server")
    if orchestrator:
        await orchestrator.close()

# Create FastAPI app
app = FastAPI(
    title="OMI-Gemini Integration Server",
    description="Webhook server for OMI app integration with Gemini AI and Google Workspace",
    version="1.0.0",
    lifespan=lifespan
)

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
    return {
        "status": "healthy",
        "orchestrator_initialized": orchestrator is not None,
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
    if webhook_validator and SecurityConfig.ENABLE_WEBHOOK_VALIDATION:
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

@app.post("/webhook/memory")
async def memory_creation_webhook(request: Request):
    """
    Memory Creation Trigger Webhook

    Called by OMI app when a new memory is created
    Query params: uid (user identifier)
    Body: Complete memory object
    """
    try:
        # Get user ID from query params
        uid = request.query_params.get("uid")
        if not uid:
            raise HTTPException(status_code=400, detail="Missing 'uid' query parameter")

        # Check rate limit
        client_id = uid or request.client.host
        await _check_rate_limit(client_id)

        # Validate signature (optional, reads body if enabled)
        validated_body = await _validate_webhook_signature(request)

        # Parse memory data (use validated body if available)
        if validated_body:
            import json
            memory_data = json.loads(validated_body)
        else:
            memory_data = await request.json()

        logger.info(f"Received memory webhook for user {uid}, memory ID: {memory_data.get('id')}")

        # Process with orchestrator
        result = await orchestrator.process_memory_webhook(memory_data, uid)

        # Return response
        status_code = 200 if result["success"] else 500

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "success" if result["success"] else "partial_failure",
                "message": f"Processed {len(result['steps_completed'])} steps",
                "details": result
            }
        )

    except Exception as e:
        logger.error(f"Error in memory webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/realtime")
async def realtime_transcript_webhook(request: Request):
    """
    Real-Time Transcript Processor Webhook

    Called by OMI app during active conversations
    Query params: session_id, uid
    Body: Array of transcript segments
    """
    try:
        # Get parameters
        session_id = request.query_params.get("session_id")
        uid = request.query_params.get("uid")

        if not session_id or not uid:
            raise HTTPException(status_code=400, detail="Missing required query parameters")

        # Parse segments
        segments = await request.json()

        logger.info(f"Received realtime transcript - session: {session_id}, segments: {len(segments)}")

        # Process
        result = await orchestrator.process_realtime_transcript(segments, session_id, uid)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "result": result
            }
        )

    except Exception as e:
        logger.error(f"Error in realtime webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/audio")
async def audio_streaming_webhook(request: Request):
    """
    Real-Time Audio Streaming Webhook

    Receives raw audio bytes from OMI device
    Query params: sample_rate, uid
    Body: Raw PCM audio bytes
    """
    try:
        sample_rate = request.query_params.get("sample_rate")
        uid = request.query_params.get("uid")

        if not sample_rate or not uid:
            raise HTTPException(status_code=400, detail="Missing required query parameters")

        # Read audio bytes
        audio_bytes = await request.body()

        logger.info(f"Received audio stream - sample_rate: {sample_rate}, bytes: {len(audio_bytes)}")

        # Process audio stream (save to buffer for potential future transcription)
        result = orchestrator.process_audio_stream(audio_bytes, int(sample_rate), uid)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "bytes_received": len(audio_bytes),
                "sample_rate": sample_rate,
                "buffered": result.get("buffered", False),
                "buffer_size": result.get("buffer_size", 0)
            }
        )

    except Exception as e:
        logger.error(f"Error in audio webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def manual_analysis(limit: int = 5):
    """
    Manual trigger for analyzing recent conversations

    Query params: limit (number of conversations to analyze)
    """
    try:
        results = await orchestrator.manual_conversation_analysis(limit=limit)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "conversations_analyzed": len(results),
                "results": results
            }
        )

    except Exception as e:
        logger.error(f"Error in manual analysis: {str(e)}", exc_info=True)
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
