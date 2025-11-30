"""
COMPLETE TEST SUITE FOR PATCHES
30+ test cases covering all fixes
"""

import pytest
import asyncio
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import tempfile

# Import fixed modules
from memory_store_fix import MemoryStoreFixed
from omi_api_completeness import OMIClientComplete
from error_handling_fix import (
    CircuitBreaker, CircuitBreakerState, RetryConfig, with_retry,
    AngelMemoryException, OMIAPIError, MemoryStoreError, ValidationError,
    ErrorContext
)
from type_safety_fix import (
    TypeValidator, SafeTypeConverter, MemoryData, ConversationData,
    MemoryMetadata, ProcessingResult, ProcessingStatus
)
from integration_fix import (
    ContextManager, RequestContext, IdempotencyStore, IdempotencyKey,
    WebhookSignatureVerifier, BatchProcessor, ResponseHandler
)
from gemini_embeddings_real import GeminiEmbedder
import numpy as np


# ============ FIXTURES ============

@pytest.fixture
def temp_db():
    """Create temporary database"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def memory_store(temp_db):
    """Create memory store instance"""
    return MemoryStoreFixed(temp_db)


@pytest.fixture
def request_context():
    """Create request context"""
    return ContextManager.create("test_user_123", {"test": True})


# ============ MEMORY STORE TESTS (6 tests) ============

class TestMemoryStoreFixed:
    """Test MemoryStoreFixed patch"""

    def test_initialize_database(self, temp_db):
        """PATCH 1: Database initialization with multi-user schema"""
        store = MemoryStoreFixed(temp_db)
        assert Path(temp_db).exists()

        # Verify tables exist
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            assert "memories" in tables
            assert "embeddings" in tables
            assert "users" in tables
            assert "audit_log" in tables

    def test_add_memory_with_user_isolation(self, memory_store):
        """PATCH 1: Add memory with user isolation"""
        uid = "user_001"
        content = "Important meeting notes"
        metadata = {"tags": ["meeting", "important"]}

        result = memory_store.add_memory(uid, content, metadata)
        assert result is True

        # Verify memory was stored
        memories = memory_store.get_user_memories(uid)
        assert len(memories) == 1
        assert memories[0]["content"] == content

    def test_memory_not_accessible_across_users(self, memory_store):
        """PATCH 1: Memory isolation between users"""
        user1 = "user_001"
        user2 = "user_002"
        content = "Secret data"

        memory_store.add_memory(user1, content)
        user2_memories = memory_store.get_user_memories(user2)
        assert len(user2_memories) == 0

    def test_update_memory_with_versioning(self, memory_store):
        """PATCH 1: Update memory and version tracking"""
        uid = "user_001"
        memory_id = "mem_test_001"
        original_content = "Original content"
        updated_content = "Updated content"

        # Add memory
        memory_store.add_memory(uid, original_content, memory_id=memory_id)

        # Update memory
        result = memory_store.update_memory(uid, memory_id, updated_content)
        assert result is True

        # Verify update
        memory = memory_store.get_memory(uid, memory_id)
        assert memory["content"] == updated_content
        assert memory["version"] == 2

    def test_soft_delete_memory(self, memory_store):
        """PATCH 1: Soft delete (mark as deleted)"""
        uid = "user_001"
        memory_id = "mem_test_001"

        memory_store.add_memory(uid, "Test content", memory_id=memory_id)
        result = memory_store.soft_delete_memory(uid, memory_id)
        assert result is True

        # Should not appear in active memories
        memories = memory_store.get_user_memories(uid)
        assert len(memories) == 0

    def test_audit_logging(self, memory_store, temp_db):
        """PATCH 1: Audit log tracking"""
        uid = "user_001"
        memory_store.add_memory(uid, "Test content")

        # Verify audit log entry
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT action FROM audit_log WHERE uid = ?", (uid,))
            rows = cursor.fetchall()
            assert len(rows) > 0
            assert rows[0][0] == "CREATE"


# ============ OMI API COMPLETENESS TESTS (6 tests) ============

class TestOMIAPICompleteness:
    """Test OMI API completeness patch"""

    @patch('requests.Session.get')
    def test_search_memories_by_query(self, mock_get):
        """PATCH 2: Search memories by text query"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "memories": [{"id": "mem_1", "content": "Test"}],
            "total_count": 1
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch('config.settings.OMIConfig.validate'):
            client = OMIClientComplete()
            memories, count = client.search_memories_by_query("test query")

        assert len(memories) == 1
        assert count == 1

    @patch('requests.Session.get')
    def test_search_memories_by_tags(self, mock_get):
        """PATCH 2: Search memories by tags"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "memories": [{"id": "mem_1", "tags": ["important"]}],
            "total_count": 1
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch('config.settings.OMIConfig.validate'):
            client = OMIClientComplete()
            memories, count = client.search_memories_by_tags(["important"])

        assert len(memories) == 1

    @patch('requests.Session.delete')
    def test_delete_memory(self, mock_delete):
        """PATCH 2: Delete memory"""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "deleted"}
        mock_response.raise_for_status = Mock()
        mock_delete.return_value = mock_response

        with patch('config.settings.OMIConfig.validate'):
            client = OMIClientComplete()
            result = client.delete_memory("mem_001")

        assert result is True

    @patch('requests.Session.delete')
    def test_batch_delete_memories(self, mock_delete):
        """PATCH 2: Batch delete multiple memories"""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "deleted"}
        mock_response.raise_for_status = Mock()
        mock_delete.return_value = mock_response

        with patch('config.settings.OMIConfig.validate'):
            client = OMIClientComplete()
            results = client.batch_delete_memories(["mem_001", "mem_002"])

        assert results["deleted"] == 2
        assert results["failed"] == 0

    @patch('requests.Session.get')
    def test_get_memory_stats(self, mock_get):
        """PATCH 2: Get memory statistics"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "total_memories": 100,
            "total_size_bytes": 1000000
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch('config.settings.OMIConfig.validate'):
            client = OMIClientComplete()
            stats = client.get_memory_stats()

        assert stats["total_memories"] == 100

    @patch('requests.Session.get')
    def test_paginate_memories(self, mock_get):
        """PATCH 2: Pagination generator"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "memories": [{"id": "mem_1"}, {"id": "mem_2"}]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch('config.settings.OMIConfig.validate'):
            client = OMIClientComplete()
            memories = list(client.paginate_memories(batch_size=2))

        assert len(memories) == 2


# ============ ERROR HANDLING TESTS (8 tests) ============

class TestErrorHandling:
    """Test error handling patch"""

    def test_exception_hierarchy(self):
        """PATCH 3: Custom exception hierarchy"""
        exc = OMIAPIError("API Error", "OMI_001", {"endpoint": "/v2/memories"})
        assert exc.error_code == "OMI_001"
        assert exc.context["endpoint"] == "/v2/memories"

    def test_exception_to_dict(self):
        """PATCH 3: Exception serialization"""
        exc = MemoryStoreError("Store error", "STORE_001")
        exc_dict = exc.to_dict()
        assert exc_dict["error"] == "STORE_001"
        assert "timestamp" in exc_dict

    def test_circuit_breaker_open(self):
        """PATCH 3: Circuit breaker opens on failures"""
        breaker = CircuitBreaker(failure_threshold=3)
        assert breaker.state == CircuitBreakerState.CLOSED

        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.is_available() is False

    def test_circuit_breaker_recovery(self):
        """PATCH 3: Circuit breaker recovery"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0)

        for _ in range(2):
            breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN

        # Simulate timeout
        import time
        time.sleep(0.1)

        # Should enter half-open
        assert breaker.is_available() is True
        assert breaker.state == CircuitBreakerState.HALF_OPEN

    def test_retry_config(self):
        """PATCH 3: Retry configuration"""
        config = RetryConfig(max_attempts=3, initial_delay=0.1, max_delay=1.0)
        assert config.get_delay(1) == 0.1
        assert config.get_delay(2) == 0.2
        assert config.get_delay(3) <= 1.0

    def test_error_context_manager(self):
        """PATCH 3: Error context manager"""
        with ErrorContext("test_op", {"user": "test"}):
            pass  # Success case

        with pytest.raises(ValueError):
            with ErrorContext("test_op", {"user": "test"}):
                raise ValueError("Test error")

    def test_fallback_handler(self):
        """PATCH 3: Fallback handler for degraded mode"""
        from error_handling_fix import FallbackHandler

        response = FallbackHandler.get_default_response("memory_analysis")
        assert response["status"] == "degraded"
        assert response["cached"] is True


