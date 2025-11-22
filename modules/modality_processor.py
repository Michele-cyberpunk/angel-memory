"""
Abstract base classes for multimodal and multilingual processing
Provides extensible interfaces for different input modalities and language support
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, BinaryIO
from dataclasses import dataclass
from enum import Enum
import logging

from config.settings import AppSettings

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class ModalityType(Enum):
    """Supported input modalities"""
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"  # Future extension

class ProcessingResult:
    """Standardized result structure for all processors"""

    def __init__(self, success: bool, modality: ModalityType, content: Any = None,
                 metadata: Optional[Dict[str, Any]] = None, error: Optional[str] = None,
                 processing_time: Optional[float] = None, model_used: Optional[str] = None):
        self.success = success
        self.modality = modality
        self.content = content  # Processed content (text, features, etc.)
        self.metadata = metadata or {}
        self.error = error
        self.processing_time = processing_time
        self.model_used = model_used

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "success": self.success,
            "modality": self.modality.value,
            "content": self.content,
            "metadata": self.metadata,
            "error": self.error,
            "processing_time": self.processing_time,
            "model_used": self.model_used
        }

class BaseModalityProcessor(ABC):
    """Abstract base class for all modality processors"""

    def __init__(self, modality_type: ModalityType):
        self.modality_type = modality_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def validate_input(self, input_data: Any) -> bool:
        """Validate input data for this modality"""
        pass

    @abstractmethod
    def process(self, input_data: Any, **kwargs) -> ProcessingResult:
        """Process input data and return standardized result"""
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Return list of supported input formats"""
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """Return processor capabilities and limits"""
        return {
            "modality": self.modality_type.value,
            "supported_formats": self.get_supported_formats(),
            "max_input_size": getattr(self, 'max_input_size', None),
            "requires_api": getattr(self, 'requires_api', True)
        }

class TextProcessor(BaseModalityProcessor):
    """Base class for text-based processors (transcripts, documents, etc.)"""

    def __init__(self):
        super().__init__(ModalityType.TEXT)
        self.max_input_size = 100000  # characters

    def validate_input(self, input_data: Any) -> bool:
        """Validate text input"""
        if not isinstance(input_data, str):
            return False
        if len(input_data.strip()) == 0:
            return False
        if len(input_data) > self.max_input_size:
            return False
        return True

    @abstractmethod
    def process(self, input_data: str, **kwargs) -> ProcessingResult:
        """Process text input"""
        pass

    def get_supported_formats(self) -> List[str]:
        return ["text/plain", "text/markdown", "text/html"]

class AudioProcessor(BaseModalityProcessor):
    """Base class for audio processors"""

    def __init__(self):
        super().__init__(ModalityType.AUDIO)
        from config.settings import MultimodalConfig
        self.sample_rate = MultimodalConfig.AUDIO_SAMPLE_RATE
        self.channels = MultimodalConfig.AUDIO_CHANNELS
        self.max_duration = MultimodalConfig.MAX_AUDIO_DURATION_SECONDS
        self.max_input_size = self.max_duration * self.sample_rate * self.channels * 2  # 16-bit

    def validate_input(self, input_data: Any) -> bool:
        """Validate audio input (bytes or file-like object)"""
        if isinstance(input_data, bytes):
            if len(input_data) > self.max_input_size:
                return False
            return True
        elif hasattr(input_data, 'read'):  # File-like object
            try:
                # Try to get size without reading entire file
                if hasattr(input_data, 'seek'):
                    input_data.seek(0, 2)  # Seek to end
                    size = input_data.tell()
                    input_data.seek(0)  # Reset to beginning
                    return size <= self.max_input_size
            except:
                pass
            return True
        return False

    @abstractmethod
    def process(self, input_data: Union[bytes, BinaryIO], **kwargs) -> ProcessingResult:
        """Process audio input"""
        pass

    def get_supported_formats(self) -> List[str]:
        return ["audio/wav", "audio/mp3", "audio/m4a", "audio/flac", "audio/ogg"]

class ImageProcessor(BaseModalityProcessor):
    """Base class for image processors"""

    def __init__(self):
        super().__init__(ModalityType.IMAGE)
        from config.settings import MultimodalConfig
        self.max_size_mb = MultimodalConfig.MAX_IMAGE_SIZE_MB
        self.supported_formats = MultimodalConfig.SUPPORTED_IMAGE_FORMATS
        self.max_input_size = self.max_size_mb * 1024 * 1024  # bytes

    def validate_input(self, input_data: Any) -> bool:
        """Validate image input"""
        if isinstance(input_data, bytes):
            if len(input_data) > self.max_input_size:
                return False
            # Basic format check by looking at file header
            if len(input_data) < 4:
                return False
            # Check common image headers
            headers = {
                b'\xff\xd8\xff': 'jpg',
                b'\x89PNG\r\n\x1a\n': 'png',
                b'GIF87a': 'gif',
                b'GIF89a': 'gif',
                b'RIFF': 'webp',  # WebP has RIFF header
                b'BM': 'bmp'
            }
            for header, ext in headers.items():
                if input_data.startswith(header):
                    return ext in self.supported_formats
            return False
        elif hasattr(input_data, 'read'):  # File-like object
            try:
                if hasattr(input_data, 'seek'):
                    input_data.seek(0, 2)
                    size = input_data.tell()
                    input_data.seek(0)
                    return size <= self.max_input_size
            except:
                pass
            return True
        return False

    @abstractmethod
    def process(self, input_data: Union[bytes, BinaryIO], **kwargs) -> ProcessingResult:
        """Process image input"""
        pass

    def get_supported_formats(self) -> List[str]:
        return [f"image/{fmt}" for fmt in self.supported_formats]

class LanguageProcessor:
    """Mixin class for language detection and translation capabilities"""

    def __init__(self):
        from config.settings import MultilingualConfig
        self.enable_detection = MultilingualConfig.ENABLE_LANGUAGE_DETECTION
        self.enable_translation = MultilingualConfig.ENABLE_TRANSLATION
        self.supported_languages = MultilingualConfig.SUPPORTED_LANGUAGES
        self.default_language = MultilingualConfig.DEFAULT_LANGUAGE
        self.confidence_threshold = MultilingualConfig.CONFIDENCE_THRESHOLD

    def detect_language(self, text: str) -> Dict[str, Any]:
        """Detect language of input text"""
        if not self.enable_detection:
            return {"language": self.default_language, "confidence": 1.0}

        # Placeholder for language detection implementation
        # In practice, this would use a language detection library or API
        return {"language": self.default_language, "confidence": 1.0}

    def translate_text(self, text: str, target_language: str, source_language: Optional[str] = None) -> Dict[str, Any]:
        """Translate text to target language"""
        if not self.enable_translation:
            return {"translated_text": text, "source_language": source_language or self.default_language}

        if target_language not in self.supported_languages:
            raise ValueError(f"Unsupported target language: {target_language}")

        # Placeholder for translation implementation
        # In practice, this would use a translation service or API
        return {"translated_text": text, "source_language": source_language or self.default_language}