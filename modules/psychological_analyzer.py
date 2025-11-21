"""
Psychological Analyzer using Gemini AI
Analyzes transcripts for ADHD indicators, anxiety patterns, and emotional tone
"""

from google import genai
from google.genai import types
from typing import Dict, Any, Optional
from config.settings import GeminiConfig, AppSettings
from modules.api_utils import with_gemini_rate_limit_and_retry
import logging
import json
import re
import hashlib
from functools import lru_cache

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class PsychologicalAnalyzer:
    """Analyze transcripts for psychological patterns using Gemini AI"""

    def __init__(self):
        try:
            GeminiConfig.validate()
            self.client = genai.Client(api_key=GeminiConfig.API_KEY)
            logger.debug("Gemini client initialized for psychological analysis")
        except Exception as e:
            logger.error("Failed to initialize Gemini client for psychological analysis", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        # Model fallback chain for complex psychological analysis
        self.models = [
            GeminiConfig.PRIMARY_MODEL,    # gemini-2.5-pro
            GeminiConfig.FALLBACK_MODEL,   # gemini-2.5-flash
            GeminiConfig.LITE_MODEL        # gemini-2.5-flash-lite
        ]

        # Simple in-memory cache for analysis results (LRU cache with 100 entries)
        self._analysis_cache = {}

        logger.info("PsychologicalAnalyzer initialized successfully", extra={
            "models": self.models
        })

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
        config = types.GenerateContentConfig(
            temperature=0.4,
            top_p=0.9,
            top_k=40,
            max_output_tokens=2048,
        )

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )

        return response

    def analyze(self, transcript: str, include_details: bool = True) -> Dict[str, Any]:
        """
        Analyze transcript for psychological patterns

        Args:
            transcript: Cleaned transcript text
            include_details: Include detailed evidence in response

        Returns:
            Dictionary with analysis results
        """
        # Input validation
        if not isinstance(transcript, str):
            raise ValueError("transcript must be a string")

        if not isinstance(include_details, bool):
            raise ValueError("include_details must be a boolean")

        transcript = transcript.strip()
        if not transcript:
            logger.warning("Empty transcript provided for analysis")
            return self._empty_analysis()

        # Quick return for very short transcripts (skip expensive analysis)
        if len(transcript) < 50:
            logger.debug("Transcript too short for full analysis, returning minimal result")
            return self._minimal_analysis()

        # Check cache first
        cache_key = self._get_cache_key(transcript, include_details)
        if cache_key in self._analysis_cache:
            logger.debug("Returning cached analysis result")
            return self._analysis_cache[cache_key]

        # Check reasonable length limits
        if len(transcript) > 50000:  # Rough limit for analysis
            logger.warning(f"Transcript too long for analysis: {len(transcript)} characters")
            transcript = transcript[:25000] + "...[truncated for analysis]"

        prompt = self._build_analysis_prompt(transcript, include_details)

        # Try models in fallback chain with rate limiting and retry
        last_error = None
        for model_name in self.models:
            try:
                logger.info(f"Attempting psychological analysis with model: {model_name}")

                # Use the decorated method for API calls
                response = self._call_gemini_api(model_name, prompt)

                if not response or not response.text:
                    logger.warning(f"Empty response from {model_name}, trying next model")
                    last_error = f"Empty response from {model_name}"
                    continue

                # Parse JSON response
                analysis_result = self._parse_analysis_response(response.text)

                logger.info(f"Psychological analysis completed with {model_name} - "
                           f"ADHD: {analysis_result.get('adhd_indicators', {}).get('score', 0)}/10, "
                           f"Anxiety: {analysis_result.get('anxiety_patterns', {}).get('score', 0)}/10, "
                           f"Biases: {analysis_result.get('cognitive_biases', {}).get('score', 0)}/10")

                # Cache the result
                self._cache_result(cache_key, analysis_result)

                return analysis_result

            except Exception as e:
                logger.warning(f"Model {model_name} failed after retries: {str(e)}, trying next model")
                last_error = f"{model_name}: {str(e)}"
                continue

        # All models failed
        logger.error(f"All models in fallback chain failed. Last error: {last_error}")
        return self._empty_analysis(error=f"All models failed: {last_error}")

    def _build_analysis_prompt(self, transcript: str, include_details: bool) -> str:
        """Build prompt for psychological analysis"""

        details_instruction = """
        For each indicator found, provide specific evidence from the transcript.
        """ if include_details else """
        Provide scores and themes only, without detailed evidence.
        """

        prompt = f"""You are a clinical psychologist assistant analyzing conversational patterns.
Analyze this transcript for psychological indicators. Be objective and evidence-based.

IMPORTANT DISCLAIMERS:
- This is a preliminary screening tool, NOT a diagnostic instrument
- Patterns may be contextual and not indicative of disorders
- Professional evaluation is required for any diagnosis

Analyze for:

1. **ADHD Indicators** (score 0-10):
   - Rapid topic changes without completion
   - Impulsive verbal patterns
   - Difficulty maintaining focus on single subject
   - Tangential thinking
   - High-energy, scattered communication style

2. **Anxiety Patterns** (score 0-10):
   - Repetitive worries or concerns
   - Catastrophic thinking
   - Rumination on specific topics
   - Excessive detail on worries
   - Uncertainty and reassurance-seeking

3. **Cognitive Biases** (score 0-10):
   - Black-and-white/all-or-nothing thinking
   - Catastrophizing or fortune-telling
   - Overgeneralization from limited evidence
   - Personalization (taking things personally)
   - Emotional reasoning (believing something because it feels true)
   - Confirmation bias (seeking information that confirms existing beliefs)

4. **Emotional Tone**:
   - Overall emotional state (e.g., neutral, anxious, excited, melancholic)
   - Emotional stability vs. volatility
   - Dominant emotions present

{details_instruction}

Respond with ONLY valid JSON in this exact format:
{{
    "adhd_indicators": {{
        "score": <0-10>,
        "evidence": [<list of specific quotes or patterns>],
        "confidence": "<low|medium|high>"
    }},
    "anxiety_patterns": {{
        "score": <0-10>,
        "themes": [<list of recurring anxiety themes>],
        "confidence": "<low|medium|high>"
    }},
    "cognitive_biases": {{
        "score": <0-10>,
        "identified_biases": [<list of specific cognitive biases detected>],
        "confidence": "<low|medium|high>"
    }},
    "emotional_tone": {{
        "primary_emotion": "<emotion name>",
        "stability": "<stable|variable|volatile>",
        "description": "<brief description>"
    }},
    "overall_assessment": "<brief 1-2 sentence summary>",
    "recommendations": [<optional list of suggestions, e.g., 'Consider mindfulness practices', 'May benefit from structured task management'>]
}}

Transcript:
{transcript}

JSON Response:"""

        return prompt

    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response from Gemini"""
        try:
            # Try to extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                json_text = response_text.strip()

            analysis = json.loads(json_text)

            # Validate structure
            required_keys = ["adhd_indicators", "anxiety_patterns", "cognitive_biases", "emotional_tone"]
            for key in required_keys:
                if key not in analysis:
                    logger.warning(f"Missing key in analysis: {key}")
                    analysis[key] = {}

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response_text}")
            return self._empty_analysis(error=f"JSON parse error: {str(e)}")

    def _get_cache_key(self, transcript: str, include_details: bool) -> str:
        """Generate cache key for transcript analysis"""
        # Create hash of transcript and settings
        content = f"{transcript[:1000]}|{include_details}"  # Limit to first 1000 chars for key
        return hashlib.md5(content.encode()).hexdigest()

    def _cache_result(self, key: str, result: Dict[str, Any]):
        """Cache analysis result (simple LRU with max 50 entries)"""
        if len(self._analysis_cache) >= 50:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._analysis_cache))
            del self._analysis_cache[oldest_key]
        self._analysis_cache[key] = result

    def _minimal_analysis(self) -> Dict[str, Any]:
        """Return minimal analysis for short transcripts"""
        return {
            "adhd_indicators": {
                "score": 0,
                "evidence": [],
                "confidence": "low"
            },
            "anxiety_patterns": {
                "score": 0,
                "themes": [],
                "confidence": "low"
            },
            "cognitive_biases": {
                "score": 0,
                "identified_biases": [],
                "confidence": "low"
            },
            "emotional_tone": {
                "primary_emotion": "neutral",
                "stability": "stable",
                "description": "Brief interaction - limited analysis possible"
            },
            "overall_assessment": "Brief conversation - minimal psychological indicators detected",
            "recommendations": [],
            "analysis_type": "minimal"
        }

    def _empty_analysis(self, error: Optional[str] = None) -> Dict[str, Any]:
        """Return empty analysis structure"""
        return {
            "adhd_indicators": {
                "score": 0,
                "evidence": [],
                "confidence": "low"
            },
            "anxiety_patterns": {
                "score": 0,
                "themes": [],
                "confidence": "low"
            },
            "cognitive_biases": {
                "score": 0,
                "identified_biases": [],
                "confidence": "low"
            },
            "emotional_tone": {
                "primary_emotion": "unknown",
                "stability": "unknown",
                "description": "Unable to analyze"
            },
            "overall_assessment": "Analysis could not be completed",
            "recommendations": [],
            "error": error
        }

    def generate_summary(self, analysis: Dict[str, Any]) -> str:
        """
        Generate human-readable summary from analysis

        Args:
            analysis: Analysis results dictionary

        Returns:
            Formatted summary string
        """
        adhd_score = analysis.get("adhd_indicators", {}).get("score", 0)
        anxiety_score = analysis.get("anxiety_patterns", {}).get("score", 0)
        bias_score = analysis.get("cognitive_biases", {}).get("score", 0)
        emotion = analysis.get("emotional_tone", {}).get("primary_emotion", "unknown")
        assessment = analysis.get("overall_assessment", "No assessment available")

        summary = f"""Psychological Analysis Summary:

ADHD Indicators: {adhd_score}/10 ({self._score_interpretation(adhd_score)})
Anxiety Patterns: {anxiety_score}/10 ({self._score_interpretation(anxiety_score)})
Cognitive Biases: {bias_score}/10 ({self._score_interpretation(bias_score)})
Primary Emotion: {emotion.capitalize()}

Assessment: {assessment}
"""

        # Add cognitive biases details if present
        biases = analysis.get("cognitive_biases", {}).get("identified_biases", [])
        if biases:
            summary += f"\nIdentified Biases: {', '.join(biases)}\n"

        recommendations = analysis.get("recommendations", [])
        if recommendations:
            summary += "\nRecommendations:\n"
            for rec in recommendations:
                summary += f"- {rec}\n"

        return summary

    def _score_interpretation(self, score: int) -> str:
        """Interpret numerical score"""
        if score <= 2:
            return "Minimal"
        elif score <= 4:
            return "Low"
        elif score <= 6:
            return "Moderate"
        elif score <= 8:
            return "Elevated"
        else:
            return "High"
