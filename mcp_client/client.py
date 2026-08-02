import asyncio
from contextlib import AsyncExitStack
from typing import Optional, List, Dict, Any, Tuple
from types import SimpleNamespace

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

class MCPClient:
    """A task-bound asynchronous Python wrapper for an MCP client connection."""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.http_client = None
        self.http_url: Optional[str] = None
        self.http_headers: Optional[Dict[str, str]] = None
        
        # Task-bound stdio worker communication
        self._worker_task: Optional[asyncio.Task] = None
        self._request_queue: Optional[asyncio.Queue] = None
        self._is_stdio = False

    async def _stdio_worker_loop(
        self,
        command: str,
        args: List[str],
        env: Dict[str, str],
        init_future: asyncio.Future
    ) -> None:
        """
        Runs the entire lifetime of stdio_client and ClientSession inside a single
        asyncio Task so that anyio cancel scopes are entered and exited in the exact same task.
        """
        server_parameters = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        try:
            async with AsyncExitStack() as stack:
                stdio_transport = await stack.enter_async_context(stdio_client(server_parameters))
                stdio, write = stdio_transport
                session = await stack.enter_async_context(ClientSession(stdio, write))
                await session.initialize()
                self.session = session
                if not init_future.done():
                    init_future.set_result(True)

                # Command execution loop inside the same task scope
                while True:
                    action, payload, res_future = await self._request_queue.get()
                    try:
                        if action == "close":
                            if res_future and not res_future.done():
                                res_future.set_result(None)
                            break
                        elif action == "get_tools":
                            response = await session.list_tools()
                            if res_future and not res_future.done():
                                res_future.set_result(response.tools)
                        elif action == "execute_tool":
                            t_name = payload.get("tool_name")
                            t_args = payload.get("arguments", {})
                            res = await session.call_tool(t_name, arguments=t_args)
                            if res_future and not res_future.done():
                                res_future.set_result(res)
                        else:
                            if res_future and not res_future.done():
                                res_future.set_exception(ValueError(f"Unknown worker action: {action}"))
                    except Exception as e:
                        if res_future and not res_future.done():
                            res_future.set_exception(e)
                    finally:
                        self._request_queue.task_done()
        except Exception as e:
            self.session = None
            if not init_future.done():
                init_future.set_exception(e)
        finally:
            self.session = None
            self._is_stdio = False

    async def connect(self, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        """Connect to an MCP server using task-bound stdio client architecture."""
        import os
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
            
        self._is_stdio = True
        self._request_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        init_future = loop.create_future()
        
        self._worker_task = loop.create_task(self._stdio_worker_loop(command, args, merged_env, init_future))
        try:
            await asyncio.wait_for(init_future, timeout=30.0)
        except Exception as e:
            if self._worker_task and not self._worker_task.done():
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
            raise RuntimeError(f"MCP server startup failed or timed out ({command} {args}): {e}") from e

    async def connect_http(self, url: str, headers: Optional[Dict[str, str]] = None):
        """Connect to a remote MCP server using stateless HTTP JSON-RPC transport."""
        import httpx
        self.http_url = url
        self.http_headers = headers or {}
        self.http_client = httpx.AsyncClient(headers=self.http_headers, timeout=30.0)
        self._is_stdio = False

    async def get_tools(self) -> List[Any]:
        """List available tools from the connected server."""
        if self.http_client and self.http_url:
            payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
            response = await self.http_client.post(self.http_url, json=payload)
            response.raise_for_status()
            data = response.json()
            tools_data = data.get("result", {}).get("tools", [])
            return [SimpleNamespace(name=t["name"], description=t.get("description", ""), inputSchema=t.get("inputSchema", {})) for t in tools_data]
        
        if self._is_stdio:
            if not self._worker_task or self._worker_task.done():
                raise RuntimeError("Not connected to any server (worker task is terminated).")
            loop = asyncio.get_running_loop()
            res_future = loop.create_future()
            await self._request_queue.put(("get_tools", None, res_future))
            return await res_future

        raise RuntimeError("Not connected to any server.")

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
        
        if self._is_stdio:
            if not self._worker_task or self._worker_task.done():
                raise RuntimeError("Not connected to any server (worker task is terminated).")
            loop = asyncio.get_running_loop()
            res_future = loop.create_future()
            await self._request_queue.put(("execute_tool", {"tool_name": tool_name, "arguments": arguments}, res_future))
            return await res_future

        raise RuntimeError("Not connected to any server.")

    async def cleanup(self):
        """Clean up the connection and terminate the server process within proper task scope."""
        if self.http_client:
            try:
                await self.http_client.aclose()
            except BaseException:
                pass
            self.http_client = None
            self.http_url = None
            
        if self._is_stdio and self._worker_task and not self._worker_task.done() and self._request_queue:
            try:
                loop = asyncio.get_running_loop()
                res_future = loop.create_future()
                await self._request_queue.put(("close", None, res_future))
                try:
                    await asyncio.wait_for(res_future, timeout=5.0)
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(self._worker_task, timeout=5.0)
                except (Exception, asyncio.CancelledError):
                    pass
            except Exception:
                if not self._worker_task.done():
                    self._worker_task.cancel()
            finally:
                self._worker_task = None
                self.session = None
                self._is_stdio = False