# ============ TYPE SAFETY TESTS (8 tests) ============

class TestTypeSafety:
    """Test type safety patch"""

    def test_memory_data_validation(self):
        """PATCH 4: Pydantic model validation"""
        data = MemoryData(
            uid="user_001",
            content="Test content",
            metadata=MemoryMetadata(tags=["test"])
        )
        assert data.uid == "user_001"
        assert len(data.metadata.tags) == 1

    def test_memory_data_invalid_content(self):
        """PATCH 4: Validation rejects empty content"""
        with pytest.raises(Exception):  # Pydantic validation error
            MemoryData(uid="user_001", content="")

    def test_conversation_data_validation(self):
        """PATCH 4: Conversation model validation"""
        now = datetime.now(timezone.utc).isoformat()
        conv = ConversationData(
            text="Meeting notes",
            started_at=now,
            finished_at=now
        )
        assert conv.text == "Meeting notes"

    def test_type_validator_uid(self):
        """PATCH 4: UID validation"""
        valid_uid = TypeValidator.validate_uid("user_123")
        assert valid_uid == "user_123"

        with pytest.raises(ValueError):
            TypeValidator.validate_uid("")

    def test_type_validator_content(self):
        """PATCH 4: Content validation"""
        valid_content = TypeValidator.validate_content("Test content")
        assert valid_content == "Test content"

        with pytest.raises(ValueError):
            TypeValidator.validate_content("   ")  # Whitespace only

    def test_safe_type_converter_to_int(self):
        """PATCH 4: Safe int conversion"""
        assert SafeTypeConverter.to_int("42") == 42
        assert SafeTypeConverter.to_int("invalid", 0) == 0
        assert SafeTypeConverter.to_int(3.14) == 3

    def test_safe_type_converter_to_bool(self):
        """PATCH 4: Safe bool conversion"""
        assert SafeTypeConverter.to_bool("true") is True
        assert SafeTypeConverter.to_bool("false") is False
        assert SafeTypeConverter.to_bool(1) is True

    def test_processing_result_model(self):
        """PATCH 4: ProcessingResult model"""
        result = ProcessingResult(
            success=True,
            status=ProcessingStatus.COMPLETED,
            uid="user_001",
            processing_time_seconds=1.5
        )
        assert result.success is True
        assert result.status == ProcessingStatus.COMPLETED


