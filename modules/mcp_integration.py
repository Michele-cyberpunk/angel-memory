"""
MCP Integration Module
Handles communication with OMI MCP Server via Docker
"""
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from config.settings import OMIConfig

logger = logging.getLogger(__name__)

class MCPIntegration:
    """Client for OMI Model Context Protocol Server"""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = None
        self._tools_cache = []
        
        # Check for SSE configuration
        self.sse_url = OMIConfig.MCP_SERVER_URL
        
        if not self.sse_url:
            # Configure Docker command for local MCP server
            self.server_params = StdioServerParameters(
                command="docker",
                args=[
                    "run", "--rm", "-i",
                    "-e", f"OMI_API_KEY={OMIConfig.APP_SECRET}", 
                    "omiai/mcp-server:latest"
                ],
                env=None
            )
        
        logger.info(f"MCP Integration initialized (Mode: {'SSE' if self.sse_url else 'Docker'})")

    async def connect(self):
        """Connect to the MCP server"""
        try:
            from contextlib import AsyncExitStack
            
            self.exit_stack = AsyncExitStack()
            
            if self.sse_url:
                # Connect via SSE
                logger.info(f"Connecting to MCP via SSE: {self.sse_url}")
                self.read_stream, self.write_stream = await self.exit_stack.enter_async_context(
                    sse_client(self.sse_url)
                )
            else:
                # Connect via Stdio (Docker)
                logger.info("Connecting to MCP via Docker (Stdio)")
                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(self.server_params)
                )
                self.read_stream, self.write_stream = stdio_transport
            
            # Start session
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read_stream, self.write_stream)
            )
            
            await self.session.initialize()
            
            # Cache tools
            result = await self.session.list_tools()
            self._tools_cache = result.tools
            
            logger.info(f"Connected to MCP Server. Found {len(self._tools_cache)} tools.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            if self.exit_stack:
                await self.exit_stack.aclose()
            return False

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools in Gemini-compatible format"""
        if not self.session:
            await self.connect()
            
        gemini_tools = []
        for tool in self._tools_cache:
            gemini_tools.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            })
            
        return gemini_tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server"""
        if not self.session:
            await self.connect()
            
        try:
            logger.info(f"Calling MCP tool: {tool_name}")
            result = await self.session.call_tool(tool_name, arguments)
            
            # Parse result content
            if not result.content:
                return None
                
            # Assuming the first content item contains the relevant data
            first_item = result.content[0]
            
            if hasattr(first_item, 'text'):
                import json
                try:
                    # Try to parse as JSON
                    return json.loads(first_item.text)
                except json.JSONDecodeError:
                    # Return raw text if not JSON
                    return first_item.text
            
            return result.content
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise

    async def close(self):
        """Close connection"""
        if self.exit_stack:
            await self.exit_stack.aclose()
            logger.info("MCP connection closed")
