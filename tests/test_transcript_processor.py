"""
Unit tests for transcript_processor.py module
Tests transcript cleaning and processing with Gemini AI
"""
import pytest
from unittest.mock import patch, MagicMock

from modules.transcript_processor import TranscriptProcessor
from config.settings import GeminiConfig


class TestTranscriptProcessorInit:
    """Test TranscriptProcessor initialization"""

    @patch('modules.transcript_processor.genai.Client')
    def test_init_success(self, mock_genai_client):
        """Test successful initialization"""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client

        processor = TranscriptProcessor()

        assert processor.client == mock_client
        assert processor.primary_model == GeminiConfig.PRIMARY_MODEL
        assert processor.fallback_model == GeminiConfig.FALLBACK_MODEL
        assert processor.lite_model == GeminiConfig.LITE_MODEL

    @patch('modules.transcript_processor.genai.Client')
    @patch('modules.transcript_processor.GeminiConfig.validate')
    def test_init_config_validation(self, mock_validate, mock_genai_client):
        """Test that config validation is called during init"""
        TranscriptProcessor()
        mock_validate.assert_called_once()


class TestTranscriptProcessorProcess:
    """Test transcript processing functionality"""

    @patch('modules.transcript_processor.genai.Client')
    def test_process_transcript_success_primary_model(self, mock_genai_client):
        """Test successful processing with primary model"""
        processor = TranscriptProcessor()

        # Mock successful response
        mock_response = MagicMock()
        mock_response.text = "Cleaned transcript text"
        processor.client.models.generate_content.return_value = mock_response

        result = processor.process_transcript("raw transcript text")

        assert result["success"] == True
        assert result["cleaned_text"] == "Cleaned transcript text"
        assert result["model_used"] == GeminiConfig.PRIMARY_MODEL

    @patch('modules.transcript_processor.genai.Client')
    def test_process_transcript_fallback_to_flash(self, mock_genai_client):
        """Test fallback to Flash model when primary fails"""
        processor = TranscriptProcessor()

        # Mock primary model failure, fallback success
        call_count = 0
        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count == 1:
                # Primary model fails
                mock_response.text = ""
            else:
                # Fallback succeeds
                mock_response.text = "Fallback cleaned text"
            return mock_response

        processor.client.models.generate_content.side_effect = mock_generate_content

        result = processor.process_transcript("raw transcript")

        assert result["success"] == True
        assert result["cleaned_text"] == "Fallback cleaned text"
        assert result["model_used"] == GeminiConfig.FALLBACK_MODEL
        assert call_count == 2

    @patch('modules.transcript_processor.genai.Client')
    def test_process_transcript_all_models_fail(self, mock_genai_client):
        """Test when all models fail"""
        processor = TranscriptProcessor()

        # Mock all models failing
        mock_response = MagicMock()
        mock_response.text = ""
        processor.client.models.generate_content.return_value = mock_response

        result = processor.process_transcript("raw transcript")

        assert result["success"] == False
        assert result["cleaned_text"] == "raw transcript"  # Returns original
        assert result["error"] == "All models failed"
        assert result["model_used"] is None

    def test_process_transcript_empty_input(self):
        """Test processing empty transcript"""
        processor = TranscriptProcessor()

        result = processor.process_transcript("")

        assert result["success"] == False
        assert result["cleaned_text"] == ""
        assert result["error"] == "Empty transcript"

    def test_process_transcript_whitespace_only(self):
        """Test processing whitespace-only transcript"""
        processor = TranscriptProcessor()

        result = processor.process_transcript("   \n\t   ")

        assert result["success"] == False
        assert result["error"] == "Empty transcript"

    def test_process_transcript_too_long(self):
        """Test processing overly long transcript"""
        processor = TranscriptProcessor()

        long_transcript = "a" * 100001  # Over 100KB limit

        result = processor.process_transcript(long_transcript)

        assert result["success"] == False
        assert result["error"] == "Transcript too long"
        assert len(result["cleaned_text"]) <= 50050  # Truncated + "..."

    def test_process_transcript_invalid_input_type(self):
        """Test processing with invalid input type"""
        processor = TranscriptProcessor()

        with pytest.raises(ValueError, match="transcript_raw must be a string"):
            processor.process_transcript(123)

    def test_process_transcript_with_context(self):
        """Test processing with context information"""
        processor = TranscriptProcessor()

        # Mock successful response
        with patch.object(processor, '_call_gemini_api') as mock_call:
            mock_response = MagicMock()
            mock_response.text = "Context-aware cleaned text"
            mock_call.return_value = mock_response

            result = processor.process_transcript("raw text", context="meeting context")

            assert result["success"] == True
            assert result["cleaned_text"] == "Context-aware cleaned text"

    def test_process_transcript_invalid_context_type(self):
        """Test processing with invalid context type"""
        processor = TranscriptProcessor()

        with pytest.raises(ValueError, match="context must be a string or None"):
            processor.process_transcript("raw text", context=123)


