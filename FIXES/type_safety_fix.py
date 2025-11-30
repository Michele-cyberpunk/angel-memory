"""
PATCH 4: Type Safety & Validation
Fixes:
  - ADD complete type hints
  - ADD Pydantic models for validation
  - ADD input/output validation
  - FIX missing type annotations
  - ADD runtime type checking
  - ADD schema validation
"""

from typing import (
    Any, Dict, List, Optional, Tuple, Union, TypedDict, Protocol,
    Callable, Generic, TypeVar, overload
)
from datetime import datetime
from enum import Enum
import json
import logging
from pydantic import BaseModel, Field, validator, root_validator
from pydantic import ValidationError as PydanticValidationError
from pathlib import Path

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============ ENUMS ============

class MemoryStatus(str, Enum):
    """Memory status"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class TextSource(str, Enum):
    """Text source types"""
    AUDIO_TRANSCRIPT = "audio_transcript"
    EMAIL = "email"
    SOCIAL_POST = "social_post"
    MEETING = "meeting"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    """Processing status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# ============ PYDANTIC MODELS - MEMORY ============

class MemoryMetadata(BaseModel):
    """Memory metadata"""
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    source_id: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=10)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class MemoryData(BaseModel):
    """Memory data model"""
    id: Optional[str] = None
    uid: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1, max_length=100000)
    metadata: Optional[MemoryMetadata] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    version: int = Field(default=1, ge=1)
    status: MemoryStatus = Field(default=MemoryStatus.ACTIVE)

    @validator('content')
    def content_not_empty(cls, v: str) -> str:
        """Validate content is not empty or whitespace"""
        if not v or not v.strip():
            raise ValueError("content cannot be empty or whitespace")
        return v.strip()

    @validator('uid')
    def uid_valid_format(cls, v: str) -> str:
        """Validate UID format"""
        if not v or not v.strip():
            raise ValueError("uid cannot be empty")
        # Alphanumeric, hyphens, underscores
        if not all(c.isalnum() or c in '-_' for c in v):
            raise ValueError("uid contains invalid characters")
        return v


# ============ PYDANTIC MODELS - OMI API ============

