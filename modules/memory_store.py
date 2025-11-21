"""
Vector Memory Store with Semantic Search
Stores memories with embeddings for efficient retrieval
Enhanced with SQLite database storage and compression
"""
import json
import sqlite3
import zlib
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone
import logging
from .memory_embedder import MemoryEmbedder
from config.settings import AppSettings

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

# Compression threshold: compress content larger than 1KB
COMPRESSION_THRESHOLD = 1024

# Database schema
CREATE_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL,
    compressed INTEGER DEFAULT 0
)
"""

CREATE_EMBEDDINGS_TABLE = """
CREATE TABLE IF NOT EXISTS embeddings (
    memory_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memories (id) ON DELETE CASCADE
)
"""

class MemoryStore:
    """
    Persistent vector store for memories with semantic search

    Storage format:
    - SQLite database with memories and embeddings tables
    - Automatic compression for large transcripts (>1KB)
    - Data integrity with transactions
    """

    def __init__(self, db_path: str, embedding_dimension: int = 768):
        """
        Initialize memory store with SQLite database

        Args:
            db_path: Path to SQLite database file
            embedding_dimension: Dimension for embeddings (128-3072)
        """
        self.db_path = db_path
        self.embedder = MemoryEmbedder(dimension=embedding_dimension)
        self.dimension = embedding_dimension

        # Initialize database
        self._init_database()

        # Cache for faster access (loaded on demand)
        self._memories_cache: Optional[List[Dict[str, Any]]] = None
        self._embeddings_cache: Optional[np.ndarray] = None

        logger.info(f"MemoryStore initialized with database at {db_path}")

    def _init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(CREATE_MEMORIES_TABLE)
            conn.execute(CREATE_EMBEDDINGS_TABLE)
            conn.commit()
        logger.info("Database tables initialized")

    def _compress_content(self, content: str) -> tuple[str, bool]:
        """Compress content if it exceeds threshold"""
        if len(content.encode('utf-8')) > COMPRESSION_THRESHOLD:
            compressed = zlib.compress(content.encode('utf-8'))
            return compressed.hex(), True
        return content, False

    def _decompress_content(self, content: str, compressed: bool) -> str:
        """Decompress content if it was compressed"""
        if compressed:
            return zlib.decompress(bytes.fromhex(content)).decode('utf-8')
        return content

    def _load_memories_cache(self):
        """Load memories into cache for faster access"""
        if self._memories_cache is not None:
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, content, metadata, created_at, compressed
                FROM memories ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()

        self._memories_cache = []
        for row in rows:
            memory_id, content, metadata, created_at, compressed = row
            content = self._decompress_content(content, compressed)
            metadata = json.loads(metadata) if metadata else {}
            self._memories_cache.append({
                "id": memory_id,
                "content": content,
                "metadata": metadata,
                "created_at": created_at,
                "embedding_dimension": self.dimension
            })

    def _load_embeddings_cache(self):
        """Load embeddings into cache for faster access"""
        if self._embeddings_cache is not None:
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT embedding FROM embeddings
                ORDER BY (SELECT created_at FROM memories WHERE id = memory_id) DESC
            """)
            rows = cursor.fetchall()

        if rows:
            embeddings = []
            for row in rows:
                embedding_bytes = row[0]
                embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                embeddings.append(embedding)
            self._embeddings_cache = np.vstack(embeddings)
        else:
            self._embeddings_cache = np.array([])

    def _invalidate_cache(self):
        """Invalidate caches when data changes"""
        self._memories_cache = None
        self._embeddings_cache = None

    # Legacy file-based loading removed - now using database

    # Legacy file-based saving removed - now using database transactions

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

        # Compress content if needed
        compressed_content, is_compressed = self._compress_content(content)

        # Create memory data
        memory_id = memory_id or f"mem_{datetime.now(timezone.utc).timestamp()}"
        created_at = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata or {})

        # Convert embedding to bytes
        embedding_bytes = embedding.astype(np.float32).tobytes()

        # Insert into database with transaction
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN TRANSACTION")

                # Insert memory
                conn.execute("""
                    INSERT INTO memories (id, content, metadata, created_at, compressed)
                    VALUES (?, ?, ?, ?, ?)
                """, (memory_id, compressed_content, metadata_json, created_at, int(is_compressed)))

                # Insert embedding
                conn.execute("""
                    INSERT INTO embeddings (memory_id, embedding)
                    VALUES (?, ?)
                """, (memory_id, embedding_bytes))

                conn.commit()

            # Invalidate cache
            self._invalidate_cache()

            logger.info(f"Added memory {memory_id}")
            return True

        except sqlite3.IntegrityError as e:
            logger.error(f"Memory ID {memory_id} already exists: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False

    def add_batch(self, memories_data: List[Dict[str, Any]]) -> int:
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
            metadata = mem_data.get("metadata")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            
            success = self.add_memory(
                content=mem_data.get("content", ""),
                metadata=metadata,
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
        # Load memories and embeddings if not cached
        self._load_memories_cache()
        self._load_embeddings_cache()

        if self._memories_cache is None or len(self._memories_cache) == 0:
            logger.warning("Memory store is empty")
            return []

        # Generate query embedding
        query_embedding = self.embedder.embed_text(query, task_type="RETRIEVAL_QUERY")

        if query_embedding is None:
            logger.error("Failed to generate query embedding")
            return []

        if self._embeddings_cache is None:
            return []

        # Find similar
        results = self.embedder.find_similar(
            query_embedding,
            list(self._embeddings_cache),
            top_k=top_k
        )

        # Filter by minimum similarity and format results
        search_results = []
        for idx, similarity in results:
            if similarity >= min_similarity:
                memory = self._memories_cache[idx].copy()
                memory["similarity_score"] = similarity
                search_results.append(memory)

        logger.info(f"Search returned {len(search_results)} results for query: '{query[:50]}...'")
        return search_results

    def get_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get memory by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, content, metadata, created_at, compressed
                FROM memories WHERE id = ?
            """, (memory_id,))
            row = cursor.fetchone()

        if row:
            memory_id, content, metadata, created_at, compressed = row
            content = self._decompress_content(content, compressed)
            metadata = json.loads(metadata) if metadata else {}
            return {
                "id": memory_id,
                "content": content,
                "metadata": metadata,
                "created_at": created_at,
                "embedding_dimension": self.dimension
            }
        return None

    def get_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all memories (most recent first)

        Args:
            limit: Optional limit on number of memories

        Returns:
            List of memories
        """
        # Use cache if available
        self._load_memories_cache()
        if self._memories_cache is not None:
            memories = self._memories_cache.copy()
            if limit:
                memories = memories[:limit]
            return memories

        # Fallback to direct query
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT id, content, metadata, created_at, compressed
                FROM memories ORDER BY created_at DESC
            """
            if limit:
                query += f" LIMIT {limit}"

            cursor = conn.execute(query)
            rows = cursor.fetchall()

        memories = []
        for row in rows:
            memory_id, content, metadata, created_at, compressed = row
            content = self._decompress_content(content, compressed)
            metadata = json.loads(metadata) if metadata else {}
            memories.append({
                "id": memory_id,
                "content": content,
                "metadata": metadata,
                "created_at": created_at,
                "embedding_dimension": self.dimension
            })

        return memories

    def delete_by_id(self, memory_id: str) -> bool:
        """Delete memory by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN TRANSACTION")

                # Check if memory exists
                cursor = conn.execute("SELECT id FROM memories WHERE id = ?", (memory_id,))
                if not cursor.fetchone():
                    logger.warning(f"Memory {memory_id} not found")
                    return False

                # Delete embedding first (due to foreign key)
                conn.execute("DELETE FROM embeddings WHERE memory_id = ?", (memory_id,))

                # Delete memory
                conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

                conn.commit()

            # Invalidate cache
            self._invalidate_cache()

            logger.info(f"Deleted memory {memory_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about memory store"""
        with sqlite3.connect(self.db_path) as conn:
            # Get total count
            cursor = conn.execute("SELECT COUNT(*) FROM memories")
            total_memories = cursor.fetchone()[0]

            # Get oldest and newest
            cursor = conn.execute("""
                SELECT MIN(created_at), MAX(created_at) FROM memories
            """)
            oldest, newest = cursor.fetchone()

            # Get storage size
            cursor = conn.execute("""
                SELECT
                    SUM(LENGTH(content)) + SUM(LENGTH(metadata)) + SUM(LENGTH(embedding))
                FROM memories m LEFT JOIN embeddings e ON m.id = e.memory_id
            """)
            total_bytes = cursor.fetchone()[0] or 0

        storage_size_mb = round(total_bytes / (1024 * 1024), 2)

        return {
            "total_memories": total_memories,
            "embedding_dimension": self.dimension,
            "embedding_model": self.embedder.EMBEDDING_MODEL,
            "storage_size_mb": storage_size_mb,
            "oldest_memory": oldest,
            "newest_memory": newest
        }

    # Legacy storage size calculation removed - now using database stats

    def rebuild_index(self):
        """
        Rebuild embeddings for all existing memories
        Useful if embedding model or dimension changes
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get all memories
            cursor = conn.execute("""
                SELECT id, content, compressed FROM memories ORDER BY created_at
            """)
            memories = cursor.fetchall()

        if not memories:
            logger.info("No memories to rebuild")
            return

        logger.info(f"Rebuilding embeddings for {len(memories)} memories")

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN TRANSACTION")

                for i, (memory_id, content, compressed) in enumerate(memories):
                    # Decompress if needed
                    content = self._decompress_content(content, compressed)

                    # Generate new embedding
                    embedding = self.embedder.embed_text(content, task_type="RETRIEVAL_DOCUMENT")

                    if embedding is not None:
                        embedding_bytes = embedding.astype(np.float32).tobytes()
                        # Update embedding
                        conn.execute("""
                            UPDATE embeddings SET embedding = ? WHERE memory_id = ?
                        """, (embedding_bytes, memory_id))
                    else:
                        logger.warning(f"Failed to rebuild embedding for memory {memory_id}")
                        # Use zero vector as placeholder
                        zero_embedding = np.zeros(self.dimension, dtype=np.float32).tobytes()
                        conn.execute("""
                            UPDATE embeddings SET embedding = ? WHERE memory_id = ?
                        """, (zero_embedding, memory_id))

                    if (i + 1) % 10 == 0:
                        logger.info(f"Rebuilt {i + 1}/{len(memories)} embeddings")

                conn.commit()

            # Invalidate cache
            self._invalidate_cache()
            logger.info("Index rebuild complete")

        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            raise
