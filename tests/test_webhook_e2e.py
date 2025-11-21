#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Script for Webhook Functionality

Tests the complete processing pipeline including:
- Transcript cleaning
- Psychological analysis
- Memory embedding
- Storage operations

Simulates webhook calls without running the server.
"""

import asyncio
import json
import logging
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
import numpy as np

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.orchestrator import OMIGeminiOrchestrator
from modules.memory_embedder import MemoryEmbedder
from modules.memory_store import MemoryStore
from modules.transcript_processor import TranscriptProcessor
from modules.psychological_analyzer import PsychologicalAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockOMIClient:
    """Mock OMI client to avoid external API calls"""

    def __init__(self):
        self.memories_created = []
        self.notifications_sent = []

    def create_memories(self, text: str, memories: List[Dict], text_source: str = "other") -> Dict[str, Any]:
        """Mock memory creation"""
        memory_id = f"mock_memory_{len(self.memories_created) + 1}"
        self.memories_created.append({
            "id": memory_id,
            "content": text,
            "source": text_source
        })
        return {
            "success": True,
            "memories": [{"id": memory_id, "content": text}]
        }

    def send_notification(self, message: str, uid: str) -> bool:
        """Mock notification sending"""
        self.notifications_sent.append({
            "message": message,
            "uid": uid
        })
        return True

    def read_conversations(self, limit: int = 5) -> List[Dict]:
        """Mock conversation reading"""
        return [
            {
                "id": f"conv_{i}",
                "text": f"Mock conversation {i} text content for testing.",
                "created_at": "2024-01-01T00:00:00Z"
            } for i in range(limit)
        ]

    def close(self):
        """Mock close"""
        pass


class MockWorkspaceAutomation:
    """Mock workspace automation to avoid Google Workspace API calls"""

    def __init__(self):
        self.credentials = True  # Mock as available
        self.emails_created = []
        self.calendars_created = []
        self.presentations_created = []
        self.client = MagicMock()
        self.client.models.generate_content.return_value = MagicMock(text="Mocked slide content")
        self.gemini_model_name = "mock-model"

    def should_create_email(self, analysis: Dict, transcript: str) -> bool:
        """Mock email decision logic"""
        anxiety_score = analysis.get("anxiety_patterns", {}).get("score", 0)
        return anxiety_score >= 5  # Create email for high anxiety

    def create_email_draft(self, context: str) -> str:
        """Mock email creation"""
        draft_id = f"mock_draft_{len(self.emails_created) + 1}"
        self.emails_created.append({
            "id": draft_id,
            "context": context
        })
        return draft_id

    def create_calendar_event(self, summary: str, start_time: str, end_time: str, description: str) -> str:
        """Mock calendar event creation"""
        event_id = f"mock_event_{len(self.calendars_created) + 1}"
        self.calendars_created.append({
            "id": event_id,
            "summary": summary,
            "start_time": start_time,
            "end_time": end_time,
            "description": description
        })
        return event_id

    def create_presentation(self, title: str, slides_content: List[Dict]) -> str:
        """Mock presentation creation"""
        pres_id = f"mock_presentation_{len(self.presentations_created) + 1}"
        self.presentations_created.append({
            "id": pres_id,
            "title": title,
            "slides": slides_content
        })
        return pres_id


def create_mock_memory_data() -> Dict[str, Any]:
    """Create mock memory data for webhook testing"""
    return {
        "id": "test_memory_123",
        "created_at": "2024-01-15T10:30:00Z",
        "transcript_segments": [
            {"text": "Hey, I've been really worried about this upcoming presentation.", "start": 0.0, "end": 3.2},
            {"text": "I keep thinking about all the things that could go wrong.", "start": 3.5, "end": 6.8},
            {"text": "What if I forget my lines or the slides don't work properly?", "start": 7.1, "end": 10.5},
            {"text": "I should probably prepare more, but I just can't focus on one thing at a time.", "start": 11.0, "end": 15.3},
            {"text": "Maybe I should schedule a meeting to discuss this with my team.", "start": 15.8, "end": 19.2}
        ],
        "structured": {
            "overview": "User expressing anxiety about upcoming presentation and difficulty focusing",
            "duration": 19.2,
            "speakers": ["user"]
        }
    }

def create_mock_realtime_segments() -> List[Dict[str, Any]]:
    """Create mock realtime transcript segments"""
    return [
        {"text": "Hello, how are you doing today?", "timestamp": "2024-01-15T10:30:00Z"},
        {"text": "I'm feeling a bit anxious about the meeting tomorrow.", "timestamp": "2024-01-15T10:30:05Z"},
        {"text": "There are so many things I need to prepare.", "timestamp": "2024-01-15T10:30:10Z"}
    ]

@pytest.mark.asyncio
async def test_memory_webhook_pipeline():
    """Test the complete memory webhook processing pipeline"""
    logger.info("Testing memory webhook pipeline...")

    # Create mock components
    mock_omi_client = MockOMIClient()
    mock_workspace = MockWorkspaceAutomation()

    # Patch the orchestrator to use mocks
    with patch('modules.orchestrator.OMIClient', return_value=mock_omi_client), \
         patch('modules.orchestrator.WorkspaceAutomation', return_value=mock_workspace):

        # Create orchestrator
        orchestrator = OMIGeminiOrchestrator()

        # Test data
        memory_data = create_mock_memory_data()
        uid = "test_user_123"

        # Process memory webhook
        result = await orchestrator.process_memory_webhook(memory_data, uid)

        # Verify results
        assert result["success"] == True, f"Processing should succeed, got {result}"
        assert "transcript_extracted" in result["steps_completed"], "Transcript extraction should complete"
        assert "transcript_cleaned" in result["steps_completed"], "Transcript cleaning should complete"
        assert "psychological_analysis" in result["steps_completed"], "Psychological analysis should complete"

        # Verify analysis scores are present
        logger.info("OK Memory webhook pipeline test passed")
        return result

@pytest.mark.asyncio
async def test_realtime_webhook_pipeline():
    """Test the realtime webhook processing pipeline"""
    logger.info("Testing realtime webhook pipeline...")

    # Create mock components
    mock_omi_client = MockOMIClient()
    mock_workspace = MockWorkspaceAutomation()

    # Patch the orchestrator to use mocks
    with patch('modules.orchestrator.OMIClient', return_value=mock_omi_client), \
         patch('modules.orchestrator.WorkspaceAutomation', return_value=mock_workspace):

        # Create orchestrator
        orchestrator = OMIGeminiOrchestrator()

        # Test data
        segments = create_mock_realtime_segments()
        session_id = "test_session_456"
        uid = "test_user_123"

        # Process realtime webhook
        result = await orchestrator.process_realtime_transcript(segments, session_id, uid)

        # Verify results
        assert result["success"] == True, f"Realtime processing should succeed, got {result}"
        assert result["session_id"] == session_id, "Session ID should be preserved"
        assert result["segments_processed"] == len(segments), "All segments should be processed"

        logger.info("OK Realtime webhook pipeline test passed")
        return result

def test_memory_embedding_and_storage():
    """Test memory embedding and storage components"""
    logger.info("Testing memory embedding and storage...")

    # Create temporary database file
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        db_path = temp_db.name

    try:
        # Initialize components
        embedder = MemoryEmbedder(dimension=768)
        memory_store = MemoryStore(db_path, embedding_dimension=768)

        # Test data
        test_memories = [
            {
                "content": "I feel anxious about the upcoming presentation and can't focus on preparing.",
                "metadata": {"source": "test", "tags": ["anxiety", "focus"]}
            },
            {
                "content": "The meeting went well, but I keep thinking about what could have gone wrong.",
                "metadata": {"source": "test", "tags": ["reflection", "meeting"]}
            },
            {
                "content": "I need to organize my tasks better and stop jumping between projects.",
                "metadata": {"source": "test", "tags": ["organization", "tasks"]}
            }
        ]

        # Add memories to store
        added_ids = []
        for mem_data in test_memories:
            success = memory_store.add_memory(
                content=mem_data["content"],
                metadata=mem_data["metadata"]
            )
            assert success, f"Failed to add memory: {mem_data['content'][:50]}..."

            # Get the last added memory ID (simplified)
            stats = memory_store.get_stats()
            added_ids.append(f"mem_{stats['total_memories']}")

        # Verify storage
        assert memory_store.get_stats()["total_memories"] == len(test_memories), "All memories should be stored"

        # Test semantic search
        query = "feeling anxious about presentations"
        search_results = memory_store.search(query, top_k=2)

        assert len(search_results) > 0, "Search should return results"
        assert "similarity_score" in search_results[0], "Results should include similarity scores"

        # Test embedding similarity
        embeddings = []
        for mem in memory_store.get_all():
            if mem.get("content"):
                emb = embedder.embed_text(mem["content"])
                if emb is not None:
                    embeddings.append(emb)

        if len(embeddings) >= 2:
            similarity = embedder.cosine_similarity(embeddings[0], embeddings[1])
            assert 0 <= similarity <= 1, f"Similarity should be between 0 and 1, got {similarity}"

        logger.info("OK Memory embedding and storage test passed")
        return memory_store.get_stats()
    finally:
        # Clean up temporary database file
        import os
        try:
            os.unlink(db_path)
        except OSError:
            pass

def test_individual_components():
    """Test individual components with mock data"""
    logger.info("Testing individual components...")

    # Test Transcript Processor
    processor = TranscriptProcessor()

    raw_transcript = "um, so I was thinking about, you know, the meeting tomorrow and I'm kinda worried about it. Like, what if I forget what to say? And also, I need to finish that report but I keep getting distracted by emails."
    cleaned_result = processor.process_transcript(raw_transcript)

    assert cleaned_result["success"] == True, "Transcript cleaning should succeed"
    assert "cleaned_text" in cleaned_result, "Cleaned text should be present"
    assert len(cleaned_result["cleaned_text"]) > 0, "Cleaned text should not be empty"

    # Test Psychological Analyzer
    analyzer = PsychologicalAnalyzer()
    analysis = analyzer.analyze(cleaned_result["cleaned_text"])

    assert "adhd_indicators" in analysis, "ADHD analysis should be present"
    assert "anxiety_patterns" in analysis, "Anxiety analysis should be present"
    assert "cognitive_biases" in analysis, "Bias analysis should be present"
    assert "emotional_tone" in analysis, "Emotional tone should be present"

    # Verify scores are within range
    for component in ["adhd_indicators", "anxiety_patterns", "cognitive_biases"]:
        score = analysis[component].get("score", 0)
        assert 0 <= score <= 10, f"{component} score should be 0-10, got {score}"

    logger.info("OK Individual components test passed")
    return {
        "transcript_cleaned": cleaned_result["cleaned_text"],
        "analysis": analysis
    }

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling and edge cases"""
    logger.info("Testing error handling...")

    # Create orchestrator with mocks
    mock_omi_client = MockOMIClient()
    mock_workspace = MockWorkspaceAutomation()

    with patch('modules.orchestrator.OMIClient', return_value=mock_omi_client), \
         patch('modules.orchestrator.WorkspaceAutomation', return_value=mock_workspace):

        orchestrator = OMIGeminiOrchestrator()

        # Test empty memory data
        result = await orchestrator.process_memory_webhook({}, "test_user")
        assert result["success"] == False, "Empty memory should fail"
        assert "No transcript available" in str(result["errors"]), "Should report no transcript"

        # Test invalid memory data type
        try:
            result = await orchestrator.process_memory_webhook("invalid", "test_user")
            assert result["success"] == False, "Invalid data type should fail"
        except ValueError as e:
            # Expected ValueError for invalid data type
            assert "must be a dictionary" in str(e), f"Expected ValueError message, got: {e}"

        # Test empty realtime segments
        result = await orchestrator.process_realtime_transcript([], "session_1", "user_1")
        assert result["success"] == False, "Empty segments should fail"

        logger.info("OK Error handling test passed")

