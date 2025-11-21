"""
Unit tests for omi_client.py module
Tests OMI API client functionality
"""
import pytest
from unittest.mock import patch, MagicMock

from modules.omi_client import OMIClient


class TestOMIClient:
    """Test OMI API client"""

    @patch('modules.omi_client.requests.post')
    @patch('modules.omi_client.requests.get')
    def test_init(self, mock_get, mock_post):
        """Test OMI client initialization"""
        client = OMIClient()

        assert client.base_url == "https://api.omi.me"
        assert client.app_id is None  # Not set in env
        assert client.app_secret is None

    @patch('modules.omi_client.requests.post')
    def test_create_memories(self, mock_post):
        """Test memory creation"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "memories": [{"id": "mem1"}]}
        mock_post.return_value = mock_response

        client = OMIClient()
        result = client.create_memories("test content", [{"content": "test"}])

        assert result["success"] == True
        assert len(result["memories"]) == 1

    @patch('modules.omi_client.requests.post')
    def test_send_notification(self, mock_post):
        """Test notification sending"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = OMIClient()
        result = client.send_notification("test message", "user123")

        assert result == True

    @patch('modules.omi_client.requests.get')
    def test_read_conversations(self, mock_get):
        """Test conversation reading"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"conversations": [{"id": "conv1", "text": "test"}]}
        mock_get.return_value = mock_response

        client = OMIClient()
        result = client.read_conversations(limit=5)

        assert len(result) > 0
        assert result[0]["id"] == "conv1"