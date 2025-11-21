"""
Unit tests for memory_store.py module
Tests vector memory storage and semantic search
"""
import pytest
import tempfile
import os
import numpy as np
from unittest.mock import patch, MagicMock

from modules.memory_store import MemoryStore


class TestMemoryStoreInit:
    """Test MemoryStore initialization"""

    def test_init_creates_database(self, temp_db_path):
        """Test initialization creates database file"""
        store = MemoryStore(temp_db_path, embedding_dimension=128)

        assert os.path.exists(temp_db_path)
        assert store.db_path == temp_db_path
        assert store.dimension == 128

    def test_init_with_custom_dimension(self, temp_db_path):
        """Test initialization with custom embedding dimension"""
        store = MemoryStore(temp_db_path, embedding_dimension=512)

        assert store.dimension == 512

    @patch('modules.memory_store.MemoryEmbedder')
    def test_init_embedder_initialization(self, mock_embedder_class, temp_db_path):
        """Test that embedder is properly initialized"""
        mock_embedder = MagicMock()
        mock_embedder_class.return_value = mock_embedder

        store = MemoryStore(temp_db_path)

        mock_embedder_class.assert_called_once_with(dimension=768)
        assert store.embedder == mock_embedder


class TestMemoryStoreCompression:
    """Test content compression functionality"""

    def test_compress_content_small(self, temp_db_path):
        """Test compression of small content (no compression)"""
        store = MemoryStore(temp_db_path)

        content = "Small content"
        compressed, is_compressed = store._compress_content(content)

        assert compressed == content
        assert is_compressed == False

    def test_compress_content_large(self, temp_db_path):
        """Test compression of large content"""
        store = MemoryStore(temp_db_path)

        large_content = "A" * 2000  # Over 1KB threshold
        compressed, is_compressed = store._compress_content(large_content)

        assert compressed != large_content
        assert is_compressed == True
        assert len(compressed) < len(large_content)

    def test_decompress_content_uncompressed(self, temp_db_path):
        """Test decompression of uncompressed content"""
        store = MemoryStore(temp_db_path)

        content = "Test content"
        result = store._decompress_content(content, False)

        assert result == content

    def test_decompress_content_compressed(self, temp_db_path):
        """Test decompression of compressed content"""
        store = MemoryStore(temp_db_path)

        original = "A" * 2000
        compressed, _ = store._compress_content(original)
        result = store._decompress_content(compressed, True)

        assert result == original


class TestMemoryStoreCRUD:
    """Test Create, Read, Update, Delete operations"""

    def test_add_memory_success(self, temp_db_path):
        """Test successful memory addition"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            success = store.add_memory("Test memory content", {"source": "test"})

        assert success == True

        # Verify memory was added
        memories = store.get_all()
        assert len(memories) == 1
        assert memories[0]["content"] == "Test memory content"
        assert memories[0]["metadata"]["source"] == "test"

    def test_add_memory_empty_content(self, temp_db_path):
        """Test adding memory with empty content"""
        store = MemoryStore(temp_db_path)

        success = store.add_memory("")
        assert success == False

        success = store.add_memory("   ")
        assert success == False

    def test_add_memory_embedding_failure(self, temp_db_path):
        """Test memory addition when embedding fails"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=None):
            success = store.add_memory("Test content")

        assert success == False

    def test_add_memory_with_custom_id(self, temp_db_path):
        """Test adding memory with custom ID"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            success = store.add_memory("Test content", memory_id="custom_id")

        assert success == True

        memory = store.get_by_id("custom_id")
        assert memory is not None
        assert memory["id"] == "custom_id"

    def test_add_memory_duplicate_id(self, temp_db_path):
        """Test adding memory with duplicate ID"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            success1 = store.add_memory("Content 1", memory_id="duplicate_id")
            success2 = store.add_memory("Content 2", memory_id="duplicate_id")

        assert success1 == True
        assert success2 == False

    def test_get_by_id_existing(self, temp_db_path):
        """Test retrieving existing memory by ID"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Test content", memory_id="test_id")

        memory = store.get_by_id("test_id")

        assert memory is not None
        assert memory["id"] == "test_id"
        assert memory["content"] == "Test content"

    def test_get_by_id_nonexistent(self, temp_db_path):
        """Test retrieving non-existent memory by ID"""
        store = MemoryStore(temp_db_path)

        memory = store.get_by_id("nonexistent")

        assert memory is None

    def test_get_all_memories(self, temp_db_path):
        """Test retrieving all memories"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Memory 1")
            store.add_memory("Memory 2")
            store.add_memory("Memory 3")

        memories = store.get_all()

        assert len(memories) == 3
        # Should be ordered by creation time (most recent first)
        assert memories[0]["content"] == "Memory 3"
        assert memories[1]["content"] == "Memory 2"
        assert memories[2]["content"] == "Memory 1"

    def test_get_all_with_limit(self, temp_db_path):
        """Test retrieving memories with limit"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            for i in range(5):
                store.add_memory(f"Memory {i}")

        memories = store.get_all(limit=3)

        assert len(memories) == 3

    def test_delete_by_id_existing(self, temp_db_path):
        """Test deleting existing memory"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Test content", memory_id="delete_test")

        success = store.delete_by_id("delete_test")

        assert success == True

        # Verify deletion
        memory = store.get_by_id("delete_test")
        assert memory is None

    def test_delete_by_id_nonexistent(self, temp_db_path):
        """Test deleting non-existent memory"""
        store = MemoryStore(temp_db_path)

        success = store.delete_by_id("nonexistent")

        assert success == False