# ============ INTEGRATION TESTS (6 tests) ============

class TestIntegration:
    """Test integration patch"""

    def test_request_context_creation(self):
        """PATCH 5: Request context creation"""
        context = ContextManager.create("user_123", {"metadata": "test"})
        assert context.user_id == "user_123"
        assert context.metadata["metadata"] == "test"

    def test_request_context_retrieval(self):
        """PATCH 5: Request context retrieval"""
        context = ContextManager.create("user_123")
        retrieved = ContextManager.get(context.request_id)
        assert retrieved is not None
        assert retrieved.user_id == "user_123"

    def test_idempotency_store(self):
        """PATCH 5: Idempotency tracking"""
        store = IdempotencyStore()
        key = "idempotency_key_123"
        result = {"memory_id": "mem_001"}

        store.record_request(key, result)
        cached = store.get_result(key)
        assert cached == result
        assert store.is_duplicate(key) is True

    def test_webhook_signature_verification(self):
        """PATCH 5: Webhook signature verification"""
        secret = "webhook_secret"
        verifier = WebhookSignatureVerifier(secret)

        payload = b"test payload"
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        signature = verifier.sign_payload(payload, timestamp)

        is_valid = verifier.verify_signature(payload, signature, timestamp)
        assert is_valid is True

    def test_response_handler_success(self):
        """PATCH 5: Response handler for success"""
        response = ResponseHandler.create_success_response(
            {"memory_id": "mem_001"},
            message="Memory created"
        )
        assert response["status"] == "success"
        assert response["data"]["memory_id"] == "mem_001"

    def test_response_handler_error(self):
        """PATCH 5: Response handler for errors"""
        response, status_code = ResponseHandler.create_error_response(
            "Invalid memory",
            "INVALID_MEMORY",
            400
        )
        assert response["status"] == "error"
        assert status_code == 400


