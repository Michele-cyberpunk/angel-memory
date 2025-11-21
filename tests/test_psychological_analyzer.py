"""
Unit tests for psychological_analyzer.py module
Tests psychological analysis using Gemini AI
"""
import pytest
from unittest.mock import patch, MagicMock

from modules.psychological_analyzer import PsychologicalAnalyzer


class TestPsychologicalAnalyzerInit:
    """Test PsychologicalAnalyzer initialization"""

    @patch('modules.psychological_analyzer.genai.Client')
    def test_init_success(self, mock_genai_client):
        """Test successful initialization"""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client

        analyzer = PsychologicalAnalyzer()

        assert analyzer.client == mock_client
        assert len(analyzer.models) == 3
        assert analyzer._analysis_cache == {}

    @patch('modules.psychological_analyzer.genai.Client')
    @patch('modules.psychological_analyzer.GeminiConfig.validate')
    def test_init_config_validation(self, mock_validate, mock_genai_client):
        """Test that config validation is called during init"""
        PsychologicalAnalyzer()
        mock_validate.assert_called_once()


class TestPsychologicalAnalyzerAnalyze:
    """Test analysis functionality"""

    @patch('modules.psychological_analyzer.genai.Client')
    def test_analyze_empty_transcript(self, mock_genai_client):
        """Test analysis with empty transcript"""
        analyzer = PsychologicalAnalyzer()

        result = analyzer.analyze("")

        assert result["adhd_indicators"]["score"] == 0
        assert result["anxiety_patterns"]["score"] == 0
        assert result["emotional_tone"]["primary_emotion"] == "unknown"

    @patch('modules.psychological_analyzer.genai.Client')
    def test_analyze_short_transcript(self, mock_genai_client):
        """Test analysis with very short transcript"""
        analyzer = PsychologicalAnalyzer()

        result = analyzer.analyze("Hi")

        assert result["analysis_type"] == "minimal"
        assert result["adhd_indicators"]["score"] == 0

    def test_analyze_invalid_input_type(self):
        """Test analysis with invalid input type"""
        analyzer = PsychologicalAnalyzer()

        with pytest.raises(ValueError, match="transcript must be a string"):
            analyzer.analyze(123)

        with pytest.raises(ValueError, match="include_details must be a boolean"):
            analyzer.analyze("test", include_details="invalid")

    @patch('modules.psychological_analyzer.genai.Client')
    def test_analyze_long_transcript(self, mock_genai_client):
        """Test analysis with overly long transcript"""
        analyzer = PsychologicalAnalyzer()

        long_transcript = "word " * 10000  # Very long transcript

        # Mock successful response
        mock_response = MagicMock()
        mock_response.text = '{"adhd_indicators": {"score": 5, "evidence": [], "confidence": "medium"}, "anxiety_patterns": {"score": 3, "themes": [], "confidence": "low"}, "cognitive_biases": {"score": 2, "identified_biases": [], "confidence": "low"}, "emotional_tone": {"primary_emotion": "neutral", "stability": "stable", "description": "Neutral"}, "overall_assessment": "Normal conversation", "recommendations": []}'
        analyzer.client.models.generate_content.return_value = mock_response

        result = analyzer.analyze(long_transcript)

        assert result["adhd_indicators"]["score"] == 5
        # Should have been truncated for analysis
        analyzer.client.models.generate_content.assert_called_once()

    @patch('modules.psychological_analyzer.genai.Client')
    def test_analyze_success_primary_model(self, mock_genai_client):
        """Test successful analysis with primary model"""
        analyzer = PsychologicalAnalyzer()

        # Mock successful response
        mock_response = MagicMock()
        mock_response.text = '{"adhd_indicators": {"score": 7, "evidence": ["rapid topic changes"], "confidence": "high"}, "anxiety_patterns": {"score": 8, "themes": ["worry"], "confidence": "high"}, "cognitive_biases": {"score": 4, "identified_biases": ["catastrophizing"], "confidence": "medium"}, "emotional_tone": {"primary_emotion": "anxious", "stability": "variable", "description": "Anxious tone"}, "overall_assessment": "High anxiety indicators present", "recommendations": ["Consider mindfulness"]}'
        analyzer.client.models.generate_content.return_value = mock_response

        result = analyzer.analyze("I keep worrying about everything that could go wrong")

        assert result["adhd_indicators"]["score"] == 7
        assert result["anxiety_patterns"]["score"] == 8
        assert result["emotional_tone"]["primary_emotion"] == "anxious"
        assert "mindfulness" in result["recommendations"][0]

    @patch('modules.psychological_analyzer.genai.Client')
    def test_analyze_fallback_to_secondary_model(self, mock_genai_client):
        """Test fallback to secondary model when primary fails"""
        analyzer = PsychologicalAnalyzer()

        # Mock primary failure, secondary success
        call_count = 0
        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count == 1:
                mock_response.text = ""  # Primary fails
            else:
                mock_response.text = '{"adhd_indicators": {"score": 3, "evidence": [], "confidence": "low"}, "anxiety_patterns": {"score": 2, "themes": [], "confidence": "low"}, "cognitive_biases": {"score": 1, "identified_biases": [], "confidence": "low"}, "emotional_tone": {"primary_emotion": "neutral", "stability": "stable", "description": "Neutral"}, "overall_assessment": "Normal", "recommendations": []}'
            return mock_response

        analyzer.client.models.generate_content.side_effect = mock_generate_content

        result = analyzer.analyze("Normal conversation text")

        assert call_count == 2  # Primary + fallback
        assert result["adhd_indicators"]["score"] == 3

    @patch('modules.psychological_analyzer.genai.Client')
    def test_analyze_all_models_fail(self, mock_genai_client):
        """Test when all models fail"""
        analyzer = PsychologicalAnalyzer()

        # Mock all models failing
        mock_response = MagicMock()
        mock_response.text = ""
        analyzer.client.models.generate_content.return_value = mock_response

        result = analyzer.analyze("Test transcript")

        assert result["error"] == "All models failed: Empty response from models/gemini-2.5-flash-lite"
        assert result["adhd_indicators"]["score"] == 0

    @patch('modules.psychological_analyzer.genai.Client')
    def test_analyze_invalid_json_response(self, mock_genai_client):
        """Test handling of invalid JSON response"""
        analyzer = PsychologicalAnalyzer()

        # Mock invalid JSON response
        mock_response = MagicMock()
        mock_response.text = "Invalid JSON response"
        analyzer.client.models.generate_content.return_value = mock_response

        result = analyzer.analyze("Test transcript")

        assert "JSON parse error" in result["error"]
        assert result["adhd_indicators"]["score"] == 0


