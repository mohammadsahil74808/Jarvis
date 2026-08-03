import asyncio
import json
import os
import urllib.request
from pathlib import Path
from typing import Dict, Any, List

from mcp_client.client import MCPClient

def convert_to_gemini_schema(schema: Any) -> Any:
    """Recursively converts JSON Schema to Gemini Schema format and strips all unsupported keywords.
    
    Gemini function declarations accept only a strict subset of JSON Schema:
      type, description, properties, required, items, enum, anyOf, format, nullable
    All other JSON Schema keywords must be removed to prevent Pydantic validation errors.
    """
    if not schema:
        return None
    if not isinstance(schema, dict):
        return schema

    # Complete set of keywords NOT supported by Gemini's function declaration schema
    STRIP_KEYS = {
        "$schema", "$id", "$ref", "$defs", "$comment", "$anchor",
        "additionalProperties", "additional_properties",
        "unevaluatedProperties", "unevaluatedItems",
        "patternProperties", "propertyNames",
        "title", "default", "examples", "example",
        "if", "then", "else",
        "allOf", "oneOf", "not",
        "contains", "minContains", "maxContains",
        "prefixItems",
        "dependentSchemas", "dependentRequired", "dependencies",
        "minProperties", "maxProperties",
        "contentEncoding", "contentMediaType", "contentSchema",
        "readOnly", "writeOnly", "deprecated",
    }

    new_schema: Dict[str, Any] = {}
    for k, v in schema.items():
        if k in STRIP_KEYS:
            continue
        if k == "type" and isinstance(v, str):
            new_schema[k] = v.upper()
        elif isinstance(v, dict):
            new_schema[k] = convert_to_gemini_schema(v)
        elif isinstance(v, list):
            new_schema[k] = [
                convert_to_gemini_schema(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            new_schema[k] = v

    # Validate that all 'required' keys actually exist in 'properties'
    if "required" in new_schema and isinstance(new_schema["required"], list):
        props = new_schema.get("properties", {})
        valid_required = []
        for req in new_schema["required"]:
            if req in props:
                valid_required.append(req)
            else:
                print(f"[MCP WARNING] Removed undefined required property: '{req}'")
        if valid_required:
            new_schema["required"] = valid_required
        else:
            del new_schema["required"]

    return new_schema

class MCPManager:
    """Manager to handle reading config and orchestrating MCP clients."""
    
    def __init__(self, config_path: str = r"C:\Projects\Jarvis\mcp_client\config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.clients: Dict[str, MCPClient] = {}
        self._gemini_tools_cache = []
        self._github_username_cache = None
        self._event_listeners = []
        self._tool_to_server: Dict[str, str] = {}

    def add_event_listener(self, callback):
        """Register a callback for MCP tool lifecycle events: (event_type, tool_name, data)."""
        if callback not in self._event_listeners:
            self._event_listeners.append(callback)

    def _emit_event(self, event_type: str, tool_name: str, data: dict):
        for cb in self._event_listeners:
            try:
                cb(event_type, tool_name, data)
            except Exception as e:
                print(f"[MCP EVENT BRIDGE] Listener error: {e}")

    def _load_config(self):
        with open(self.config_path, "r") as f:
            return json.load(f)

    async def init_client(self, server_name: str) -> MCPClient:
        """Initialize and connect a resilient client for the given server name."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
            
        tag = f"MCP {server_name.upper().replace('_', ' ')}"
        if server_name in self.clients:
            c = self.clients[server_name]
            is_stale_loop = False
            try:
                loop = asyncio.get_running_loop()
                task_loop = getattr(c._worker_task, "_loop", None) if c._worker_task else None
                if task_loop and task_loop != loop:
                    is_stale_loop = True
                elif loop.is_closed():
                    is_stale_loop = True
            except Exception:
                is_stale_loop = True

            if getattr(c, "_is_stdio", False) and (is_stale_loop or not c._worker_task or c._worker_task.done()):
                print(f"[{tag}] Stale or disconnected worker detected for {server_name}. Cleaning up before reconnecting...")
                try:
                    await c.cleanup()
                except Exception:
                    pass
                self.clients.pop(server_name, None)
            else:
                return self.clients[server_name]
            
        server_config = self.config.get("mcpServers", {}).get(server_name)
        if not server_config:
            raise ValueError(f"Server '{server_name}' not found in config.")
        
        command = server_config.get("command")
        args = list(server_config.get("args", []))
        env = server_config.get("env")
        
        if server_name == "sqlite":
            db_path = args[-1] if args else "C:\\Projects\\Jarvis\\data\\jarvis.db"
            db_dir = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(db_dir, exist_ok=True)
        elif server_name == "playwright":
            try:
                from jarvis.browser.browser_context import get_chrome_automation_config, get_jarvis_dedicated_profile_dir
                cfg = get_chrome_automation_config()
                if cfg.get("cdp_endpoint"):
                    for conflicting_flag in ("--browser", "--user-data-dir", "--executable-path"):
                        while conflicting_flag in args:
                            idx = args.index(conflicting_flag)
                            del args[idx:idx+2]
                    if "--cdp-endpoint" not in args:
                        args.extend(["--cdp-endpoint", cfg["cdp_endpoint"]])
                else:
                    if cfg.get("executable_path") and "--executable-path" not in args:
                        args.extend(["--executable-path", cfg["executable_path"]])
                    jarvis_prof = str(get_jarvis_dedicated_profile_dir())
                    if "--user-data-dir" not in args:
                        args.extend(["--user-data-dir", jarvis_prof])
            except Exception as e:
                print(f"[MCP PLAYWRIGHT WARNING] Failed to resolve Google Chrome configuration: {e}")
        
        if server_name == "google_drive":
            print(f"[{tag}] Starting...")
        else:
            print(f"[{tag}] Starting {server_name} MCP...")
            
        client = MCPClient()
        try:
            if server_config.get("transport") == "http":
                url = server_config.get("url")
                headers = {}
                if server_name == "google_drive":
                    try:
                        from mcp_client.google_auth import get_google_drive_token
                        token = get_google_drive_token()
                        headers["Authorization"] = f"Bearer {token}"
                    except Exception as e:
                        print(f"[{tag}] Authentication failed: {e}")
                        raise
                await client.connect_http(url, headers=headers)
                print(f"[{tag}] Connected")
                if server_name == "google_drive" and "Authorization" in headers:
                    print(f"[{tag}] Authenticated")
            else:
                await client.connect(command, args, env=env)
                print(f"[{tag}] Connected")
                
            if server_name == "filesystem":
                try:
                    from mcp_client.filesystem_security import get_filesystem_security_manager
                    get_filesystem_security_manager().print_startup_logs()
                except Exception as e:
                    print(f"[SECURITY WARNING] Failed to initialize security manager: {e}")

            if server_name == "sqlite":
                db_path = args[-1] if args else "C:\\Projects\\Jarvis\\data\\jarvis.db"
                print(f"[{tag}] Database: {db_path}")
            self.clients[server_name] = client
            return client
        except Exception as e:
            await client.cleanup()
            self.clients.pop(server_name, None)
            print(f"[{tag}] Startup failed: {e}")
            raise
        
    def _resolve_github_username(self) -> str:
        """Dynamically resolve the authenticated GitHub username via API."""
        if self._github_username_cache is not None:
            return self._github_username_cache
            
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
            
        token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            server_config = self.config.get("mcpServers", {}).get("github", {})
            token = server_config.get("env", {}).get("GITHUB_PERSONAL_ACCESS_TOKEN")
            
        if not token:
            print("[MCP GITHUB ERROR] GITHUB_PERSONAL_ACCESS_TOKEN is missing from environment!")
            print("[MCP GITHUB ERROR] Please set $env:GITHUB_PERSONAL_ACCESS_TOKEN in PowerShell or add it to c:\\Projects\\Jarvis\\.env")
            self._github_username_cache = ""
            return ""
            
        try:
            req = urllib.request.Request("https://api.github.com/user")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("User-Agent", "JARVIS-MCP-Client")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                username = data.get("login", "")
                self._github_username_cache = username
                if username:
                    print(f"[MCP GITHUB] Authenticated user: {username}")
                return username
        except Exception as e:
            print(f"[MCP GITHUB] Warning: Failed to resolve GitHub username: {e}")
            self._github_username_cache = ""
            return ""
        
    async def get_all_gemini_tools(self, close_after: bool = False) -> List[Dict[str, Any]]:
        """Fetch tools from all configured servers and convert them to Gemini format."""
        if self._gemini_tools_cache:
            return self._gemini_tools_cache
            
        gemini_tools = []
        for server_name in self.config.get("mcpServers", {}):
            tag = f"MCP {server_name.upper().replace('_', ' ')}"
            try:
                client = await self.init_client(server_name)
                tools = await client.get_tools()
                
                github_username = ""
                if server_name == "github":
                    github_username = self._resolve_github_username()
                    
                server_tool_count = 0
                for tool in tools:
                    self._tool_to_server[tool.name] = server_name
                    desc = tool.description or f"MCP tool {tool.name}"
                    
                    if server_name == "github" and github_username:
                        context = (
                            f"[CRITICAL GITHUB IDENTITY RULE: The user's name is Sahil, BUT their GitHub username is NOT 'Sahil'. "
                            f"The authenticated GitHub account username is '{github_username}'. "
                            f"When the user refers to 'my repositories', 'my repos', 'my issues', 'my PRs', or 'my commits', "
                            f"you MUST use '{github_username}' for 'owner' or 'user:{github_username}' in search queries. "
                            f"Do NOT use 'user:Sahil' or owner 'Sahil' unless the user explicitly asks for a GitHub user named Sahil.] "
                        )
                        desc = context + desc
                        
                    gemini_tool = {
                        "name": tool.name,
                        "description": desc,
                    }
                    if hasattr(tool, "inputSchema") and tool.inputSchema:
                        gemini_params = convert_to_gemini_schema(tool.inputSchema)
                        if server_name == "github" and github_username and isinstance(gemini_params, dict):
                            props = gemini_params.get("properties", {})
                            if "query" in props and isinstance(props["query"], dict):
                                props["query"]["description"] = (
                                    f"Search query (GitHub search syntax). For 'my repos', set query to 'user:{github_username}'. "
                                    f"Do NOT use 'user:Sahil' unless user explicitly asks for GitHub user 'Sahil'."
                                )
                            if "owner" in props and isinstance(props["owner"], dict):
                                props["owner"]["description"] = (
                                    f"Repository owner. For 'my repository', set owner to '{github_username}'. "
                                    f"Do NOT use 'Sahil' unless user explicitly asks for GitHub user 'Sahil'."
                                )
                        gemini_tool["parameters"] = gemini_params
                    gemini_tools.append(gemini_tool)
                    server_tool_count += 1
                    
                print(f"[{tag}] Discovered {server_tool_count} tools")
                if close_after:
                    await client.cleanup()
                    self.clients.pop(server_name, None)
            except Exception as e:
                if server_name == "playwright":
                    print(f"[MCP PLAYWRIGHT] WARNING: Failed to start Playwright MCP — JARVIS will continue without browser control.")
                    print(f"[MCP PLAYWRIGHT] Error: {e}")
                elif server_name == "sqlite":
                    print(f"[MCP SQLITE] WARNING: Failed to start SQLite MCP — JARVIS will continue without SQLite database tools.")
                    print(f"[MCP SQLITE] Error: {e}")
                elif server_name == "google_drive":
                    print(f"[MCP GOOGLE DRIVE] WARNING: Failed to start Google Drive MCP — JARVIS will continue without Google Drive tools.")
                    print(f"[MCP GOOGLE DRIVE] Error: {e}")
                else:
                    print(f"[MCP] Error loading tools from {server_name}: {e}")
                
        self._gemini_tools_cache = gemini_tools
        return gemini_tools
        
    async def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool by searching across connected clients."""
        target_servers = []
        if tool_name in self._tool_to_server:
            target_servers = [self._tool_to_server[tool_name]]
        else:
            target_servers = list(self.config.get("mcpServers", {}).keys())

        for server_name in target_servers:
            client = None
            try:
                client = await self.init_client(server_name)
                tools = await client.get_tools()
            except Exception:
                continue  # Skip servers that cannot be initialized

            if any(t.name == tool_name for t in tools):
                if tool_name == "search_files" and server_name == "filesystem" and "query" in arguments and "path" not in arguments:
                    continue  # Discard filesystem match in favor of Google Drive search_files when using 'query'
                try:
                    if server_name == "github":
                        auth_user = self._resolve_github_username()
                        if auth_user:
                            # 1. Sanitize 'owner' parameter if it refers to Sahil/me/my/self/empty
                            if "owner" in arguments:
                                o = str(arguments["owner"]).strip()
                                if o.lower() in ("sahil", "me", "my", "self", "authenticated", ""):
                                    arguments["owner"] = auth_user

                            # 2. Sanitize 'query' parameter in search tools if it refers to user:Sahil
                            if "query" in arguments and isinstance(arguments["query"], str):
                                q = arguments["query"].strip()
                                import re
                                if re.search(r'\b(user|owner):\s*sahil\b', q, re.IGNORECASE):
                                    q = re.sub(r'\b(user|owner):\s*sahil\b', f'\\1:{auth_user}', q, flags=re.IGNORECASE)
                                    arguments["query"] = q
                                elif q.lower() in ("sahil", "me", "my", "my repos", "my repositories"):
                                    arguments["query"] = f"user:{auth_user}"

                    if server_name == "filesystem":
                        from mcp_client.filesystem_security import (
                            get_filesystem_security_manager,
                            RISK_SAFE, RISK_CONFIRMATION_REQUIRED, RISK_BLOCKED, AuditLogger
                        )
                        sec_mgr = get_filesystem_security_manager()
                        risk_level, prompt_msg, path_summary = sec_mgr.evaluate_operation(tool_name, arguments)
                        safe_prompt = prompt_msg or f"Security prompt for '{tool_name}' on '{path_summary}'"

                        if risk_level == RISK_BLOCKED:
                            print(f"[SECURITY BLOCK] Prevented execution of '{tool_name}' on '{path_summary}'")
                            self._emit_event("mcp_tool_error", tool_name, {"error": safe_prompt, "server": server_name})
                            return safe_prompt

                        if risk_level == RISK_CONFIRMATION_REQUIRED:
                            user_confirmed = arguments.get("user_confirmed") or arguments.get("confirmed") or False
                            if not user_confirmed:
                                sec_mgr.set_pending_confirmation(tool_name, arguments, safe_prompt)
                                AuditLogger.log_event(
                                    tool_name,
                                    arguments.get("path") or arguments.get("directory") or "",
                                    arguments.get("destination") or "",
                                    RISK_CONFIRMATION_REQUIRED,
                                    True,
                                    "AWAITING_CONFIRMATION",
                                    "PENDING"
                                )
                                print(f"[SECURITY] Confirmation required for '{tool_name}' on '{path_summary}'")
                                return safe_prompt

                    print(f"[JARVIS] Tool: {tool_name}")
                    print(f"[JARVIS] [TOOL] {tool_name} {arguments}")
                    self._emit_event("mcp_tool_started", tool_name, {"arguments": arguments, "server": server_name})
                    result = await client.execute_tool(tool_name, arguments)

                    if server_name == "filesystem":
                        from mcp_client.filesystem_security import get_filesystem_security_manager, AuditLogger, RISK_CONFIRMATION_REQUIRED
                        sec_mgr = get_filesystem_security_manager()
                        conf_res = "APPROVED" if (arguments.get("user_confirmed") or arguments.get("confirmed")) else "NOT_REQUIRED"
                        AuditLogger.log_event(
                            tool_name,
                            arguments.get("path") or arguments.get("directory") or "",
                            arguments.get("destination") or "",
                            "SAFE" if conf_res == "NOT_REQUIRED" else RISK_CONFIRMATION_REQUIRED,
                            conf_res == "APPROVED",
                            conf_res,
                            "ERROR" if result.isError else "SUCCESS"
                        )
                        if sec_mgr.pending_confirmation and conf_res == "APPROVED":
                            sec_mgr.clear_pending_confirmation()

                    if result.isError:
                        err_text = f"Error from MCP {server_name}: {result.content}"
                        self._emit_event("mcp_tool_error", tool_name, {"error": err_text, "server": server_name})
                        return err_text
                    
                    # Extract text content
                    text_parts = []
                    for content in result.content:
                        if content.type == "text":
                            text_parts.append(content.text)
                    out_text = "\n".join(text_parts) if text_parts else "Done (No output)."
                    
                    # Truncate oversized MCP results to prevent Gemini Live WebSocket crash
                    MCP_MAX_RESULT = 25000
                    if len(out_text) > MCP_MAX_RESULT:
                        print(f"[MCP] [WARN] Tool '{tool_name}' result truncated: {len(out_text)} -> {MCP_MAX_RESULT} chars")
                        out_text = out_text[:MCP_MAX_RESULT] + "\n\n[OUTPUT TRUNCATED - result too large. Ask the user to narrow the scope.]"
                    
                    self._emit_event("mcp_tool_result", tool_name, {"result": out_text, "server": server_name})
                    return out_text
                except Exception as e:
                    print(f"Error executing tool {tool_name} on MCP server {server_name}: {e}")
                    if client and server_name != "google_drive":
                        await client.cleanup()
                        self.clients.pop(server_name, None)
                    self._emit_event("mcp_tool_error", tool_name, {"error": str(e), "server": server_name})
                    return f"Error executing tool {tool_name}: {e}"
                
        err_msg = f"Unknown MCP tool: {tool_name}"
        self._emit_event("mcp_tool_error", tool_name, {"error": err_msg, "server": "unknown"})
        return err_msg

    async def cleanup(self):
        """Cleanup all clients."""
        for client in self.clients.values():
            try:
                await client.cleanup()
            except BaseException:
                pass
        self.clients.clear()

# Global manager instance for JARVIS integration
_global_manager = None

def get_mcp_manager() -> MCPManager:
    global _global_manager
    if _global_manager is None:
        config_file = Path(__file__).parent / "config.json"
        _global_manager = MCPManager(str(config_file))
    return _global_manager

async def setup_mcp_integration():
    """Initializes connections and returns the list of Gemini-formatted tools."""
    manager = get_mcp_manager()
    return await manager.get_all_gemini_tools(close_after=True)

async def execute_mcp_tool(name: str, arguments: dict) -> str:
    """Executes an MCP tool."""
    manager = get_mcp_manager()
    return await manager.execute_tool(name, arguments)

async def test_filesystem_server():
    """Test the filesystem MCP server by connecting and running list_directory."""
    print("Initializing filesystem MCP server...")
    try:
        tools = await setup_mcp_integration()
        print(f"Discovered {len(tools)} tools.")
        for tool in tools:
            print(f"- {tool['name']}: {tool.get('description', '')}")
            
        test_dir = "C:\\Projects\\Jarvis"
        print(f"\nTesting list_allowed_directories (or list_directory) for {test_dir}...")
        
        res = await execute_mcp_tool("list_allowed_directories", {})
        print(f"Result for list_allowed_directories: {res}")
            
        res = await execute_mcp_tool("list_directory", {"path": test_dir})
        print(f"Result for list_directory: {res}")
            
    finally:
        print("\nCleaning up connections...")
        await get_mcp_manager().cleanup()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(test_filesystem_server())
