"""
Configuration management for OMI-Gemini Integration System
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv(BASE_DIR / ".env.template")

# OMI Configuration
class OMIConfig:
    APP_ID = os.getenv("OMI_APP_ID")
    APP_SECRET = os.getenv("OMI_APP_SECRET")
    DEV_KEY = os.getenv("OMI_DEV_KEY")
    BASE_URL = os.getenv("OMI_BASE_URL", "https://api.omi.me")
    USER_UID = os.getenv("OMI_USER_UID")
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")

    @classmethod
    def validate(cls):
        """Validate required OMI credentials"""
        missing = []
        if not cls.APP_ID:
            missing.append("OMI_APP_ID")
        if not cls.APP_SECRET:
            missing.append("OMI_APP_SECRET")
        if not cls.USER_UID:
            missing.append("OMI_USER_UID")

        if missing:
            raise ValueError(f"Missing OMI credentials: {', '.join(missing)}")

        return True

# Gemini Configuration
class GeminiConfig:
    API_KEY = os.getenv("GEMINI_API_KEY")
    PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.5-pro")
    FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
    LITE_MODEL = os.getenv("GEMINI_LITE_MODEL", "gemini-2.5-flash-lite")

    # Rate limiting settings
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("GEMINI_RATE_LIMIT_RPM", "60"))
    RATE_LIMIT_REQUESTS_PER_HOUR = int(os.getenv("GEMINI_RATE_LIMIT_RPH", "1000"))

    # Retry settings
    MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    INITIAL_RETRY_DELAY = float(os.getenv("GEMINI_INITIAL_RETRY_DELAY", "1.0"))
    MAX_RETRY_DELAY = float(os.getenv("GEMINI_MAX_RETRY_DELAY", "60.0"))

    @classmethod
    def validate(cls):
        """Validate Gemini API key"""
        if not cls.API_KEY:
            raise ValueError("Missing GEMINI_API_KEY in environment")
        return True

# Google Workspace Configuration
class GoogleWorkspaceConfig:
    CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE", str(BASE_DIR / "config" / "client_secret.json"))
    TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", str(BASE_DIR / "config" / "token.json"))
    REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/oauth2callback")
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/presentations'
    ]

# Webhook Server Configuration
class WebhookConfig:
    HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    # Use PORT environment variable for Railway deployment, default to 8000
    PORT = int(os.getenv("PORT", "8000"))
    BASE_URL = os.getenv("WEBHOOK_BASE_URL", f"http://localhost:{PORT}")

# Security Settings
class SecurityConfig:
    # Webhook signature validation (production only)
    ENABLE_WEBHOOK_SIGNATURE_VALIDATION = os.getenv("WEBHOOK_SIGNATURE_VALIDATION", "false").lower() == "true"
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", OMIConfig.APP_SECRET)  # Use OMI secret by default

    # Rate limiting
    ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    # HTTPS and host security
    ENFORCE_HTTPS = os.getenv("ENFORCE_HTTPS", "true").lower() == "true"
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",") if os.getenv("ALLOWED_HOSTS") else None

# Multimodal Configuration
class MultimodalConfig:
    # Audio Processing
    ENABLE_AUDIO_PROCESSING = os.getenv("ENABLE_AUDIO_PROCESSING", "true").lower() == "true"
    AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "1"))
    AUDIO_FORMAT = os.getenv("AUDIO_FORMAT", "wav")
    MAX_AUDIO_DURATION_SECONDS = int(os.getenv("MAX_AUDIO_DURATION_SECONDS", "300"))  # 5 minutes
    AUDIO_MODEL = os.getenv("AUDIO_MODEL", "gemini-2.0-flash-exp")  # For audio understanding

    # Image Analysis
    ENABLE_IMAGE_ANALYSIS = os.getenv("ENABLE_IMAGE_ANALYSIS", "true").lower() == "true"
    MAX_IMAGE_SIZE_MB = float(os.getenv("MAX_IMAGE_SIZE_MB", "10"))
    SUPPORTED_IMAGE_FORMATS = os.getenv("SUPPORTED_IMAGE_FORMATS", "jpg,jpeg,png,webp,bmp").split(",")
    IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-2.0-flash-exp")  # For vision tasks

    # Video Processing (future extension)
    ENABLE_VIDEO_PROCESSING = os.getenv("ENABLE_VIDEO_PROCESSING", "false").lower() == "true"
    VIDEO_MAX_DURATION_SECONDS = int(os.getenv("VIDEO_MAX_DURATION_SECONDS", "60"))

    @classmethod
    def validate(cls):
        """Validate multimodal settings"""
        if cls.AUDIO_SAMPLE_RATE not in [8000, 16000, 22050, 44100]:
            raise ValueError(f"Unsupported audio sample rate: {cls.AUDIO_SAMPLE_RATE}")
        if cls.AUDIO_CHANNELS not in [1, 2]:
            raise ValueError(f"Unsupported audio channels: {cls.AUDIO_CHANNELS}")
        if cls.MAX_AUDIO_DURATION_SECONDS > 600:  # 10 minutes max
            raise ValueError("Audio duration too long")
        return True

# Multilingual Configuration
class MultilingualConfig:
    # Language Detection and Translation
    ENABLE_LANGUAGE_DETECTION = os.getenv("ENABLE_LANGUAGE_DETECTION", "true").lower() == "true"
    ENABLE_TRANSLATION = os.getenv("ENABLE_TRANSLATION", "true").lower() == "true"
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
    SUPPORTED_LANGUAGES = os.getenv("SUPPORTED_LANGUAGES", "en,es,fr,de,it,pt,zh,ja,ko,ru,ar,hi").split(",")
    TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "gemini-2.0-flash-exp")

    # Language-specific processing
    CONFIDENCE_THRESHOLD = float(os.getenv("LANGUAGE_CONFIDENCE_THRESHOLD", "0.7"))
    MAX_TRANSLATION_LENGTH = int(os.getenv("MAX_TRANSLATION_LENGTH", "10000"))

    @classmethod
    def validate(cls):
        """Validate multilingual settings"""
        if cls.DEFAULT_LANGUAGE not in cls.SUPPORTED_LANGUAGES:
            raise ValueError(f"Default language '{cls.DEFAULT_LANGUAGE}' not in supported languages")
        if not (0.0 <= cls.CONFIDENCE_THRESHOLD <= 1.0):
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        return True

# Application Settings
class AppSettings:
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = BASE_DIR / "logs"

    # Ensure logs directory exists
    LOG_DIR.mkdir(exist_ok=True)

    @classmethod
    def setup_logging(cls):
        """Configure structured logging for the application"""
        import logging
        import sys

        # Create formatters
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Structured formatter for file logging
        class StructuredFormatter(logging.Formatter):
            def format(self, record):
                # Add structured fields
                if not hasattr(record, 'extra_fields'):
                    record.extra_fields = {}
                # Include any extra fields from the log call
                if hasattr(record, '__dict__'):
                    for key, value in record.__dict__.items():
                        if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName', 'process', 'message', 'asctime', 'extra_fields']:
                            record.extra_fields[key] = value
                return super().format(record)

        structured_formatter = StructuredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(extra_fields)s'
        )

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, cls.LOG_LEVEL))

        # Clear existing handlers
        root_logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # File handler with structured format
        try:
            file_handler = logging.FileHandler(cls.LOG_DIR / "app.log")
            file_handler.setFormatter(structured_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Fallback if file logging fails
            console_handler.setLevel(logging.WARNING)
            logging.warning(f"Could not set up file logging: {e}")

        # Set specific loggers to reduce noise
        logging.getLogger('google').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)

        logging.info("Logging configured", extra={
            "log_level": cls.LOG_LEVEL,
            "debug_mode": cls.DEBUG,
            "log_dir": str(cls.LOG_DIR)
        })

def validate_all_configs():
    """Validate all configuration classes"""
    try:
        OMIConfig.validate()
        GeminiConfig.validate()
        MultimodalConfig.validate()
        MultilingualConfig.validate()
        return True
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {str(e)}")

# Export all configs
__all__ = [
    "OMIConfig",
    "GeminiConfig",
    "GoogleWorkspaceConfig",
    "WebhookConfig",
    "SecurityConfig",
    "MultimodalConfig",
    "MultilingualConfig",
    "AppSettings",
    "BASE_DIR",
    "validate_all_configs"
]