class TestPsychologicalAnalyzerCache:
    """Test caching functionality"""

    @patch('modules.psychological_analyzer.genai.Client')
    def test_cache_hit(self, mock_genai_client):
        """Test cache hit returns cached result"""
        analyzer = PsychologicalAnalyzer()

        # First call - should cache
        mock_response = MagicMock()
        mock_response.text = '{"adhd_indicators": {"score": 5, "evidence": [], "confidence": "medium"}, "anxiety_patterns": {"score": 3, "themes": [], "confidence": "low"}, "cognitive_biases": {"score": 2, "identified_biases": [], "confidence": "low"}, "emotional_tone": {"primary_emotion": "neutral", "stability": "stable", "description": "Neutral"}, "overall_assessment": "Normal", "recommendations": []}'
        analyzer.client.models.generate_content.return_value = mock_response

        result1 = analyzer.analyze("Test transcript for caching")

        # Second call with same transcript - should use cache
        result2 = analyzer.analyze("Test transcript for caching")

        assert result1 == result2
        # Should only call API once due to caching
        assert analyzer.client.models.generate_content.call_count == 1

    @patch('modules.psychological_analyzer.genai.Client')
    def test_cache_miss_different_params(self, mock_genai_client):
        """Test cache miss with different parameters"""
        analyzer = PsychologicalAnalyzer()

        mock_response = MagicMock()
        mock_response.text = '{"adhd_indicators": {"score": 5, "evidence": [], "confidence": "medium"}, "anxiety_patterns": {"score": 3, "themes": [], "confidence": "low"}, "cognitive_biases": {"score": 2, "identified_biases": [], "confidence": "low"}, "emotional_tone": {"primary_emotion": "neutral", "stability": "stable", "description": "Neutral"}, "overall_assessment": "Normal", "recommendations": []}'
        analyzer.client.models.generate_content.return_value = mock_response

        # Different include_details should create different cache keys
        result1 = analyzer.analyze("Test transcript", include_details=True)
        result2 = analyzer.analyze("Test transcript", include_details=False)

        # Should call API twice
        assert analyzer.client.models.generate_content.call_count == 2


