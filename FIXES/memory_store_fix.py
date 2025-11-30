"""
PATCH 1: Memory Store Fix - Multi-User Isolation + Update Mechanism
Fixes:
  - ADD multi-user isolation with uid field
  - ADD update mechanism for existing memories
  - FIX SQLite schema to support user isolation
  - ADD user-scoped queries
  - ADD memory update and soft delete support
"""

import json
import sqlite3
import zlib
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone
import logging
from config.settings import AppSettings

if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

COMPRESSION_THRESHOLD = 1024

# FIXED: Enhanced schema with uid and soft delete support
CREATE_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT NOT NULL,
    uid TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    compressed INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    PRIMARY KEY (id, uid),
    FOREIGN KEY (uid) REFERENCES users (uid) ON DELETE CASCADE
)
"""

CREATE_EMBEDDINGS_TABLE = """
CREATE TABLE IF NOT EXISTS embeddings (
    memory_id TEXT NOT NULL,
    uid TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (memory_id, uid),
    FOREIGN KEY (memory_id, uid) REFERENCES memories (id, uid) ON DELETE CASCADE
)
"""

# ADDED: Users table for isolation
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    uid TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_activity TEXT
)
"""

# ADDED: Audit log for compliance
CREATE_AUDIT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT NOT NULL,
    action TEXT NOT NULL,
    memory_id TEXT,
    timestamp TEXT NOT NULL,
    details TEXT,
    FOREIGN KEY (uid) REFERENCES users (uid) ON DELETE CASCADE
)
"""


class MemoryStoreFixed:
    """
    Fixed Memory Store with:
    - Multi-user isolation
    - Update mechanism
    - Soft deletes
    - Audit logging
    """

    def __init__(self, db_path: str, embedding_dimension: int = 768):
        """Initialize with multi-user support"""
        self.db_path = db_path
        self.dimension = embedding_dimension
        self._init_database()
        logger.info(f"MemoryStore initialized with multi-user isolation at {db_path}")

    def _init_database(self):
        """Initialize all database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(CREATE_USERS_TABLE)
            conn.execute(CREATE_MEMORIES_TABLE)
            conn.execute(CREATE_EMBEDDINGS_TABLE)
            conn.execute(CREATE_AUDIT_LOG_TABLE)
            conn.commit()
        logger.info("Database tables initialized with multi-user schema")

    def _ensure_user_exists(self, uid: str) -> None:
        """Ensure user record exists for isolation"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO users (uid, created_at, last_activity) VALUES (?, ?, ?)",
                    (uid, datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to ensure user exists: {e}")
            raise

    def _audit_log(self, uid: str, action: str, memory_id: Optional[str] = None, details: Optional[str] = None) -> None:
        """Log actions for compliance"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO audit_log (uid, action, memory_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
                    (uid, action, memory_id, datetime.now(timezone.utc).isoformat(), details)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Audit logging failed (non-fatal): {e}")

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

    def add_memory(self, uid: str, content: str, metadata: Optional[Dict[str, Any]] = None,
                   memory_id: Optional[str] = None) -> bool:
        """
        Add memory with user isolation

        Args:
            uid: User identifier
            content: Memory text content
            metadata: Optional metadata
            memory_id: Optional unique ID
        """
        if not content or not content.strip():
            logger.warning(f"Cannot add empty memory for user {uid}")
            return False

        if not uid or not uid.strip():
            logger.error("uid is required for memory isolation")
            return False

        try:
            self._ensure_user_exists(uid)

            compressed_content, is_compressed = self._compress_content(content)
            memory_id = memory_id or f"mem_{uid}_{datetime.now(timezone.utc).timestamp()}"
            created_at = datetime.now(timezone.utc).isoformat()
            metadata_json = json.dumps(metadata or {})

            # Simulate embedding (in production, use actual embedder)
            embedding = np.random.randn(self.dimension).astype(np.float32)
            embedding_bytes = embedding.tobytes()

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN TRANSACTION")
                try:
                    conn.execute(
                        """INSERT INTO memories (id, uid, content, metadata, created_at, updated_at, compressed, version)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (memory_id, uid, compressed_content, metadata_json, created_at, created_at, int(is_compressed), 1)
                    )
                    conn.execute(
                        "INSERT INTO embeddings (memory_id, uid, embedding, created_at) VALUES (?, ?, ?, ?)",
                        (memory_id, uid, embedding_bytes, created_at)
                    )
                    conn.commit()
                    self._audit_log(uid, "CREATE", memory_id, f"Created memory version 1")
                    logger.info(f"Added memory {memory_id} for user {uid}")
                    return True
                except Exception as e:
                    conn.rollback()
                    raise e

        except sqlite3.IntegrityError as e:
            logger.error(f"Memory ID {memory_id} already exists for user {uid}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False

    def update_memory(self, uid: str, memory_id: str, content: str,
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update existing memory with version tracking

        Args:
            uid: User identifier
            memory_id: Memory to update
            content: New content
            metadata: Updated metadata
        """
        if not content or not content.strip():
            logger.warning(f"Cannot update memory with empty content")
            return False

        try:
            self._ensure_user_exists(uid)

            # Verify ownership
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT version FROM memories WHERE id = ? AND uid = ? AND deleted_at IS NULL",
                    (memory_id, uid)
                )
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Memory {memory_id} not found or not owned by user {uid}")
                    return False

                new_version = row[0] + 1

            compressed_content, is_compressed = self._compress_content(content)
            updated_at = datetime.now(timezone.utc).isoformat()
            metadata_json = json.dumps(metadata or {})
            embedding = np.random.randn(self.dimension).astype(np.float32)
            embedding_bytes = embedding.tobytes()

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN TRANSACTION")
                try:
                    conn.execute(
                        """UPDATE memories SET content = ?, metadata = ?, updated_at = ?,
                           compressed = ?, version = ? WHERE id = ? AND uid = ? AND deleted_at IS NULL""",
                        (compressed_content, metadata_json, updated_at, int(is_compressed), new_version, memory_id, uid)
                    )
                    # Update embedding
                    conn.execute(
                        "UPDATE embeddings SET embedding = ?, created_at = ? WHERE memory_id = ? AND uid = ?",
                        (embedding_bytes, updated_at, memory_id, uid)
                    )
                    conn.commit()
                    self._audit_log(uid, "UPDATE", memory_id, f"Updated to version {new_version}")
                    logger.info(f"Updated memory {memory_id} for user {uid} to version {new_version}")
                    return True
                except Exception as e:
                    conn.rollback()
                    raise e

        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return False

    def soft_delete_memory(self, uid: str, memory_id: str) -> bool:
        """
        Soft delete memory (mark as deleted)

        Args:
            uid: User identifier
            memory_id: Memory to delete
        """
        try:
            deleted_at = datetime.now(timezone.utc).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE memories SET deleted_at = ? WHERE id = ? AND uid = ? RETURNING id",
                    (deleted_at, memory_id, uid)
                )
                if cursor.fetchone():
                    conn.commit()
                    self._audit_log(uid, "DELETE", memory_id, "Soft deleted")
                    logger.info(f"Soft deleted memory {memory_id} for user {uid}")
                    return True
                else:
                    logger.warning(f"Memory {memory_id} not found for user {uid}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    def get_user_memories(self, uid: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get user's memories (active only)

        Args:
            uid: User identifier
            limit: Maximum results
            offset: Pagination offset
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT id, content, metadata, created_at, updated_at, version
                       FROM memories
                       WHERE uid = ? AND deleted_at IS NULL
                       ORDER BY updated_at DESC
                       LIMIT ? OFFSET ?""",
                    (uid, limit, offset)
                )
                rows = cursor.fetchall()

            memories = []
            for row in rows:
                memory_id, content, metadata, created_at, updated_at, version = row
                memories.append({
                    "id": memory_id,
                    "content": content,
                    "metadata": json.loads(metadata) if metadata else {},
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "version": version
                })

            return memories

        except Exception as e:
            logger.error(f"Failed to get user memories: {e}")
            return []

    def get_memory(self, uid: str, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific memory owned by user

        Args:
            uid: User identifier
            memory_id: Memory to retrieve
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT id, content, metadata, created_at, updated_at, version
                       FROM memories
                       WHERE id = ? AND uid = ? AND deleted_at IS NULL""",
                    (memory_id, uid)
                )
                row = cursor.fetchone()

            if row:
                memory_id, content, metadata, created_at, updated_at, version = row
                return {
                    "id": memory_id,
                    "content": content,
                    "metadata": json.loads(metadata) if metadata else {},
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "version": version
                }

            logger.warning(f"Memory {memory_id} not found for user {uid}")
            return None

        except Exception as e:
            logger.error(f"Failed to get memory: {e}")
            return None

    def purge_deleted(self, uid: str, days_old: int = 30) -> int:
        """
        Permanently delete soft-deleted memories older than specified days

        Args:
            uid: User identifier
            days_old: Delete records older than this many days
        """
        try:
            cutoff_date = (datetime.now(timezone.utc) - timezone.utc.timedelta(days=days_old)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM memories WHERE uid = ? AND deleted_at IS NOT NULL AND deleted_at < ?",
                    (uid, cutoff_date)
                )
                deleted_count = cursor.rowcount
                conn.commit()

            if deleted_count > 0:
                self._audit_log(uid, "PURGE", None, f"Permanently deleted {deleted_count} old records")
                logger.info(f"Purged {deleted_count} old memories for user {uid}")

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to purge deleted memories: {e}")
            return 0