class TestTranscriptProcessorBatch:
    """Test batch processing functionality"""

    @patch('modules.transcript_processor.genai.Client')
    def test_batch_process_success(self, mock_genai_client):
        """Test successful batch processing"""
        processor = TranscriptProcessor()

        # Mock successful responses
        mock_response = MagicMock()
        mock_response.text = "Cleaned text"
        processor.client.models.generate_content.return_value = mock_response

        transcripts = ["transcript 1", "transcript 2", "transcript 3"]

        results = processor.batch_process(transcripts)

        assert len(results) == 3
        for result in results:
            assert result["success"] == True
            assert result["cleaned_text"] == "Cleaned text"

    @patch('modules.transcript_processor.genai.Client')
    def test_batch_process_with_context(self, mock_genai_client):
        """Test batch processing with shared context"""
        processor = TranscriptProcessor()

        mock_response = MagicMock()
        mock_response.text = "Context-aware cleaned text"
        processor.client.models.generate_content.return_value = mock_response

        transcripts = ["transcript 1", "transcript 2"]

        results = processor.batch_process(transcripts, context="shared context")

        assert len(results) == 2
        for result in results:
            assert result["success"] == True


class TestTranscriptProcessorInternal:
    """Test internal methods of TranscriptProcessor"""

    @patch('modules.transcript_processor.genai.Client')
    def test_build_cleaning_prompt_basic(self, mock_genai_client):
        """Test basic prompt building"""
        processor = TranscriptProcessor()

        prompt = processor._build_cleaning_prompt("test transcript")

        assert "test transcript" in prompt
        assert "professional transcript editor" in prompt
        assert "Cleaned Transcript:" in prompt

    @patch('modules.transcript_processor.genai.Client')
    def test_build_cleaning_prompt_with_context(self, mock_genai_client):
        """Test prompt building with context"""
        processor = TranscriptProcessor()

        prompt = processor._build_cleaning_prompt("test transcript", "meeting context")

        assert "test transcript" in prompt
        assert "meeting context" in prompt
        assert "Context:" in prompt

    @patch('modules.transcript_processor.genai.Client')
    def test_clean_with_gemini_success(self, mock_genai_client):
        """Test successful cleaning with specific model"""
        processor = TranscriptProcessor()

        mock_response = MagicMock()
        mock_response.text = "Cleaned content"
        processor.client.models.generate_content.return_value = mock_response

        result = processor._clean_with_gemini("raw text", "test-model")

        assert result["success"] == True
        assert result["cleaned_text"] == "Cleaned content"
        assert result["model_used"] == "test-model"

    @patch('modules.transcript_processor.genai.Client')
    def test_clean_with_gemini_empty_response(self, mock_genai_client):
        """Test cleaning with empty API response"""
        processor = TranscriptProcessor()

        mock_response = MagicMock()
        mock_response.text = ""
        processor.client.models.generate_content.return_value = mock_response

        result = processor._clean_with_gemini("raw text", "test-model")

        assert result["success"] == False
        assert result["cleaned_text"] == ""
        assert result["error"] == "Empty response"

    @patch('modules.transcript_processor.genai.Client')
    def test_clean_with_gemini_api_error(self, mock_genai_client):
        """Test cleaning with API error"""
        processor = TranscriptProcessor()

        processor.client.models.generate_content.side_effect = Exception("API Error")

        result = processor._clean_with_gemini("raw text", "test-model")

        assert result["success"] == False
        assert result["cleaned_text"] == ""
        assert "API Error" in result["error"]

    @patch('modules.transcript_processor.genai.Client')
    def test_call_gemini_api_with_decorator(self, mock_genai_client):
        """Test that API calls use the rate limit decorator"""
        processor = TranscriptProcessor()

        mock_response = MagicMock()
        mock_response.text = "response"
        processor.client.models.generate_content.return_value = mock_response

        # The _call_gemini_api method should be decorated with rate limiting
        result = processor._call_gemini_api("model", "prompt")

        assert result == mock_response
        processor.client.models.generate_content.assert_called_once()


