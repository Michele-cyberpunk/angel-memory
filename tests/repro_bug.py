import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from modules.orchestrator import OMIGeminiOrchestrator
import asyncio

@pytest.mark.asyncio
async def test_manual_conversation_analysis_type_error():
    """
    Test that manual_conversation_analysis handles the case where
    mcp_client.call_tool returns a dictionary instead of a list.
    """
    orchestrator = OMIGeminiOrchestrator()

    # Mock MCP Integration
    orchestrator.mcp_client = MagicMock()
    orchestrator.mcp_client.call_tool = AsyncMock()

    # Simulate return value that is NOT a list (e.g. a dict)
    # The bug suspected is in:
    # conversations = conversations_data if isinstance(conversations_data, list) else []
    # This will silently fail if it returns a dict, returning []

    # Let's assume call_tool returns a dict that HAS a list inside it
    # which is a common API pattern, but the code expects a direct list.
    # If call_tool returns {"conversations": [...]}, the code will set conversations = []

    mock_conversations_data = {
        "conversations": [
            {"id": "1", "text": "test transcript"}
        ]
    }

    orchestrator.mcp_client.call_tool.return_value = mock_conversations_data

    # Mock transcript processor and psychological analyzer to avoid side effects
    orchestrator.transcript_processor.process_transcript = MagicMock(return_value={
        "success": True,
        "cleaned_text": "clean text",
        "model_used": "test-model"
    })
    orchestrator.psychological_analyzer.analyze = MagicMock(return_value={
        "adhd_indicators": {"score": 1},
        "anxiety_patterns": {"score": 1},
        "emotional_tone": {"primary_emotion": "neutral"}
    })

    results = await orchestrator.manual_conversation_analysis(limit=5)

    # If the bug is fixed, results will NOT be empty because the dict was accepted
    # and parsed correctly
    assert len(results) == 1
    assert results[0]["conversation_id"] == "1"

    # Now let's verify that if it WAS a list, it works
    orchestrator.mcp_client.call_tool.return_value = [
        {"id": "1", "text": "test transcript"}
    ]

    results = await orchestrator.manual_conversation_analysis(limit=5)
    assert len(results) == 1
