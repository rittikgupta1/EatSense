import json
import os
import shutil
from typing import Dict, Any, List, Optional

import anyio
import httpx

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

def _load_mcp_config(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

def _mock_results(dish: str) -> List[Dict[str, Any]]:
    return [
        {"name": f"{dish} Express", "price": "₹220", "eta_minutes": 30},
        {"name": f"Classic {dish}", "price": "₹260", "eta_minutes": 35},
        {"name": f"Street {dish}", "price": "₹180", "eta_minutes": 25},
    ]

async def _call_mcp_server(server_name: str, server_config: Dict[str, Any], dish: str) -> Optional[Dict[str, Any]]:
    """Helper to connect to an MCP server and call a commerce tool."""
    try:
        preferred_tool = os.getenv("SWIGGY_MCP_TOOL_NAME", "").strip()
        query_param = os.getenv("SWIGGY_MCP_QUERY_PARAM", "query").strip() or "query"
        if server_config.get("type") == "http":
            headers = {}
            auth_header = os.getenv("SWIGGY_MCP_AUTH_HEADER", "").strip()
            auth_token = os.getenv("SWIGGY_MCP_AUTH_TOKEN", "").strip()
            if auth_header and auth_token:
                headers[auth_header] = auth_token
            client = httpx.AsyncClient(headers=headers) if headers else None
            async with streamable_http_client(server_config["url"], http_client=client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    search_tool = None
                    if preferred_tool:
                        search_tool = next((t for t in tools.tools if t.name == preferred_tool), None)
                    if not search_tool:
                        search_tool = next((t for t in tools.tools if "search" in t.name or "list" in t.name), None)
                    if search_tool:
                        result = await session.call_tool(search_tool.name, arguments={query_param: dish})
                        return {"status": "available", "results": result.content, "source": server_name}

        elif "command" in server_config:
            command = server_config["command"]
            if not shutil.which(command):
                raise FileNotFoundError(command)
            params = StdioServerParameters(
                command=command,
                args=server_config.get("args", []),
                env={**os.environ, **server_config.get("env", {})}
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    search_tool = None
                    if preferred_tool:
                        search_tool = next((t for t in tools.tools if t.name == preferred_tool), None)
                    if not search_tool:
                        search_tool = next((t for t in tools.tools if "search" in t.name or "list" in t.name), None)
                    if search_tool:
                        result = await session.call_tool(search_tool.name, arguments={query_param: dish})
                        
                        # Process results into a standard format
                        processed_results = []
                        for item in result.content:
                            if item.type == 'text':
                                try:
                                    # Try to parse as JSON if the tool returns a JSON string
                                    data = json.loads(item.text)
                                    if isinstance(data, list):
                                        processed_results.extend(data)
                                    else:
                                        processed_results.append(data)
                                except json.JSONDecodeError:
                                    # If not JSON, just add the raw text as a name
                                    processed_results.append({"name": item.text, "price": "N/A", "eta_minutes": "N/A"})
                        
                        return {
                            "status": "available", 
                            "results": processed_results, 
                            "source": server_name
                        }
    except Exception as e:
        print(f"Error calling MCP server {server_name}: {e}")
    return None

def commerce_lookup(dish: str) -> Dict[str, Any]:
    enabled = os.getenv("SWIGGY_MCP_ENABLED", "false").lower() == "true"
    if not enabled:
        return {
            "agent": "CommerceAgent",
            "status": "disabled",
            "message": "Commerce lookup is disabled. Set SWIGGY_MCP_ENABLED=true to try it.",
        }

    config_path = os.getenv("SWIGGY_MCP_CONFIG", "./mcp.json")
    config = _load_mcp_config(config_path)
    servers = config.get("mcpServers", {})

    if not servers:
        return {
            "agent": "CommerceAgent",
            "status": "unavailable",
            "message": "No MCP servers configured.",
        }

    # Attempt to call Swiggy-specific servers
    for name in ["swiggy-food", "swiggy"]:
        if name in servers:
            try:
                # Use anyio to run the async call in a synchronous context (for Streamlit/Pipeline)
                mcp_result = anyio.run(_call_mcp_server, name, servers[name], dish)
                if mcp_result:
                    return {
                        "agent": "CommerceAgent",
                        "status": mcp_result["status"],
                        "results": mcp_result["results"],
                        "source": mcp_result["source"],
                    }
            except Exception:
                continue

    # Fallback to mock if real MCP fails or no tool found
    return {
        "agent": "CommerceAgent",
        "status": "mock",
        "results": _mock_results(dish),
        "quote": {
            "items": [dish],
            "estimated_total": "₹260",
        },
        "note": "Mock results shown. MCP connection attempts failed or no search tool found.",
    }
