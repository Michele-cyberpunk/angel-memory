"""
Gemini Embedding System for Semantic Memory Storage
Uses gemini-embedding-001 (state-of-the-art model)
"""
import google.genai as genai
from google.genai import types
from typing import List, Dict, Any, Optional
from config.settings import GeminiConfig, AppSettings
from modules.api_utils import with_gemini_rate_limit_and_retry
import logging
import numpy as np

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class MemoryEmbedder:
    """Generate semantic embeddings for memories using Gemini"""

    EMBEDDING_MODEL = "models/gemini-embedding-001"
    DEFAULT_DIMENSION = 768  # Recommended dimension for balance between performance and size

    def __init__(self, dimension: int = DEFAULT_DIMENSION):
        """
        Initialize embedder with Gemini API

        Args:
            dimension: Output dimension (128-3072, recommended: 768, 1536, 3072)
        """
        try:
            GeminiConfig.validate()
            self.client = genai.Client(api_key=GeminiConfig.API_KEY)
            logger.debug("Gemini client initialized for embeddings")
        except Exception as e:
            logger.error("Failed to initialize Gemini client", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        if not (128 <= dimension <= 3072):
            logger.error("Invalid dimension parameter", extra={
                "dimension": dimension,
                "valid_range": "128-3072"
            })
            raise ValueError(f"Dimension must be between 128 and 3072, got {dimension}")

        self.dimension = dimension
        logger.info("MemoryEmbedder initialized successfully", extra={
            "model": self.EMBEDDING_MODEL,
            "dimension": dimension
        })

    @with_gemini_rate_limit_and_retry
    def _call_embedding_api(self, text: str, task_type: str) -> Any:
        """
        Call Gemini embedding API with rate limiting and retry logic

        Args:
            text: Text to embed
            task_type: Task optimization type

        Returns:
            API response object
        """
        result = self.client.models.embed_content(
            model=self.EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dimension
            )
        )
        return result

    def embed_text(self, text: str, task_type: str = "SEMANTIC_SIMILARITY") -> Optional[np.ndarray]:
        """
        Generate embedding for text

        Args:
            text: Text to embed (max 2048 tokens)
            task_type: Task optimization type
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding", extra={
                "text_length": len(text) if text else 0,
                "task_type": task_type
            })
            return None

        try:
            logger.debug("Generating embedding", extra={
                "text_length": len(text),
                "task_type": task_type,
                "model": self.EMBEDDING_MODEL,
                "dimension": self.dimension
            })

            result = self._call_embedding_api(text, task_type)

            # New SDK returns object with .embeddings attribute which is a list of Embedding objects
            # For single content, we expect one embedding
            if result.embeddings:
                embedding = np.array(result.embeddings[0].values, dtype=np.float32)
                logger.debug("Embedding generated successfully", extra={
                    "shape": embedding.shape,
                    "task_type": task_type
                })
                return embedding

            logger.warning("No embeddings returned from API", extra={
                "task_type": task_type,
                "text_preview": text[:100] + "..." if len(text) > 100 else text
            })
            return None

        except Exception as e:
            logger.error("Failed to generate embedding", exc_info=True, extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "task_type": task_type,
                "text_length": len(text)
            })
            return None

    @with_gemini_rate_limit_and_retry
    def _call_batch_embedding_api(self, texts: List[str], task_type: str) -> Any:
        """
        Call Gemini batch embedding API with rate limiting and retry logic

        Args:
            texts: List of texts to embed
            task_type: Task optimization type

        Returns:
            API response object
        """
        result = self.client.models.embed_content(
            model=self.EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dimension
            )
        )
        return result

    def embed_batch(self, texts: List[str], task_type: str = "SEMANTIC_SIMILARITY") -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple texts using batch API

        Args:
            texts: List of texts to embed
            task_type: Task optimization type
        """
        if not texts:
            return []

        logger.info(f"Batch embedding {len(texts)} texts")

        try:
            result = self._call_batch_embedding_api(texts, task_type)

            if result.embeddings:
                embeddings = [
                    np.array(emb.values, dtype=np.float32)
                    for emb in result.embeddings
                ]
                logger.info(f"Batch embedding complete: {len(embeddings)}/{len(texts)} successful")
                return list(embeddings)

            logger.warning("No embeddings returned in batch response")
            return [None] * len(texts)

        except Exception as e:
            logger.error(f"Batch embedding failed: {str(e)}")
            # Fallback to sequential if batch fails
            logger.info("Falling back to sequential embedding")
            fallback_embeddings: List[Optional[np.ndarray]] = []
            for i, text in enumerate(texts):
                embedding = self.embed_text(text, task_type)
                fallback_embeddings.append(embedding)
            
            # Filter out None values for return, or handle as needed
            # Assuming callers expect valid embeddings or we should filter
            valid_embeddings: List[Optional[np.ndarray]] = [e for e in fallback_embeddings if e is not None]
            if len(valid_embeddings) != len(texts):
                 logger.warning(f"Sequential embedding partial failure: {len(valid_embeddings)}/{len(texts)} successful")
            
            return valid_embeddings

    def embed_memory(self, memory_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Embed a complete memory object with metadata

        Args:
            memory_data: Memory object containing 'content', 'id', 'created_at', etc.

        Returns:
            Dict with original memory + 'embedding' field, or None if failed
        """
        content = memory_data.get("content", "")

        if not content:
            logger.warning(f"Memory {memory_data.get('id')} has no content")
            return None

        embedding = self.embed_text(content, task_type="RETRIEVAL_DOCUMENT")

        if embedding is None:
            return None

        return {
            **memory_data,
            "embedding": embedding,
            "embedding_model": self.EMBEDDING_MODEL,
            "embedding_dimension": self.dimension
        }

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors
        """
        if vec1 is None or vec2 is None:
            return 0.0

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def find_similar(self, query_embedding: np.ndarray,
                    candidate_embeddings: List[np.ndarray],
                    top_k: int = 5) -> List[tuple[int, float]]:
        """
        Find most similar embeddings to query
        """
        similarities = []

        for i, candidate in enumerate(candidate_embeddings):
            if candidate is not None:
                sim = self.cosine_similarity(query_embedding, candidate)
                similarities.append((i, sim))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]