class ConversationData(BaseModel):
    """OMI conversation"""
    id: Optional[str] = None
    text: str = Field(..., min_length=1)
    started_at: str  # ISO 8601
    finished_at: str  # ISO 8601
    language: str = Field(default="en", min_length=2, max_length=5)
    text_source: TextSource = TextSource.OTHER
    text_source_spec: Optional[str] = None
    geolocation: Optional[Dict[str, float]] = None

    @validator('text')
    def text_not_empty(cls, v: str) -> str:
        """Validate text"""
        if not v or not v.strip():
            raise ValueError("text cannot be empty")
        return v.strip()

    @validator('geolocation')
    def geolocation_valid(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        """Validate geolocation"""
        if v is None:
            return v
        if "latitude" in v and "longitude" in v:
            lat, lon = v["latitude"], v["longitude"]
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Invalid latitude/longitude values")
        return v


class MemoryCreationRequest(BaseModel):
    """OMI memory creation request"""
    text: str = Field(..., min_length=1)
    text_source: TextSource = TextSource.OTHER
    text_source_spec: Optional[str] = None
    memories: Optional[List[Dict[str, Any]]] = None


# ============ PYDANTIC MODELS - WEBHOOKS ============

class WebhookMemoryPayload(BaseModel):
    """Webhook memory payload"""
    uid: str = Field(..., min_length=1)
    memory_id: Optional[str] = None
    content: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    class Config:
        extra = "allow"


class WebhookTranscriptPayload(BaseModel):
    """Webhook transcript payload"""
    uid: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    segments: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: Optional[datetime] = None

    class Config:
        extra = "allow"


class WebhookAudioPayload(BaseModel):
    """Webhook audio payload"""
    uid: str = Field(..., min_length=1)
    sample_rate: int = Field(..., ge=8000, le=48000)
    duration_seconds: Optional[float] = None
    codec: Optional[str] = None


# ============ PYDANTIC MODELS - RESPONSES ============

class ApiResponse(BaseModel, Generic[T]):
    """Generic API response"""
    status: str
    message: Optional[str] = None
    data: Optional[T] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True


class MemoryResponse(BaseModel):
    """Memory response"""
    id: str
    uid: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    version: int
    status: MemoryStatus


class ProcessingResult(BaseModel):
    """Processing result"""
    success: bool
    status: ProcessingStatus
    memory_id: Optional[str] = None
    uid: str
    steps_completed: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    processing_time_seconds: Optional[float] = None
    analysis: Optional[Dict[str, Any]] = None


# ============ VALIDATION UTILITIES ============

class TypeValidator:
    """Type validation utilities"""

    @staticmethod
    def validate_uid(uid: Any) -> str:
        """Validate and return UID"""
        if not isinstance(uid, str):
            raise TypeError(f"uid must be str, got {type(uid).__name__}")
        if not uid or not uid.strip():
            raise ValueError("uid cannot be empty")
        if len(uid) > 256:
            raise ValueError("uid too long (max 256 chars)")
        if not all(c.isalnum() or c in '-_' for c in uid):
            raise ValueError("uid contains invalid characters")
        return uid

    @staticmethod
    def validate_memory_id(memory_id: Any) -> str:
        """Validate memory ID"""
        if not isinstance(memory_id, str):
            raise TypeError(f"memory_id must be str, got {type(memory_id).__name__}")
        if not memory_id or len(memory_id) == 0:
            raise ValueError("memory_id cannot be empty")
        if len(memory_id) > 512:
            raise ValueError("memory_id too long")
        return memory_id

    @staticmethod
    def validate_content(content: Any) -> str:
        """Validate memory content"""
        if not isinstance(content, str):
            raise TypeError(f"content must be str, got {type(content).__name__}")
        if not content or not content.strip():
            raise ValueError("content cannot be empty or whitespace only")
        if len(content) > 100000:
            raise ValueError("content too long (max 100000 chars)")
        return content.strip()

    @staticmethod
    def validate_metadata(metadata: Any) -> Dict[str, Any]:
        """Validate metadata"""
        if metadata is None:
            return {}
        if not isinstance(metadata, dict):
            raise TypeError(f"metadata must be dict, got {type(metadata).__name__}")
        # Limit to reasonable size
        if len(json.dumps(metadata)) > 50000:
            raise ValueError("metadata too large")
        return metadata

    @staticmethod
    def validate_tags(tags: Any) -> List[str]:
        """Validate tags list"""
        if not isinstance(tags, list):
            raise TypeError(f"tags must be list, got {type(tags).__name__}")
        if len(tags) > 50:
            raise ValueError("Too many tags (max 50)")
        validated = []
        for tag in tags:
            if not isinstance(tag, str):
                raise TypeError(f"Tag must be str, got {type(tag).__name__}")
            if len(tag) > 100:
                raise ValueError("Tag too long")
            if tag.strip():
                validated.append(tag.strip())
        return validated

    @staticmethod
    def validate_limit(limit: Any, max_limit: int = 1000, default: int = 100) -> int:
        """Validate pagination limit"""
        if limit is None:
            return default
        if not isinstance(limit, int):
            raise TypeError(f"limit must be int, got {type(limit).__name__}")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if limit > max_limit:
            raise ValueError(f"limit exceeds maximum ({max_limit})")
        return limit

    @staticmethod
    def validate_offset(offset: Any) -> int:
        """Validate pagination offset"""
        if offset is None:
            return 0
        if not isinstance(offset, int):
            raise TypeError(f"offset must be int, got {type(offset).__name__}")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        return offset


# ============ SAFE TYPE CONVERSION ============

class SafeTypeConverter:
    """Safe type conversion utilities"""

    @staticmethod
    def to_int(value: Any, default: int = 0) -> int:
        """Safe conversion to int"""
        try:
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
            if isinstance(value, float):
                return int(value)
        except (ValueError, TypeError):
            pass
        return default

    @staticmethod
    def to_float(value: Any, default: float = 0.0) -> float:
        """Safe conversion to float"""
        try:
            if isinstance(value, float):
                return value
            if isinstance(value, int):
                return float(value)
            if isinstance(value, str):
                return float(value)
        except (ValueError, TypeError):
            pass
        return default

    @staticmethod
    def to_bool(value: Any, default: bool = False) -> bool:
        """Safe conversion to bool"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return default

    @staticmethod
    def to_dict(value: Any, default: Optional[Dict] = None) -> Dict[str, Any]:
        """Safe conversion to dict"""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return default or {}

    @staticmethod
    def to_list(value: Any, default: Optional[List] = None) -> List[Any]:
        """Safe conversion to list"""
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return default or []


# ============ PROTOCOL DEFINITIONS ============

class MemoryStoreProtocol(Protocol):
    """Protocol for memory stores"""

    def add_memory(self, uid: str, content: str,
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add memory"""
        ...

    def get_memory(self, uid: str, memory_id: str) -> Optional[MemoryData]:
        """Get memory"""
        ...

    def get_user_memories(self, uid: str, limit: int = 100) -> List[MemoryData]:
        """Get user memories"""
        ...


class OMIClientProtocol(Protocol):
    """Protocol for OMI clients"""

    def create_memories(self, memories: List[Dict[str, Any]],
                       text: str) -> Dict[str, Any]:
        """Create memories"""
        ...

    def read_memories(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read memories"""
        ...