class TestPsychologicalAnalyzerSummary:
    """Test summary generation"""

    @patch('modules.psychological_analyzer.genai.Client')
    def test_generate_summary_complete_analysis(self, mock_genai_client):
        """Test summary generation with complete analysis"""
        analyzer = PsychologicalAnalyzer()

        analysis = {
            "adhd_indicators": {"score": 7},
            "anxiety_patterns": {"score": 8},
            "cognitive_biases": {"score": 4, "identified_biases": ["catastrophizing", "all-or-nothing"]},
            "emotional_tone": {"primary_emotion": "anxious"},
            "overall_assessment": "High anxiety with ADHD patterns",
            "recommendations": ["Practice mindfulness", "Consider therapy"]
        }

        summary = analyzer.generate_summary(analysis)

        assert "ADHD Indicators: 7/10 (Elevated)" in summary
        assert "Anxiety Patterns: 8/10 (High)" in summary
        assert "Cognitive Biases: 4/10 (Low)" in summary
        assert "Primary Emotion: Anxious" in summary
        assert "catastrophizing, all-or-nothing" in summary
        assert "Practice mindfulness" in summary
        assert "Consider therapy" in summary

    @patch('modules.psychological_analyzer.genai.Client')
    def test_generate_summary_minimal_analysis(self, mock_genai_client):
        """Test summary generation with minimal analysis"""
        analyzer = PsychologicalAnalyzer()

        analysis = {
            "adhd_indicators": {"score": 1},
            "anxiety_patterns": {"score": 2},
            "cognitive_biases": {"score": 0},
            "emotional_tone": {"primary_emotion": "neutral"},
            "overall_assessment": "Normal conversation"
        }

        summary = analyzer.generate_summary(analysis)

        assert "ADHD Indicators: 1/10 (Minimal)" in summary
        assert "Anxiety Patterns: 2/10 (Minimal)" in summary
        assert "Cognitive Biases: 0/10 (Minimal)" in summary

    def test_score_interpretation(self):
        """Test score interpretation"""
        analyzer = PsychologicalAnalyzer()

        assert analyzer._score_interpretation(1) == "Minimal"
        assert analyzer._score_interpretation(3) == "Low"
        assert analyzer._score_interpretation(5) == "Moderate"
        assert analyzer._score_interpretation(7) == "Elevated"
        assert analyzer._score_interpretation(9) == "High"


class TestPsychologicalAnalyzerInternal:
    """Test internal methods"""

    @patch('modules.psychological_analyzer.genai.Client')
    def test_build_analysis_prompt(self, mock_genai_client):
        """Test prompt building"""
        analyzer = PsychologicalAnalyzer()

        prompt = analyzer._build_analysis_prompt("Test transcript", True)

        assert "Test transcript" in prompt
        assert "clinical psychologist assistant" in prompt
        assert "ADHD Indicators" in prompt
        assert "Anxiety Patterns" in prompt
        assert "provide specific evidence" in prompt

    @patch('modules.psychological_analyzer.genai.Client')
    def test_build_analysis_prompt_without_details(self, mock_genai_client):
        """Test prompt building without details"""
        analyzer = PsychologicalAnalyzer()

        prompt = analyzer._build_analysis_prompt("Test transcript", False)

        assert "without detailed evidence" in prompt

    @patch('modules.psychological_analyzer.genai.Client')
    def test_parse_analysis_response_valid_json(self, mock_genai_client):
        """Test parsing valid JSON response"""
        analyzer = PsychologicalAnalyzer()

        json_response = '{"adhd_indicators": {"score": 5}, "anxiety_patterns": {"score": 3}, "cognitive_biases": {"score": 2}, "emotional_tone": {"primary_emotion": "neutral"}}'

        result = analyzer._parse_analysis_response(json_response)

        assert result["adhd_indicators"]["score"] == 5
        assert result["anxiety_patterns"]["score"] == 3

    @patch('modules.psychological_analyzer.genai.Client')
    def test_parse_analysis_response_markdown_json(self, mock_genai_client):
        """Test parsing JSON wrapped in markdown"""
        analyzer = PsychologicalAnalyzer()

        markdown_response = '''```json
        {"adhd_indicators": {"score": 6}, "anxiety_patterns": {"score": 4}, "cognitive_biases": {"score": 3}, "emotional_tone": {"primary_emotion": "calm"}}
        ```'''

        result = analyzer._parse_analysis_response(markdown_response)

        assert result["adhd_indicators"]["score"] == 6

    @patch('modules.psychological_analyzer.genai.Client')
    def test_parse_analysis_response_invalid_json(self, mock_genai_client):
        """Test parsing invalid JSON response"""
        analyzer = PsychologicalAnalyzer()

        result = analyzer._parse_analysis_response("Invalid JSON")

        assert "JSON parse error" in result["error"]
        assert result["adhd_indicators"]["score"] == 0

    @patch('modules.psychological_analyzer.genai.Client')
    def test_get_cache_key(self, mock_genai_client):
        """Test cache key generation"""
        analyzer = PsychologicalAnalyzer()

        key1 = analyzer._get_cache_key("Test transcript", True)
        key2 = analyzer._get_cache_key("Test transcript", False)
        key3 = analyzer._get_cache_key("Different transcript", True)

        assert key1 != key2  # Different include_details
        assert key1 != key3  # Different transcript
        assert len(key1) == 32  # MD5 hash length