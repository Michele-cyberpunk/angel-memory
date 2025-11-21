"""
Example custom processor plugin
This demonstrates how to extend the system with custom modality processors
"""
from modules.modality_processor import TextProcessor, ProcessingResult
from config.settings import AppSettings

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

import logging
logger = logging.getLogger(__name__)

class CustomTextProcessor(TextProcessor):
    """Example custom text processor with specialized functionality"""

    def __init__(self):
        super().__init__()
        self.custom_feature_enabled = True
        logger.info("Custom text processor initialized")

    def process(self, input_data: str, **kwargs) -> ProcessingResult:
        """Process text with custom logic"""
        import time
        start_time = time.time()

        try:
            # Add custom processing logic here
            # For example: specialized text analysis, custom formatting, etc.

            # Basic validation
            if not self.validate_input(input_data):
                return ProcessingResult(
                    success=False,
                    modality=self.modality_type,
                    error="Invalid input data"
                )

            # Custom processing (placeholder)
            processed_text = f"[CUSTOM] {input_data.upper()} [/CUSTOM]"

            return ProcessingResult(
                success=True,
                modality=self.modality_type,
                content=processed_text,
                metadata={
                    "custom_processing": True,
                    "original_length": len(input_data),
                    "processed_length": len(processed_text)
                },
                processing_time=time.time() - start_time,
                model_used="custom_processor_v1.0"
            )

        except Exception as e:
            logger.error(f"Custom processing failed: {str(e)}")
            return ProcessingResult(
                success=False,
                modality=self.modality_type,
                error=str(e),
                processing_time=time.time() - start_time
            )

    def get_supported_formats(self) -> list[str]:
        """Return supported formats including custom ones"""
        return super().get_supported_formats() + ["text/custom"]

# This processor will be automatically discovered and registered
# by the ProcessorRegistry when the system starts