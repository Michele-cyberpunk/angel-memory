"""
Transcript Processor with Gemini AI
Handles transcript cleaning and structuring with fallback chain
"""
from google import genai
from google.genai import types
from typing import Optional, Dict, Any
from config.settings import GeminiConfig, AppSettings
from modules.api_utils import with_gemini_rate_limit_and_retry
import logging
import time

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class TranscriptProcessor:
    """Process and clean transcripts using Gemini AI with fallback chain"""

    def __init__(self):
        try:
            GeminiConfig.validate()
            self.client = genai.Client(api_key=GeminiConfig.API_KEY)
            logger.debug("Gemini client initialized for transcript processing")
        except Exception as e:
            logger.error("Failed to initialize Gemini client for transcript processing", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        self.primary_model = GeminiConfig.PRIMARY_MODEL
        self.fallback_model = GeminiConfig.FALLBACK_MODEL
        self.lite_model = GeminiConfig.LITE_MODEL

        logger.info("TranscriptProcessor initialized successfully", extra={
            "models": [self.primary_model, self.fallback_model, self.lite_model]
        })

    def process_transcript(self, transcript_raw: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Process raw transcript with Gemini AI

        Args:
            transcript_raw: Raw transcript text (potentially imprecise)
            context: Optional context information

        Returns:
            Dict with cleaned_text, success status, and model used
        """
        # Input validation
        if not isinstance(transcript_raw, str):
            raise ValueError("transcript_raw must be a string")

        if context is not None and not isinstance(context, str):
            raise ValueError("context must be a string or None")

        transcript_raw = transcript_raw.strip()
        if not transcript_raw:
            logger.warning("Empty transcript provided")
            return {
                "cleaned_text": "",
                "success": False,
                "error": "Empty transcript",
                "model_used": None
            }

        # Check length limits (Gemini has token limits)
        if len(transcript_raw) > 100000:  # Rough character limit
            logger.warning(f"Transcript too long: {len(transcript_raw)} characters")
            return {
                "cleaned_text": transcript_raw[:50000] + "...[truncated]",  # Return truncated version
                "success": False,
                "error": "Transcript too long",
                "model_used": None
            }

        try:
            # Try primary model first
            result = self._clean_with_gemini(transcript_raw, self.primary_model, context)
            if result["success"]:
                return result

            logger.warning(f"Primary model {self.primary_model} failed after {result.get('attempts_used', 1)} attempts, falling back to {self.fallback_model}")

            # Fallback to Flash model
            result = self._clean_with_gemini(transcript_raw, self.fallback_model, context)
            if result["success"]:
                logger.info(f"Successfully processed transcript using fallback model {self.fallback_model}")
                return result

            logger.warning(f"Fallback model {self.fallback_model} failed after {result.get('attempts_used', 1)} attempts, falling back to {self.lite_model}")

            # Final fallback to Flash-Lite
            result = self._clean_with_gemini(transcript_raw, self.lite_model, context)
            if result["success"]:
                logger.info(f"Successfully processed transcript using lite fallback model {self.lite_model}")
                return result

            # All models failed
            logger.error("All Gemini models failed to process transcript")
            return {
                "cleaned_text": transcript_raw,  # Return original as fallback
                "success": False,
                "error": "All models failed",
                "model_used": None
            }

        except Exception as e:
            logger.error(f"Unexpected error in process_transcript: {str(e)}", exc_info=True)
            return {
                "cleaned_text": transcript_raw,
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "model_used": None
            }

    @with_gemini_rate_limit_and_retry
    def _call_gemini_api(self, model_name: str, prompt: str) -> Any:
        """
        Call Gemini API with rate limiting and retry logic

        Args:
            model_name: Gemini model identifier
            prompt: Prompt text

        Returns:
            API response object
        """
        # Configure generation parameters
        config = types.GenerateContentConfig(
            temperature=0.3,  # Lower temperature for more consistent cleaning
            top_p=0.8,
            top_k=40,
            max_output_tokens=4096,
        )

        start_time = time.time()
        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        elapsed = time.time() - start_time

        logger.debug(f"Gemini API call completed in {elapsed:.2f}s for model {model_name}")
        return response

    def _clean_with_gemini(self, text: str, model_name: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Clean transcript using specific Gemini model with rate limiting and retry logic

        Args:
            text: Raw transcript text
            model_name: Gemini model identifier
            context: Optional context information

        Returns:
            Dict with cleaned_text, success status, and model_used
        """
        prompt = self._build_cleaning_prompt(text, context)

        try:
            response = self._call_gemini_api(model_name, prompt)

            if not response or not response.text:
                logger.warning(f"Model {model_name} returned empty response")
                return {
                    "cleaned_text": "",
                    "success": False,
                    "error": "Empty response",
                    "model_used": model_name
                }

            cleaned_text = response.text.strip()
            logger.info(f"Successfully cleaned transcript with {model_name}")

            return {
                "cleaned_text": cleaned_text,
                "success": True,
                "model_used": model_name
            }

        except Exception as e:
            logger.error(f"All retry attempts failed for model {model_name}: {str(e)}")
            return {
                "cleaned_text": "",
                "success": False,
                "error": str(e),
                "model_used": model_name
            }

    def _build_cleaning_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for transcript cleaning"""

        base_prompt = f"""You are a professional transcript editor. Your task is to clean and structure this conversational transcript.

The transcript may contain:
- Speech recognition errors
- Unclear or ambiguous phrases
- Incomplete sentences
- Filler words that should be preserved if meaningful
- Multiple speakers

Your job:
1. Fix obvious speech recognition errors
2. Correct grammar and punctuation
3. Maintain the original meaning and conversational tone
4. Keep all meaningful content, including natural speech patterns
5. Structure into clear paragraphs if multiple topics
6. DO NOT add information that wasn't in the original
7. DO NOT over-correct casual language if it's intentional

{"Context: " + context if context else ""}

Raw Transcript:
{text}

Cleaned Transcript:"""

        return base_prompt

    def batch_process(self, transcripts: list[str], context: Optional[str] = None) -> list[Dict[str, Any]]:
        """
        Process multiple transcripts

        Args:
            transcripts: List of raw transcripts
            context: Optional shared context

        Returns:
            List of processing results
        """
        results = []
        for i, transcript in enumerate(transcripts):
            logger.info(f"Processing transcript {i+1}/{len(transcripts)}")
            result = self.process_transcript(transcript, context)
            results.append(result)

        return results
