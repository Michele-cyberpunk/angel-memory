
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from modules.memory_embedder import MemoryEmbedder

def test_embed_batch_implementation():
    """
    Test that embed_batch uses batch processing correctly.
    """
    embedder = MemoryEmbedder()

    texts = ["text1", "text2", "text3"]

    with patch('google.generativeai.embed_content') as mock_embed:
        # Return a mock response structure for batch request
        # The structure usually has 'embedding' key which is a list of list of floats
        mock_embed.return_value = {'embedding': [[0.1]*768, [0.2]*768, [0.3]*768]}

        embeddings = embedder.embed_batch(texts)

        # Assert it was called once (using batch API)
        assert mock_embed.call_count == 1

        # Verify args
        call_args = mock_embed.call_args
        assert call_args.kwargs['content'] == texts

        # Verify output
        assert len(embeddings) == 3
        assert isinstance(embeddings[0], np.ndarray)
        assert len(embeddings[0]) == 768