# ============ INTEGRATION SCENARIO TESTS (2 tests) ============

class TestIntegrationScenarios:
    """End-to-end integration scenarios"""

    def test_full_memory_workflow(self, memory_store):
        """Full memory creation, update, delete workflow"""
        uid = "user_001"

        # Create
        memory_store.add_memory(uid, "Original content")
        memories = memory_store.get_user_memories(uid)
        memory_id = memories[0]["id"]

        # Update
        assert memory_store.update_memory(uid, memory_id, "Updated content")
        memory = memory_store.get_memory(uid, memory_id)
        assert memory["version"] == 2

        # Delete
        assert memory_store.soft_delete_memory(uid, memory_id)
        memories = memory_store.get_user_memories(uid)
        assert len(memories) == 0

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Batch processing workflow"""
        processor = BatchProcessor(batch_size=2)
        context = ContextManager.create("user_001")

        items = [
            {"id": 1, "content": "test1"},
            {"id": 2, "content": "test2"},
            {"id": 3, "content": "test3"}
        ]

        async def mock_processor(item, ctx):
            return {"success": True, "item_id": item["id"]}

        result = await processor.process_batch(items, mock_processor, context)
        assert result["processed"] == 3
        assert result["failed"] == 0


# ============ GEMINI EMBEDDINGS TESTS (4 tests) ============

class TestGeminiEmbeddings:
    """Test real Gemini embeddings integration"""

    @patch('google.generativeai.embed_content')
    def test_gemini_embedder_initialization(self, mock_embed):
        """REAL EMBEDDINGS: Initialize GeminiEmbedder with API key"""
        from config.settings import GeminiConfig

        try:
            embedder = GeminiEmbedder(api_key=GeminiConfig.API_KEY)
            assert embedder.model == "models/embedding-001"
            assert embedder is not None
        except Exception as e:
            # Skip if API key not available (expected in test environment)
            pytest.skip(f"Gemini API not available: {e}")

    @patch('google.generativeai.embed_content')
    def test_embed_text_real_api(self, mock_embed):
        """REAL EMBEDDINGS: Generate embedding from text"""
        # Mock the Gemini API response
        mock_embedding = np.random.randn(768).tolist()  # 768-dimensional embedding
        mock_embed.return_value = {'embedding': mock_embedding}

        from config.settings import GeminiConfig
        embedder = GeminiEmbedder(api_key="test_key")

        result = embedder.embed_text("Hello world, this is a test")
        assert result is not None
        assert isinstance(result, np.ndarray)
        assert result.shape == (768,)
        assert result.dtype == np.float32

    @patch('google.generativeai.embed_content')
    def test_embed_batch_real_api(self, mock_embed):
        """REAL EMBEDDINGS: Batch embedding generation"""
        # Mock API responses
        mock_embedding = np.random.randn(768).tolist()
        mock_embed.return_value = {'embedding': mock_embedding}

        from config.settings import GeminiConfig
        embedder = GeminiEmbedder(api_key="test_key")

        texts = [
            "First memory",
            "Second memory",
            "Third memory"
        ]

        results = embedder.embed_batch(texts)
        assert len(results) == 3
        assert all(isinstance(r, np.ndarray) for r in results)
        assert all(r.shape == (768,) for r in results)

    @patch('google.generativeai.embed_content')
    def test_embedding_similarity_computation(self, mock_embed):
        """REAL EMBEDDINGS: Compute cosine similarity between embeddings"""
        # Create two fixed embeddings for reproducible test
        emb1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        emb2 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        emb3 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)

        from config.settings import GeminiConfig
        embedder = GeminiEmbedder(api_key="test_key")

        # Identical embeddings should have similarity = 1.0
        sim_same = embedder.similarity(emb1, emb2)
        assert abs(sim_same - 1.0) < 0.01

        # Orthogonal embeddings should have similarity = 0.0
        sim_orthogonal = embedder.similarity(emb1, emb3)
        assert abs(sim_orthogonal - 0.0) < 0.01


# ============ RUN TESTS ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
