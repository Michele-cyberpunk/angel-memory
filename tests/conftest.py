"""
Pytest configuration and shared fixtures for omi-gemini-integration tests
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, MagicMock
from pathlib import Path

# Add modules to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def temp_db_path():
    """Create a temporary database file path"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        temp_path = temp_file.name
    yield temp_path
    # Cleanup
    try:
        os.unlink(temp_path)
    except OSError:
        pass

@pytest.fixture
def mock_gemini_client():
    """Mock Gemini API client"""
    mock_client = MagicMock()
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Mock response text"

    mock_model.generate_content.return_value = mock_response
    mock_client.models.generate_content.return_value = mock_response
    mock_client.models = mock_model

    return mock_client

@pytest.fixture
def mock_omi_client():
    """Mock OMI API client"""
    mock_client = MagicMock()
    mock_client.create_memories.return_value = {
        "success": True,
        "memories": [{"id": "mock_memory_1", "content": "test"}]
    }
    mock_client.send_notification.return_value = True
    mock_client.read_conversations.return_value = [
        {"id": "conv_1", "text": "Mock conversation", "created_at": "2024-01-01T00:00:00Z"}
    ]
    mock_client.close.return_value = None
    return mock_client

@pytest.fixture
def mock_workspace_automation():
    """Mock WorkspaceAutomation instance"""
    mock_ws = MagicMock()
    mock_ws.should_create_email.return_value = True
    mock_ws.create_email_draft.return_value = "mock_draft_1"
    mock_ws.create_calendar_event.return_value = "mock_event_1"
    mock_ws.create_presentation.return_value = "mock_presentation_1"
    mock_ws.authenticate.return_value = True
    return mock_ws

@pytest.fixture
def sample_memory_data():
    """Sample memory data for testing"""
    return {
        "id": "test_memory_123",
        "created_at": "2024-01-15T10:30:00Z",
        "transcript_segments": [
            {"text": "Hey, I've been really worried about this upcoming presentation.", "start": 0.0, "end": 3.2},
            {"text": "I keep thinking about all the things that could go wrong.", "start": 3.5, "end": 6.8},
            {"text": "What if I forget my lines or the slides don't work properly?", "start": 7.1, "end": 10.5}
        ],
        "structured": {
            "overview": "User expressing anxiety about upcoming presentation",
            "duration": 10.5,
            "speakers": ["user"]
        }
    }

@pytest.fixture
def sample_transcript():
    """Sample transcript text for testing"""
    return "um, so I was thinking about, you know, the meeting tomorrow and I'm kinda worried about it. Like, what if I forget what to say? And also, I need to finish that report but I keep getting distracted by emails."

@pytest.fixture
def sample_analysis_result():
    """Sample psychological analysis result"""
    return {
        "adhd_indicators": {"score": 7, "details": ["distractibility", "task switching"]},
        "anxiety_patterns": {"score": 8, "details": ["future worry", "performance anxiety"]},
        "cognitive_biases": {"score": 3, "details": ["catastrophizing"]},
        "emotional_tone": "anxious",
        "overall_assessment": "High anxiety and ADHD indicators present"
    }

@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter that always allows requests"""
    mock_limiter = MagicMock()
    mock_limiter.acquire.return_value = True
    mock_limiter.wait_for_tokens.return_value = True
    return mock_limiter

@pytest.fixture
def mock_http_response():
    """Mock HTTP response"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_response.text = '{"success": true}'
    return mock_response