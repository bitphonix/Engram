"""
Engram — MCP Server.

Runs as a standalone process. Claude Code spawns it via stdio.
Exposes 4 tools that Claude Code calls automatically during sessions.

Tools:
  engram_capture    → ingest session content into the knowledge graph
  engram_context    → retrieve relevant past decisions before starting work
  engram_warn       → surface counterfactual warnings for a specific concern
  engram_stats      → show knowledge graph health

Setup for Claude Code:
  Add to ~/.claude/settings.json:
  {
    "mcpServers": {
      "engram": {
        "command": "python",
        "args": ["/path/to/engram/app/mcp/server.py"],
        "env": {
          "ENGRAM_API_URL": "http://localhost:8000"
        }
      }
    }
  }

The MCP server talks to the Engram FastAPI backend via HTTP.
This means the backend can be local OR remote (deployed on DigitalOcean).
"""
import sys
import os
import json
import asyncio
import httpx
from typing import Any

# MCP protocol constants
JSONRPC_VERSION = "2.0"
MCP_VERSION     = "2024-11-05"

# Engram API base URL — defaults to local, overridable via env
API_URL = os.getenv("ENGRAM_API_URL", "http://localhost:8000")


# ── MCP Tool definitions ───────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "engram_capture",
        "description": (
            "Capture this conversation or a summary of work done into Engram's "
            "knowledge graph. Call this at the END of a session to save decisions "
            "and rejected alternatives. Engram extracts atomic decisions and their "
            "counterfactuals automatically — just pass the conversation or a "
            "summary of what was decided and why."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The conversation text or session summary to capture. Include decisions made and alternatives considered."
                },
                "project": {
                    "type": "string",
                    "description": "Project name or identifier (e.g., 'my-saas-app', 'ml-pipeline'). Used to link related sessions."
                },
                "tool": {
                    "type": "string",
                    "description": "Which AI tool was used (claude, chatgpt, gemini, cursor). Defaults to 'claude'.",
                    "default": "claude"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "engram_context",
        "description": (
            "Retrieve relevant past decisions and counterfactual warnings before "
            "starting work on a new problem. Call this at the START of a session "
            "when you know what domain you're working in. Returns a ready-to-use "
            "context briefing based on your decision history."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What you're about to work on or decide (e.g., 'choosing a database for high-throughput writes', 'setting up authentication for B2B SaaS')."
                },
                "domain": {
                    "type": "string",
                    "description": "Optional domain hint. One of: database, architecture, api_design, authentication, infrastructure, framework, deployment, security, performance, other."
                },
                "concerns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of concerns relevant to your decision. E.g. ['cost', 'scalability', 'vendor_lock_in']. Triggers counterfactual warnings."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "engram_warn",
        "description": (
            "Surface counterfactual warnings for a specific option you're considering. "
            "Use this when you're about to choose something and want to know if "
            "you've rejected it before and why. Returns past rejection reasons "
            "across all your projects."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "option": {
                    "type": "string",
                    "description": "The specific technology or approach you're considering (e.g., 'MongoDB', 'microservices', 'GraphQL')."
                },
                "concern": {
                    "type": "string",
                    "description": "The concern you have about this option. One of: scalability, complexity, cost, team_expertise, performance, maintenance_burden, security, vendor_lock_in, latency, consistency."
                }
            },
            "required": ["option"]
        }
    },
    {
        "name": "engram_stats",
        "description": (
            "Show the current state of your Engram knowledge graph — "
            "how many decisions, counterfactuals, and sessions are stored, "
            "and the average epistemic weight of your decision history."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# ── API calls to Engram backend ────────────────────────────────────────────────

async def call_engram_capture(content: str, project: str = None, tool: str = "claude") -> str:
    payload = {
        "content":      content,
        "tool":         tool,
        "captured_via": "mcp",
        "project_id":   project,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{API_URL}/ingest", json=payload)
        resp.raise_for_status()
        data = resp.json()

    if data.get("error"):
        return f"⚠ Engram: Captured with error — {data['error']}"

    if not data.get("is_high_signal"):
        return "Engram: Low signal content — no decisions detected worth storing."

    lines = [
        f"✓ Engram captured to knowledge graph:",
        f"  • {data['saved_decisions']} decision(s) saved",
        f"  • {data['saved_counterfactuals']} counterfactual(s) saved",
        f"  • Domain: {data.get('domain_primary', 'unknown')}",
        f"  • Critique score: {data.get('critique_score', '?')}/10",
    ]
    if data.get("session_summary"):
        lines.append(f"  • Summary: {data['session_summary']}")

    return "\n".join(lines)


async def call_engram_context(query: str, domain: str = None,
                               concerns: list = None) -> str:
    payload = {
        "query":    query,
        "domain":   domain,
        "concerns": concerns or [],
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{API_URL}/context", json=payload)
        resp.raise_for_status()
        data = resp.json()

    decisions_found = data.get("decisions_found", 0)
    warnings_found  = data.get("warnings_found", 0)

    if decisions_found == 0 and warnings_found == 0:
        return "Engram: No relevant past decisions found for this query. This appears to be a new domain for you."

    briefing = data.get("briefing", "")
    lines = [
        f"Engram context ({decisions_found} past decisions, {warnings_found} warnings):",
        "",
        briefing,
    ]
    return "\n".join(lines)


async def call_engram_warn(option: str, concern: str = None) -> str:
    concerns = [concern] if concern else [
        "scalability", "complexity", "cost", "performance",
        "maintenance_burden", "vendor_lock_in"
    ]
    payload = {"query": f"considering {option}", "concerns": concerns}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{API_URL}/context", json=payload)
        resp.raise_for_status()
        data = resp.json()

    warnings = data.get("counterfactual_warnings", [])
    relevant = [
        w for w in warnings
        if option.lower() in w.get("counterfactual", {}).get("rejected_option", "").lower()
    ]

    if not relevant:
        return f"Engram: No past rejections of '{option}' found in your history."

    lines = [f"⚠ Engram: You've rejected '{option}' before:"]
    for w in relevant:
        cf = w.get("counterfactual", {})
        lines.append(
            f"  • Project: {w.get('session', {}).get('project_id', 'unknown')}"
        )
        lines.append(f"    Reason: {cf.get('rejection_reason', '')}")
        lines.append(f"    Concern: {cf.get('rejection_concern', '')}")
    return "\n".join(lines)


async def call_engram_stats() -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{API_URL}/graph/stats")
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        return f"Engram: Stats unavailable — {data['error']}"

    return (
        f"Engram knowledge graph:\n"
        f"  • Active decisions:      {data.get('active_decisions', 0)}\n"
        f"  • Total counterfactuals: {data.get('total_counterfactuals', 0)}\n"
        f"  • Total sessions:        {data.get('total_sessions', 0)}\n"
        f"  • Avg epistemic weight:  {data.get('avg_epistemic_weight', 0):.3f}"
    )


# ── MCP protocol handler ───────────────────────────────────────────────────────

def send(obj: dict):
    """Write a JSON-RPC message to stdout."""
    line = json.dumps(obj) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()


def make_response(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def make_error(request_id: Any, code: int, message: str) -> dict:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message}
    }


async def handle_request(request: dict) -> dict | None:
    method     = request.get("method")
    request_id = request.get("id")
    params     = request.get("params", {})

    # ── Initialization ─────────────────────────────────────────────────────
    if method == "initialize":
        return make_response(request_id, {
            "protocolVersion": MCP_VERSION,
            "capabilities":    {"tools": {}},
            "serverInfo":      {"name": "engram", "version": "0.1.0"}
        })

    if method == "notifications/initialized":
        return None  # notification, no response needed

    # ── Tool listing ───────────────────────────────────────────────────────
    if method == "tools/list":
        return make_response(request_id, {"tools": TOOLS})

    # ── Tool execution ─────────────────────────────────────────────────────
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "engram_capture":
                text = await call_engram_capture(
                    content=arguments.get("content", ""),
                    project=arguments.get("project"),
                    tool=arguments.get("tool", "claude"),
                )
            elif tool_name == "engram_context":
                text = await call_engram_context(
                    query=arguments.get("query", ""),
                    domain=arguments.get("domain"),
                    concerns=arguments.get("concerns"),
                )
            elif tool_name == "engram_warn":
                text = await call_engram_warn(
                    option=arguments.get("option", ""),
                    concern=arguments.get("concern"),
                )
            elif tool_name == "engram_stats":
                text = await call_engram_stats()
            else:
                return make_error(request_id, -32601, f"Unknown tool: {tool_name}")

            return make_response(request_id, {
                "content": [{"type": "text", "text": text}]
            })

        except httpx.ConnectError:
            return make_response(request_id, {
                "content": [{
                    "type": "text",
                    "text": (
                        f"⚠ Engram: Cannot connect to {API_URL}. "
                        "Is the Engram server running? "
                        "Start it with: doppler run -- uvicorn app.main:app --reload"
                    )
                }]
            })
        except Exception as e:
            return make_response(request_id, {
                "content": [{"type": "text", "text": f"⚠ Engram error: {str(e)}"}]
            })

    return make_error(request_id, -32601, f"Method not found: {method}")


async def main():
    """
    Main stdio loop. Reads JSON-RPC messages from stdin, processes them,
    writes responses to stdout. Claude Code communicates via this protocol.
    """
    loop = asyncio.get_event_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break  # stdin closed — Claude Code session ended

            line = line.strip()
            if not line:
                continue

            request = json.loads(line)
            response = await handle_request(request)

            if response is not None:
                send(response)

        except json.JSONDecodeError:
            send(make_error(None, -32700, "Parse error"))
        except KeyboardInterrupt:
            break
        except Exception as e:
            send(make_error(None, -32603, f"Internal error: {str(e)}"))


if __name__ == "__main__":
    asyncio.run(main())