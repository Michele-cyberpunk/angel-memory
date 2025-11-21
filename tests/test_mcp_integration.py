"""
Unit tests for mcp_integration.py module
Tests MCP server integration
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from modules.mcp_integration import MCPIntegration


class TestMCPIntegration:
    """Test MCP Integration functionality"""

    def test_init(self):
        """Test MCP integration initialization"""
        mcp = MCPIntegration()

        assert mcp.session is None
        assert mcp.exit_stack is None
        assert mcp._tools_cache == []

    @patch('modules.mcp_integration.sse_client')
    @patch('modules.mcp_integration.ClientSession')
    async def test_connect_sse(self, mock_session, mock_sse_client):
        """Test SSE connection"""
        # Mock SSE URL
        with patch('modules.mcp_integration.OMIConfig.MCP_SERVER_URL', 'http://test.com'):
            mcp = MCPIntegration()

            mock_read_stream = MagicMock()
            mock_write_stream = MagicMock()
            mock_sse_client.return_value.__aenter__.return_value = (mock_read_stream, mock_write_stream)

            mock_session_instance = MagicMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.initialize = AsyncMock()
            mock_session_instance.list_tools = AsyncMock(return_value=MagicMock(tools=[]))

            result = await mcp.connect()

            assert result == True
            assert mcp.session == mock_session_instance

    async def test_list_tools_without_session(self):
        """Test listing tools without active session"""
        mcp = MCPIntegration()

        with patch.object(mcp, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = True
            mcp._tools_cache = [MagicMock(name="test_tool", description="test", inputSchema={})]

            tools = await mcp.list_tools()

            assert len(tools) == 1
            assert tools[0]["name"] == "test_tool"