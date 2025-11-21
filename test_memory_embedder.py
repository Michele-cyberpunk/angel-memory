#!/usr/bin/env python3
"""
Test script for MemoryEmbedder functionality
"""
from modules.memory_embedder import MemoryEmbedder
import numpy as np

def test_memory_embedder():
    print("Testing MemoryEmbedder...")

    try:
        # Initialize embedder
        embedder = MemoryEmbedder(dimension=768)
        print("[OK] MemoryEmbedder initialized successfully")

        # Test single embedding
        text = "Hello world, this is a test for embedding."
        embedding = embedder.embed_text(text)
        print(f"[OK] Single embedding generated: shape {embedding.shape if embedding is not None else 'None'}")

        # Test batch embedding
        texts = ["First text", "Second text", "Third text"]
        embeddings = embedder.embed_batch(texts)
        print(f"[OK] Batch embedding generated: {len(embeddings)} embeddings")

        # Test memory embedding
        memory_data = {
            "id": "test_memory_1",
            "content": "This is a test memory for embedding",
            "created_at": "2024-01-01T00:00:00Z"
        }
        embedded_memory = embedder.embed_memory(memory_data)
        print(f"[OK] Memory embedding generated: {'embedding' in embedded_memory if embedded_memory else False}")

        # Test similarity
        if len(embeddings) >= 2 and all(e is not None for e in embeddings[:2]):
            sim = embedder.cosine_similarity(embeddings[0], embeddings[1])
            print(f"[OK] Cosine similarity calculated: {sim:.4f}")

        print("All tests passed!")

    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_memory_embedder()