class TestMemoryStoreBatch:
    """Test batch memory operations"""

    def test_add_batch_success(self, temp_db_path):
        """Test successful batch addition"""
        store = MemoryStore(temp_db_path)

        batch_data = [
            {"content": "Memory 1", "metadata": {"tag": "test1"}},
            {"content": "Memory 2", "metadata": {"tag": "test2"}},
            {"content": "Memory 3", "metadata": {"tag": "test3"}}
        ]

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            count = store.add_batch(batch_data)

        assert count == 3

        memories = store.get_all()
        assert len(memories) == 3

    def test_add_batch_partial_failure(self, temp_db_path):
        """Test batch addition with some failures"""
        store = MemoryStore(temp_db_path)

        # Mock embedder to fail on second call
        call_count = 0
        def mock_embed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return None
            return np.random.rand(768)

        batch_data = [
            {"content": "Memory 1"},
            {"content": ""},  # This should fail
            {"content": "Memory 3"}
        ]

        with patch.object(store.embedder, 'embed_text', side_effect=mock_embed):
            count = store.add_batch(batch_data)

        assert count == 2  # Only first and third should succeed


class TestMemoryStoreSearch:
    """Test semantic search functionality"""

    def test_search_empty_store(self, temp_db_path):
        """Test search on empty memory store"""
        store = MemoryStore(temp_db_path)

        results = store.search("test query")

        assert results == []

    def test_search_with_memories(self, temp_db_path):
        """Test search with existing memories"""
        store = MemoryStore(temp_db_path)

        # Add some test memories
        test_memories = [
            "I love programming with Python",
            "Machine learning is fascinating",
            "The weather is nice today",
            "I enjoy reading science fiction books"
        ]

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            for memory in test_memories:
                store.add_memory(memory)

        # Mock the search functionality
        with patch.object(store.embedder, 'find_similar', return_value=[(0, 0.9), (1, 0.8)]):
            with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
                results = store.search("programming and coding", top_k=2)

        assert len(results) == 2
        assert "similarity_score" in results[0]
        assert results[0]["similarity_score"] == 0.9

    def test_search_embedding_failure(self, temp_db_path):
        """Test search when query embedding fails"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Test memory")

        with patch.object(store.embedder, 'embed_text', return_value=None):
            results = store.search("test query")

        assert results == []

    def test_search_with_min_similarity(self, temp_db_path):
        """Test search with minimum similarity threshold"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Test memory")

        # Mock find_similar to return low similarity
        with patch.object(store.embedder, 'find_similar', return_value=[(0, 0.3)]):
            with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
                results = store.search("test query", min_similarity=0.5)

        assert results == []  # Should filter out low similarity


class TestMemoryStoreStats:
    """Test memory store statistics"""

    def test_get_stats_empty_store(self, temp_db_path):
        """Test statistics for empty store"""
        store = MemoryStore(temp_db_path)

        stats = store.get_stats()

        assert stats["total_memories"] == 0
        assert stats["embedding_dimension"] == 768
        assert stats["storage_size_mb"] == 0.0
        assert stats["oldest_memory"] is None
        assert stats["newest_memory"] is None

    def test_get_stats_with_memories(self, temp_db_path):
        """Test statistics with memories"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Test memory 1")
            store.add_memory("Test memory 2")

        stats = store.get_stats()

        assert stats["total_memories"] == 2
        assert stats["embedding_dimension"] == 768
        assert stats["storage_size_mb"] >= 0.0
        assert stats["oldest_memory"] is not None
        assert stats["newest_memory"] is not None


class TestMemoryStoreCache:
    """Test memory store caching functionality"""

    def test_cache_invalidation_on_add(self, temp_db_path):
        """Test cache invalidation when adding memories"""
        store = MemoryStore(temp_db_path)

        # Initially no cache
        assert store._memories_cache is None
        assert store._embeddings_cache is None

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Test memory")

        # Cache should be invalidated after add
        assert store._memories_cache is None
        assert store._embeddings_cache is None

    def test_cache_loading(self, temp_db_path):
        """Test cache loading functionality"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Test memory")

        # Load caches
        store._load_memories_cache()
        store._load_embeddings_cache()

        assert store._memories_cache is not None
        assert len(store._memories_cache) == 1
        assert store._embeddings_cache is not None


class TestMemoryStoreRebuild:
    """Test index rebuilding functionality"""

    def test_rebuild_index_empty_store(self, temp_db_path):
        """Test rebuilding index on empty store"""
        store = MemoryStore(temp_db_path)

        # Should not raise exception
        store.rebuild_index()

    def test_rebuild_index_with_memories(self, temp_db_path):
        """Test rebuilding index with existing memories"""
        store = MemoryStore(temp_db_path)

        with patch.object(store.embedder, 'embed_text', return_value=np.random.rand(768)):
            store.add_memory("Memory 1")
            store.add_memory("Memory 2")

        # Rebuild should work
        store.rebuild_index()

        # Cache should be invalidated
        assert store._memories_cache is None
        assert store._embeddings_cache is None