class TestTranscriptProcessorErrorHandling:
    """Test error handling in transcript processor"""

    @patch('modules.transcript_processor.genai.Client')
    def test_init_gemini_client_failure(self, mock_genai_client):
        """Test initialization failure"""
        mock_genai_client.side_effect = Exception("Client init failed")

        with pytest.raises(Exception):
            TranscriptProcessor()

    @patch('modules.transcript_processor.genai.Client')
    def test_process_transcript_none_response(self, mock_genai_client):
        """Test handling None response from API"""
        processor = TranscriptProcessor()

        processor.client.models.generate_content.return_value = None

        result = processor.process_transcript("test")

        assert result["success"] == False
        assert result["error"] == "All models failed"

    @patch('modules.transcript_processor.genai.Client')
    def test_process_transcript_exception_handling(self, mock_genai_client):
        """Test general exception handling"""
        processor = TranscriptProcessor()

        # Mock the _clean_with_gemini to raise exception
        with patch.object(processor, '_clean_with_gemini', side_effect=Exception("Unexpected error")):
            result = processor.process_transcript("test")

            assert result["success"] == False
            assert result["cleaned_text"] == "test"  # Returns original
            assert "Unexpected error" in result["error"]


class TestTranscriptProcessorEdgeCases:
    """Test edge cases in transcript processing"""

    @patch('modules.transcript_processor.genai.Client')
    def test_process_transcript_unicode_content(self, mock_genai_client):
        """Test processing transcript with unicode characters"""
        processor = TranscriptProcessor()

        unicode_text = "Hello 世界 🌍 café résumé naïve"
        mock_response = MagicMock()
        mock_response.text = f"Cleaned: {unicode_text}"
        processor.client.models.generate_content.return_value = mock_response

        result = processor.process_transcript(unicode_text)

        assert result["success"] == True
        assert unicode_text in result["cleaned_text"]

    @patch('modules.transcript_processor.genai.Client')
    def test_process_transcript_special_characters(self, mock_genai_client):
        """Test processing transcript with special characters"""
        processor = TranscriptProcessor()

        special_text = "Test: @#$%^&*()[]{}|\\:;\"'<>?,./"
        mock_response = MagicMock()
        mock_response.text = f"Processed: {special_text}"
        processor.client.models.generate_content.return_value = mock_response

        result = processor.process_transcript(special_text)

        assert result["success"] == True

    @patch('modules.transcript_processor.genai.Client')
    def test_batch_process_empty_list(self, mock_genai_client):
        """Test batch processing empty list"""
        processor = TranscriptProcessor()

        results = processor.batch_process([])

        assert results == []

    @patch('modules.transcript_processor.genai.Client')
    def test_batch_process_mixed_success_failure(self, mock_genai_client):
        """Test batch processing with mixed success/failure"""
        processor = TranscriptProcessor()

        # Mock alternating success/failure
        call_count = 0
        def mock_generate_content(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            # 1: Trans 1 Primary (Success)
            # 2: Trans 2 Primary (Fail)
            # 3: Trans 2 Fallback (Fail)
            # 4: Trans 2 Lite (Fail) -> All failed
            # 5: Trans 3 Primary (Success)
            
            # Note: logic depends on how many fallbacks happen.
            # If Primary fails -> Fallback. If Fallback fails -> Lite. If Lite fails -> Fail.
            # So for Trans 2 to fail, we need 3 failures.
            
            if call_count == 1 or call_count == 5:
                mock_response.text = f"Success {call_count}"
            else:
                mock_response.text = ""
            return mock_response

        processor.client.models.generate_content.side_effect = mock_generate_content

        transcripts = ["transcript 1", "transcript 2", "transcript 3"]

        results = processor.batch_process(transcripts)

        assert len(results) == 3
        assert results[0]["success"] == True
        assert results[1]["success"] == False
        assert results[2]["success"] == True