"""
Gemini Embedding System for Semantic Memory Storage
Uses gemini-embedding-001 (state-of-the-art model)
"""
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from config.settings import GeminiConfig
import logging
import numpy as np

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
        GeminiConfig.validate()
        genai.configure(api_key=GeminiConfig.API_KEY)

        if not (128 <= dimension <= 3072):
            raise ValueError(f"Dimension must be between 128 and 3072, got {dimension}")

        self.dimension = dimension
        logger.info(f"Initialized MemoryEmbedder with {self.EMBEDDING_MODEL}, dimension={dimension}")

    def embed_text(self, text: str, task_type: str = "SEMANTIC_SIMILARITY") -> Optional[np.ndarray]:
        """
        Generate embedding for text

        Args:
            text: Text to embed (max 2048 tokens)
            task_type: Task optimization type:
                - SEMANTIC_SIMILARITY (default)
                - RETRIEVAL_DOCUMENT
                - RETRIEVAL_QUERY
                - CLASSIFICATION
                - CLUSTERING
                - QUESTION_ANSWERING
                - FACT_VERIFICATION
                - CODE_RETRIEVAL_QUERY

        Returns:
            Embedding vector as numpy array, or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None

        try:
            result = genai.embed_content(
                model=self.EMBEDDING_MODEL,
                content=text,
                task_type=task_type,
                output_dimensionality=self.dimension
            )

            embedding = np.array(result['embedding'], dtype=np.float32)
            logger.debug(f"Generated embedding with shape {embedding.shape}")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return None

    def embed_batch(self, texts: List[str], task_type: str = "SEMANTIC_SIMILARITY") -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed
            task_type: Task optimization type

        Returns:
            List of embedding vectors (None for failed embeddings)
        """
        logger.info(f"Batch embedding {len(texts)} texts")

        embeddings = []
        for i, text in enumerate(texts):
            embedding = self.embed_text(text, task_type)
            embeddings.append(embedding)

            if (i + 1) % 10 == 0:
                logger.info(f"Embedded {i + 1}/{len(texts)} texts")

        successful = sum(1 for e in embeddings if e is not None)
        logger.info(f"Batch embedding complete: {successful}/{len(texts)} successful")

        return embeddings

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

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0-1, higher is more similar)
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

        Args:
            query_embedding: Query vector
            candidate_embeddings: List of candidate vectors
            top_k: Number of top results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity (highest first)
        """
        similarities = []

        for i, candidate in enumerate(candidate_embeddings):
            if candidate is not None:
                sim = self.cosine_similarity(query_embedding, candidate)
                similarities.append((i, sim))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]
