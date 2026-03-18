# Engram MCP Server Setup

The MCP server lets Claude Code automatically capture sessions and retrieve
context — no manual pasting required.

## How it works

Claude Code spawns the MCP server as a subprocess on startup.
During your session, you can ask Claude to:

- "Capture this session to Engram" → calls `engram_capture`
- "What does Engram know about database choices?" → calls `engram_context`
- "Have I rejected PostgreSQL before?" → calls `engram_warn`
- "Show my Engram graph stats" → calls `engram_stats`

Claude Code calls these tools automatically when you ask — no setup per session.

## Prerequisites

1. Engram server must be running locally:
   ```bash
   doppler run -- uvicorn app.main:app --reload
   ```

2. Install httpx in your venv (already in requirements.txt):
   ```bash
   pip install httpx
   ```

## Installation — Option A: Per Project (recommended for development)

Place `.claude/settings.json` in your project root:

```json
{
  "mcpServers": {
    "engram": {
      "command": "python",
      "args": ["/absolute/path/to/engram/app/mcp/server.py"],
      "env": {
        "ENGRAM_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Replace `/absolute/path/to/engram` with your actual path, e.g.:
`/Users/yourname/Documents/engram`

## Installation — Option B: Global (Engram works in ALL your projects)

```bash
# Find Claude Code's global config location
# macOS: ~/.claude/settings.json
# Linux: ~/.config/claude/settings.json

mkdir -p ~/.claude
cat > ~/.claude/settings.json << 'EOF'
{
  "mcpServers": {
    "engram": {
      "command": "python",
      "args": ["/absolute/path/to/engram/app/mcp/server.py"],
      "env": {
        "ENGRAM_API_URL": "http://localhost:8000"
      }
    }
  }
}
EOF
```

Global installation is the power move — Engram captures decisions from
every project you work on automatically.

## Verify it's working

Start Claude Code in any project directory:
```bash
claude
```

Then ask:
```
Show my Engram graph stats
```

You should see your knowledge graph stats returned immediately.

## When the Engram server is deployed (not local)

Update ENGRAM_API_URL to your DigitalOcean URL:
```json
"env": {
  "ENGRAM_API_URL": "https://engram-xxxxx.ondigitalocean.app"
}
```

Now Engram works from anywhere — not just when your local server is running.

## Example session workflow

### Start of session:
Ask Claude: "Check Engram for context on authentication decisions"
→ Claude calls `engram_context` and injects your decision history

### End of session:
Ask Claude: "Capture this session to Engram for project auth-service"
→ Claude calls `engram_capture` with the conversation
→ Decisions and counterfactuals saved to your knowledge graph

### Before making a decision:
Ask Claude: "Has Engram seen us reject GraphQL before?"
→ Claude calls `engram_warn` and surfaces past rejection reasons