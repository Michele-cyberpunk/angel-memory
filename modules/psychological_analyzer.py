"""
Psychological Analyzer using Gemini AI
Analyzes transcripts for ADHD indicators, anxiety patterns, and emotional tone
"""

from google import genai
from google.genai import types
from typing import Dict, Any, Optional
from config.settings import GeminiConfig
import logging
import json
import re

logger = logging.getLogger(__name__)

class PsychologicalAnalyzer:
    """Analyze transcripts for psychological patterns using Gemini AI"""

    def __init__(self):
        GeminiConfig.validate()
        self.client = genai.Client(api_key=GeminiConfig.API_KEY)

        # Use Pro model for complex psychological analysis
        self.model_name = GeminiConfig.FALLBACK_MODEL
        
        logger.info(f"Initialized PsychologicalAnalyzer with model: {self.model_name}")

    def analyze(self, transcript: str, include_details: bool = True) -> Dict[str, Any]:
        """
        Analyze transcript for psychological patterns

        Args:
            transcript: Cleaned transcript text
            include_details: Include detailed evidence in response

        Returns:
            Dictionary with analysis results
        """
        if not transcript or not transcript.strip():
            logger.warning("Empty transcript provided for analysis")
            return self._empty_analysis()

        prompt = self._build_analysis_prompt(transcript, include_details)

        try:
            config = types.GenerateContentConfig(
                temperature=0.4,
                top_p=0.9,
                top_k=40,
                max_output_tokens=2048,
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )

            if not response or not response.text:
                logger.error("Empty response from Gemini")
                return self._empty_analysis(error="Empty response from AI")

            # Parse JSON response
            analysis_result = self._parse_analysis_response(response.text)

            logger.info(f"Psychological analysis completed - ADHD: {analysis_result.get('adhd_indicators', {}).get('score', 0)}/10, "
                       f"Anxiety: {analysis_result.get('anxiety_patterns', {}).get('score', 0)}/10")

            return analysis_result

        except Exception as e:
            logger.error(f"Error during psychological analysis: {str(e)}")
            return self._empty_analysis(error=str(e))

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

3. **Emotional Tone**:
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
            required_keys = ["adhd_indicators", "anxiety_patterns", "emotional_tone"]
            for key in required_keys:
                if key not in analysis:
                    logger.warning(f"Missing key in analysis: {key}")
                    analysis[key] = {}

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response_text}")
            return self._empty_analysis(error=f"JSON parse error: {str(e)}")

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
        emotion = analysis.get("emotional_tone", {}).get("primary_emotion", "unknown")
        assessment = analysis.get("overall_assessment", "No assessment available")

        summary = f"""Psychological Analysis Summary:

ADHD Indicators: {adhd_score}/10 ({self._score_interpretation(adhd_score)})
Anxiety Patterns: {anxiety_score}/10 ({self._score_interpretation(anxiety_score)})
Primary Emotion: {emotion.capitalize()}

Assessment: {assessment}
"""

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
