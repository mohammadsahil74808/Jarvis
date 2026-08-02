import asyncio
from contextlib import AsyncExitStack
from typing import Optional, List, Dict, Any
from types import SimpleNamespace

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

class MCPClient:
    """A low-level asynchronous Python wrapper for an MCP client connection."""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.http_client = None
        self.http_url: Optional[str] = None
        self.http_headers: Optional[Dict[str, str]] = None

    async def connect(self, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        """Connect to an MCP server using stdio."""
        import os
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
            
        server_parameters = StdioServerParameters(
            command=command,
            args=args,
            env=merged_env
        )

        # Enter the stdio client context
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_parameters))
        self.stdio, self.write = stdio_transport
        
        # Initialize the session
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()

    async def connect_http(self, url: str, headers: Optional[Dict[str, str]] = None):
        """Connect to a remote MCP server using stateless HTTP JSON-RPC transport."""
        import httpx
        self.http_url = url
        self.http_headers = headers or {}
        self.http_client = httpx.AsyncClient(headers=self.http_headers, timeout=30.0)

    async def get_tools(self) -> List[Any]:
        """List available tools from the connected server."""
        if self.http_client and self.http_url:
            payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
            response = await self.http_client.post(self.http_url, json=payload)
            response.raise_for_status()
            data = response.json()
            tools_data = data.get("result", {}).get("tools", [])
            return [SimpleNamespace(name=t["name"], description=t.get("description", ""), inputSchema=t.get("inputSchema", {})) for t in tools_data]
        if not self.session:
            raise RuntimeError("Not connected to any server.")
        response = await self.session.list_tools()
        return response.tools

    async def execute_tool(self, tool_name: str, arguments: dict) -> CallToolResult:
        """Execute a tool with given arguments."""
        if self.http_client and self.http_url:
            payload = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}, "id": 2}
            response = await self.http_client.post(self.http_url, json=payload)
            data = response.json()
            res_data = data.get("result", {})
            is_error = res_data.get("isError", False)
            content_list = res_data.get("content", [])
            if "error" in data:
                is_error = True
                content_list = [{"type": "text", "text": str(data["error"])}]
            content_objs = [SimpleNamespace(type=c.get("type", "text"), text=c.get("text", str(c))) for c in content_list]
            return SimpleNamespace(isError=is_error, content=content_objs)
        if not self.session:
            raise RuntimeError("Not connected to any server.")
        return await self.session.call_tool(tool_name, arguments=arguments)

    async def cleanup(self):
        """Clean up the connection and terminate the server process."""
        if self.http_client:
            try:
                await self.http_client.aclose()
            except BaseException:
                pass
            self.http_client = None
            self.http_url = None
        try:
            await self.exit_stack.aclose()
        except BaseException:
            pass
        self.session = None

