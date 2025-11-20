
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from modules.memory_embedder import MemoryEmbedder

def test_embed_batch_implementation():
    """
    Test that embed_batch uses batch processing correctly with new SDK.
    """
    # Mock the Client class
    with patch('modules.memory_embedder.genai.Client') as MockClient:
        # Setup the mock client instance and its method
        mock_client_instance = MockClient.return_value
        mock_embed_content = mock_client_instance.models.embed_content
        
        # Create a mock response object
        mock_response = MagicMock()
        # Create mock embedding objects
        emb1 = MagicMock()
        emb1.values = [0.1] * 768
        emb2 = MagicMock()
        emb2.values = [0.2] * 768
        emb3 = MagicMock()
        emb3.values = [0.3] * 768
        
        mock_response.embeddings = [emb1, emb2, emb3]
        mock_embed_content.return_value = mock_response

        # Initialize embedder (will use the mocked Client)
        embedder = MemoryEmbedder()
        
        texts = ["text1", "text2", "text3"]
        embeddings = embedder.embed_batch(texts)

        # Assert it was called once (using batch API)
        assert mock_embed_content.call_count == 1

        # Verify args
        call_args = mock_embed_content.call_args
        assert call_args.kwargs['contents'] == texts
        assert call_args.kwargs['model'] == "models/gemini-embedding-001"

        # Verify output
        assert len(embeddings) == 3
        assert isinstance(embeddings[0], np.ndarray)
        assert len(embeddings[0]) == 768
        assert embeddings[0][0] == 0.1
