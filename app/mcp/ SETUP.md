# Engram MCP Server Setup

The MCP server lets Claude Code, Cursor, and VS Code automatically capture
sessions and retrieve context — no manual pasting required.

## How it works

The AI tool spawns the MCP server as a subprocess on startup.
During your session, you can ask:

- "Capture this session to Engram" → calls `engram_capture`
- "What does Engram know about database choices?" → calls `engram_context`
- "Have I rejected Kafka before?" → calls `engram_warn`
- "Show my Engram graph stats" → calls `engram_stats`

## Prerequisites

1. Engram server must be running:
   ```bash
   doppler run -- uvicorn app.main:app --reload
   ```

2. Use your venv Python path in all configs below:
   ```bash
   which python   # run inside activated venv
   # e.g. /Users/yourname/Documents/Engram/venv/bin/python
   ```

---

## Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "engram": {
      "command": "/absolute/path/to/engram/venv/bin/python",
      "args": ["/absolute/path/to/engram/app/mcp/server.py"],
      "env": {
        "ENGRAM_API_URL": "http://localhost:8000",
        "PYTHONPATH": "/absolute/path/to/engram"
      }
    }
  }
}
```

Start Claude Code in any directory:
```bash
claude
```

---

## Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "engram": {
      "command": "/absolute/path/to/engram/venv/bin/python",
      "args": ["/absolute/path/to/engram/app/mcp/server.py"],
      "env": {
        "ENGRAM_API_URL": "http://localhost:8000",
        "PYTHONPATH": "/absolute/path/to/engram"
      }
    }
  }
}
```

Restart Cursor. Engram tools appear automatically in Cursor chat.

---

## VS Code (GitHub Copilot)

Requires VS Code 1.99+ with GitHub Copilot. MCP runs in **Agent mode**.

Create `.vscode/mcp.json` in your project root:

```json
{
  "servers": {
    "engram": {
      "command": "/absolute/path/to/engram/venv/bin/python",
      "args": ["/absolute/path/to/engram/app/mcp/server.py"],
      "env": {
        "ENGRAM_API_URL": "http://localhost:8000",
        "PYTHONPATH": "/absolute/path/to/engram"
      }
    }
  }
}
```

Note: VS Code uses `"servers"` as the top-level key — not `"mcpServers"`.

Open Copilot Chat → switch to **Agent** mode → Engram tools are available.

---

## Global vs per-project installation

**Per-project** — place config in `.vscode/mcp.json`, `.cursor/mcp.json`,
or `.claude/settings.json` inside the project folder. Engram only runs
for that project.

**Global** (recommended) — place config in the home directory files above.
Engram captures decisions from every project you work on automatically.

---

## When Engram is deployed (not local)

Update `ENGRAM_API_URL` in any config to your deployed URL:

```json
"env": {
  "ENGRAM_API_URL": "https://engram-xxxxx.ondigitalocean.app",
  "PYTHONPATH": "/absolute/path/to/engram"
}
```

Now Engram works from anywhere — not just when your local server is running.

---

## Verify it's working

In any AI tool chat (Agent mode for VS Code), type:

```
Show my Engram graph stats
```

You should see live knowledge graph stats pulled from Neo4j immediately.

---

## Example session workflow

**Start of session:**
> "Check Engram for context on database decisions"
→ 4-level causal retrieval with counterfactual warnings

**End of session:**
> "Capture this session to Engram for project my-api"
→ Decisions and counterfactuals saved to knowledge graph

**Before making a decision:**
> "Have I rejected GraphQL before?"
→ Past rejection reasons surfaced with project context