import asyncio
import traceback
from mcp_client.manager import get_mcp_manager

async def test_mcp():
    manager = get_mcp_manager()
    
    servers = manager.config.get("mcpServers", {})
    results = []
    
    for server_name in servers.keys():
        print(f"Testing server: {server_name}")
        status = "FAIL"
        tools_discovered = 0
        try:
            client = await manager.init_client(server_name)
            tools = await client.get_tools()
            tools_discovered = len(tools)
            status = "PASS"
        except Exception as e:
            print(f"Error for {server_name}: {e}")
            traceback.print_exc()
        finally:
            if server_name in manager.clients:
                await manager.clients[server_name].cleanup()
                
        results.append({
            "name": server_name,
            "status": status,
            "tools_discovered": tools_discovered
        })
        
    print("\n--- TEST SUMMARY ---")
    for res in results:
        print(f"{res['name']} MCP: {res['status']}")
        print(f"{res['name']} Tools Discovered: {res['tools_discovered']} tools")

if __name__ == "__main__":
    asyncio.run(test_mcp())
