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
    PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.0-flash-exp")
    FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-1.5-pro")
    LITE_MODEL = os.getenv("GEMINI_LITE_MODEL", "gemini-1.5-flash")

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
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/presentations'
    ]

# Webhook Server Configuration
class WebhookConfig:
    HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    # Prioritize PORT (standard for PaaS) then WEBHOOK_PORT, default to 8000
    PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8000")))
    BASE_URL = os.getenv("WEBHOOK_BASE_URL", f"http://localhost:{PORT}")

# Security Settings
class SecurityConfig:
    # Webhook signature validation (production only)
    ENABLE_WEBHOOK_VALIDATION = os.getenv("ENABLE_WEBHOOK_VALIDATION", "false").lower() == "true"
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", OMIConfig.APP_SECRET)  # Use OMI secret by default

    # Rate limiting
    ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# Application Settings
class AppSettings:
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = BASE_DIR / "logs"

    # Ensure logs directory exists
    LOG_DIR.mkdir(exist_ok=True)

# Export all configs
__all__ = [
    "OMIConfig",
    "GeminiConfig",
    "GoogleWorkspaceConfig",
    "WebhookConfig",
    "SecurityConfig",
    "AppSettings",
    "BASE_DIR"
]
