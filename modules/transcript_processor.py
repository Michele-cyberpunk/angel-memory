"""
Transcript Processor with Gemini AI
Handles transcript cleaning and structuring with fallback chain
"""
from google import genai
from google.genai import types
from typing import Optional, Dict, Any
from config.settings import GeminiConfig
import logging
import time

logger = logging.getLogger(__name__)

class TranscriptProcessor:
    """Process and clean transcripts using Gemini AI with fallback chain"""

    def __init__(self):
        GeminiConfig.validate()
        self.client = genai.Client(api_key=GeminiConfig.API_KEY)

        self.primary_model = GeminiConfig.PRIMARY_MODEL
        self.fallback_model = GeminiConfig.FALLBACK_MODEL
        self.lite_model = GeminiConfig.LITE_MODEL

        logger.info(f"Initialized TranscriptProcessor with models: {self.primary_model} -> {self.fallback_model} -> {self.lite_model}")

    def process_transcript(self, transcript_raw: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Process raw transcript with Gemini AI

        Args:
            transcript_raw: Raw transcript text (potentially imprecise)
            context: Optional context information

        Returns:
            Dict with cleaned_text, success status, and model used
        """
        if not transcript_raw or not transcript_raw.strip():
            logger.warning("Empty transcript provided")
            return {
                "cleaned_text": "",
                "success": False,
                "error": "Empty transcript",
                "model_used": None
            }

        # Try primary model first
        result = self._clean_with_gemini(transcript_raw, self.primary_model, context)
        if result["success"]:
            return result

        logger.warning(f"Primary model {self.primary_model} failed, trying fallback")

        # Fallback to Pro model
        result = self._clean_with_gemini(transcript_raw, self.fallback_model, context)
        if result["success"]:
            return result

        logger.warning(f"Fallback model {self.fallback_model} failed, trying lite model")

        # Final fallback to Flash-Lite
        result = self._clean_with_gemini(transcript_raw, self.lite_model, context)
        if result["success"]:
            return result

        # All models failed
        logger.error("All Gemini models failed to process transcript")
        return {
            "cleaned_text": transcript_raw,  # Return original as fallback
            "success": False,
            "error": "All models failed",
            "model_used": None
        }

    def _clean_with_gemini(self, text: str, model_name: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Clean transcript using specific Gemini model

        Args:
            text: Raw transcript text
            model_name: Gemini model identifier
            context: Optional context information

        Returns:
            Dict with cleaned_text, success status, and model_used
        """
        prompt = self._build_cleaning_prompt(text, context)

        try:
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

            if not response or not response.text:
                logger.warning(f"Model {model_name} returned empty response")
                return {
                    "cleaned_text": "",
                    "success": False,
                    "error": "Empty response",
                    "model_used": model_name
                }

            cleaned_text = response.text.strip()
            logger.info(f"Successfully cleaned transcript with {model_name} in {elapsed:.2f}s")

            return {
                "cleaned_text": cleaned_text,
                "success": True,
                "model_used": model_name,
                "processing_time": elapsed
            }

        except Exception as e:
            logger.error(f"Error with model {model_name}: {str(e)}")
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
