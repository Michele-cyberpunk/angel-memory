"""
PATCH AGGIUNTIVO: Real Gemini Embeddings Integration
Sostituisce il placeholder np.random.randn() con Gemini embeddings API reale

Utilizzo:
  from gemini_embeddings_real import GeminiEmbedder
  embedder = GeminiEmbedder(api_key="AIzaSyAxtA0...")
  embedding = embedder.embed("text to embed")
"""

import google.generativeai as genai
from typing import List
import numpy as np
import logging

logger = logging.getLogger(__name__)


class GeminiEmbedder:
    """Produce real embeddings usando Gemini Embedding API"""

    def __init__(self, api_key: str):
        """Inizializza con API key Gemini"""
        genai.configure(api_key=api_key)
        self.model = "models/embedding-001"

    def embed_text(self, text: str) -> np.ndarray:
        """
        Genera embedding reale di un testo usando Gemini API

        Args:
            text: Testo da embeddare

        Returns:
            numpy array (768D) con l'embedding

        Raises:
            Exception: Se API call fallisce
        """
        try:
            result = genai.embed_content(
                model=self.model,
                content=text,
                task_type="SEMANTIC_SIMILARITY"
            )

            embedding = np.array(result['embedding'], dtype=np.float32)
            logger.info(f"✅ Embedding generato: {len(embedding)} dimensioni")
            return embedding

        except Exception as e:
            logger.error(f"❌ Errore durante embedding: {e}")
            raise

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Genera embeddings per multiple texts (batch)

        Args:
            texts: Lista di testi

        Returns:
            Lista di numpy arrays (embeddings)
        """
        embeddings = []
        for text in texts:
            try:
                embedding = self.embed_text(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.warning(f"Skipping text due to error: {e}")
                embeddings.append(np.zeros(768, dtype=np.float32))

        return embeddings

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calcola cosine similarity tra due embeddings

        Args:
            emb1, emb2: numpy arrays

        Returns:
            Similarity score 0-1
        """
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


# Integration con memory_store_fix.py
def replace_placeholder_embedder():
    """
    Modifica memory_store_fix.py per usare GeminiEmbedder reale

    Instead di:
        embedding = np.random.randn(self.dimension).astype(np.float32)

    Use:
        embedder = GeminiEmbedder(api_key=GeminiConfig.API_KEY)
        embedding = embedder.embed_text(memory_text)
    """
    pass


if __name__ == "__main__":
    # Test
    from config.settings import GeminiConfig

    embedder = GeminiEmbedder(api_key=GeminiConfig.API_KEY)

    # Test 1: Single text
    text1 = "Hello world, this is a test"
    emb1 = embedder.embed_text(text1)
    print(f"✅ Embedding 1: {emb1.shape}")

    # Test 2: Batch
    texts = [
        "This is the first memory",
        "This is the second memory",
        "Another memory"
    ]
    embeddings = embedder.embed_batch(texts)
    print(f"✅ Batch embeddings: {len(embeddings)} embeddings created")

    # Test 3: Similarity
    sim = embedder.similarity(emb1, embeddings[0])
    print(f"✅ Similarity score: {sim:.4f}")
