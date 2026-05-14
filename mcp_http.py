from typing import Any

from agent import SelfHealingAgent

APP_VERSION = "0.2.10"
APP_AUTHOR = "Starace Giuseppe"

TOOLS = [
    {
        "name": "ha_self_healer_status",
        "description": "Restituisce stato dell'agente self-healing.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ha_check_logs",
        "description": "Legge i log Home Assistant e restituisce nuovi errori non ancora trattati.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ha_run_self_healing",
        "description": "Esegue un ciclo di diagnosi e remediation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notify": {"type": "boolean", "default": True},
            },
        },
    },
]


def handle_mcp(agent: SelfHealingAgent, request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method")
    request_id = request.get("id")
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ha-mcp-self-healer", "version": APP_VERSION, "author": APP_AUTHOR},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = request.get("params") or {}
            result = _call_tool(agent, params.get("name"), params.get("arguments") or {})
        else:
            return _error(request_id, -32601, f"Metodo MCP non supportato: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return _error(request_id, -32000, str(exc))


def _call_tool(agent: SelfHealingAgent, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "ha_self_healer_status":
        data = agent.status()
    elif name == "ha_check_logs":
        data = [issue.model_dump(mode="json") for issue in agent.check_logs()]
    elif name == "ha_run_self_healing":
        report = agent.run_once(notify=bool(arguments.get("notify", True)))
        data = report.model_dump(mode="json")
    else:
        raise ValueError(f"Tool sconosciuto: {name}")

    return {
        "content": [
            {
                "type": "text",
                "text": _to_text(data),
            }
        ],
        "structuredContent": data,
    }


def _to_text(data: Any) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
