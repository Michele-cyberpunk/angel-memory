"""
Vector Memory Store with Semantic Search
Stores memories with embeddings for efficient retrieval
"""
import json
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import logging
from .memory_embedder import MemoryEmbedder

logger = logging.getLogger(__name__)

class MemoryStore:
    """
    Persistent vector store for memories with semantic search

    Storage format:
    - memories.json: Memory metadata + content
    - embeddings.npy: Numpy array of all embeddings
    """

    def __init__(self, storage_dir: Path, embedding_dimension: int = 768):
        """
        Initialize memory store

        Args:
            storage_dir: Directory to store memories and embeddings
            embedding_dimension: Dimension for embeddings (128-3072)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.memories_file = self.storage_dir / "memories.json"
        self.embeddings_file = self.storage_dir / "embeddings.npy"

        self.embedder = MemoryEmbedder(dimension=embedding_dimension)
        self.dimension = embedding_dimension

        # Load existing data
        self.memories: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = np.array([])

        self._load()

        logger.info(f"MemoryStore initialized with {len(self.memories)} memories at {storage_dir}")

    def _load(self):
        """Load memories and embeddings from disk"""
        try:
            if self.memories_file.exists():
                with open(self.memories_file, 'r', encoding='utf-8') as f:
                    self.memories = json.load(f)
                logger.info(f"Loaded {len(self.memories)} memories from disk")

            if self.embeddings_file.exists():
                self.embeddings = np.load(str(self.embeddings_file))
                logger.info(f"Loaded embeddings with shape {self.embeddings.shape}")

            # Verify consistency
            if len(self.memories) != len(self.embeddings):
                logger.warning(f"Mismatch: {len(self.memories)} memories vs {len(self.embeddings)} embeddings")
                # Truncate to match
                min_len = min(len(self.memories), len(self.embeddings))
                self.memories = self.memories[:min_len]
                self.embeddings = self.embeddings[:min_len]

        except Exception as e:
            logger.error(f"Failed to load from disk: {str(e)}")
            self.memories = []
            self.embeddings = np.array([])

    def _save(self):
        """Save memories and embeddings to disk"""
        try:
            # Save memories as JSON
            with open(self.memories_file, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, indent=2, ensure_ascii=False, default=str)

            # Save embeddings as numpy array
            if len(self.embeddings) > 0:
                np.save(str(self.embeddings_file), self.embeddings)

            logger.info(f"Saved {len(self.memories)} memories to disk")

        except Exception as e:
            logger.error(f"Failed to save to disk: {str(e)}")

    def add_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None,
                  memory_id: Optional[str] = None) -> bool:
        """
        Add a new memory with automatic embedding generation

        Args:
            content: Memory text content
            metadata: Optional metadata (tags, source, etc.)
            memory_id: Optional unique ID

        Returns:
            True if successful
        """
        if not content or not content.strip():
            logger.warning("Cannot add empty memory")
            return False

        # Generate embedding
        embedding = self.embedder.embed_text(content, task_type="RETRIEVAL_DOCUMENT")

        if embedding is None:
            logger.error("Failed to generate embedding for memory")
            return False

        # Create memory object
        memory = {
            "id": memory_id or f"mem_{datetime.utcnow().timestamp()}",
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "embedding_dimension": self.dimension
        }

        # Add to store
        self.memories.append(memory)

        # Add embedding
        if len(self.embeddings) == 0:
            self.embeddings = embedding.reshape(1, -1)
        else:
            self.embeddings = np.vstack([self.embeddings, embedding])

        # Save to disk
        self._save()

        logger.info(f"Added memory {memory['id']}, total: {len(self.memories)}")
        return True

    def add_batch(self, memories_data: List[Dict[str, str]]) -> int:
        """
        Add multiple memories at once

        Args:
            memories_data: List of dicts with 'content' and optional 'metadata', 'id'

        Returns:
            Number of successfully added memories
        """
        logger.info(f"Adding batch of {len(memories_data)} memories")

        success_count = 0
        for mem_data in memories_data:
            success = self.add_memory(
                content=mem_data.get("content", ""),
                metadata=mem_data.get("metadata"),
                memory_id=mem_data.get("id")
            )
            if success:
                success_count += 1

        logger.info(f"Successfully added {success_count}/{len(memories_data)} memories")
        return success_count

    def search(self, query: str, top_k: int = 5, min_similarity: float = 0.0) -> List[Dict[str, Any]]:
        """
        Semantic search for similar memories

        Args:
            query: Search query text
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity threshold (0-1)

        Returns:
            List of memories with similarity scores, sorted by relevance
        """
        if len(self.memories) == 0:
            logger.warning("Memory store is empty")
            return []

        # Generate query embedding
        query_embedding = self.embedder.embed_text(query, task_type="RETRIEVAL_QUERY")

        if query_embedding is None:
            logger.error("Failed to generate query embedding")
            return []

        # Find similar
        results = self.embedder.find_similar(
            query_embedding,
            list(self.embeddings),
            top_k=top_k
        )

        # Filter by minimum similarity and format results
        search_results = []
        for idx, similarity in results:
            if similarity >= min_similarity:
                memory = self.memories[idx].copy()
                memory["similarity_score"] = similarity
                search_results.append(memory)

        logger.info(f"Search returned {len(search_results)} results for query: '{query[:50]}...'")
        return search_results

    def get_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get memory by ID"""
        for memory in self.memories:
            if memory.get("id") == memory_id:
                return memory
        return None

    def get_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all memories (most recent first)

        Args:
            limit: Optional limit on number of memories

        Returns:
            List of memories
        """
        memories = sorted(
            self.memories,
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )

        if limit:
            memories = memories[:limit]

        return memories

    def delete_by_id(self, memory_id: str) -> bool:
        """Delete memory by ID"""
        for i, memory in enumerate(self.memories):
            if memory.get("id") == memory_id:
                # Remove from memories
                self.memories.pop(i)

                # Remove embedding
                self.embeddings = np.delete(self.embeddings, i, axis=0)

                # Save
                self._save()

                logger.info(f"Deleted memory {memory_id}")
                return True

        logger.warning(f"Memory {memory_id} not found")
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about memory store"""
        return {
            "total_memories": len(self.memories),
            "embedding_dimension": self.dimension,
            "embedding_model": self.embedder.EMBEDDING_MODEL,
            "storage_size_mb": self._get_storage_size_mb(),
            "oldest_memory": self.memories[0].get("created_at") if self.memories else None,
            "newest_memory": self.memories[-1].get("created_at") if self.memories else None
        }

    def _get_storage_size_mb(self) -> float:
        """Calculate total storage size in MB"""
        total_bytes = 0

        if self.memories_file.exists():
            total_bytes += self.memories_file.stat().st_size

        if self.embeddings_file.exists():
            total_bytes += self.embeddings_file.stat().st_size

        return round(total_bytes / (1024 * 1024), 2)

    def rebuild_index(self):
        """
        Rebuild embeddings for all existing memories
        Useful if embedding model or dimension changes
        """
        logger.info(f"Rebuilding embeddings for {len(self.memories)} memories")

        new_embeddings = []

        for i, memory in enumerate(self.memories):
            content = memory.get("content", "")
            embedding = self.embedder.embed_text(content, task_type="RETRIEVAL_DOCUMENT")

            if embedding is not None:
                new_embeddings.append(embedding)
            else:
                logger.warning(f"Failed to rebuild embedding for memory {i}")
                # Use zero vector as placeholder
                new_embeddings.append(np.zeros(self.dimension, dtype=np.float32))

            if (i + 1) % 10 == 0:
                logger.info(f"Rebuilt {i + 1}/{len(self.memories)} embeddings")

        if new_embeddings:
            self.embeddings = np.vstack(new_embeddings)
            self._save()
            logger.info("Index rebuild complete")