async def run_all_tests():
    """Run all test suites"""
    logger.info("Starting comprehensive webhook E2E tests...")

    test_results = {}

    try:
        # Test individual components
        test_results["individual_components"] = test_individual_components()

        # Test memory embedding and storage
        test_results["memory_storage"] = test_memory_embedding_and_storage()

        # Test webhook pipelines
        test_results["memory_webhook"] = await test_memory_webhook_pipeline()
        test_results["realtime_webhook"] = await test_realtime_webhook_pipeline()

        # Test error handling
        await test_error_handling()

        logger.info("🎉 All tests passed successfully!")

        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        memory_result = test_results["memory_webhook"]
        print(f"Memory Webhook: {len(memory_result['steps_completed'])} steps completed")
        print(f"  - Transcript cleaned with model: {memory_result.get('model_used', 'unknown')}")
        print(f"  - Analysis scores: ADHD={memory_result['analysis']['adhd_score']}, Anxiety={memory_result['analysis']['anxiety_score']}, Biases={memory_result['analysis']['bias_score']}")
        print(f"  - Processing time: {memory_result.get('processing_time_seconds', 0):.2f}s")

        storage_stats = test_results["memory_storage"]
        print(f"Memory Storage: {storage_stats['total_memories']} memories stored ({storage_stats['storage_size_mb']:.2f} MB)")

        print("="*60)

        return True

    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)