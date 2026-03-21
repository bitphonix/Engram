# Engram Setup Guide

Complete setup from zero to running in ~15 minutes.

---

## Step 1 — Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/engram
cd engram
python -m venv venv && source venv/bin/activate
pip install -e .
```

---

## Step 2 — Get a Gemini API key (free)

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API key** → **Create API key**
3. Copy the key — looks like `AIzaSy...`

---

## Step 3 — Create a Neo4j AuraDB database (free)

1. Go to [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
2. Sign up for a free account
3. Click **New Instance** → select **AuraDB Free**
4. Name it `engram`, select any region, click **Create**
5. **Important:** A credentials file downloads automatically — save it, you need it
6. Wait 2-3 minutes for the instance to become **Running**
7. From the downloaded credentials file, copy:
   - `NEO4J_URI` — looks like `neo4j+s://xxxxxxxx.databases.neo4j.io`
   - `NEO4J_USERNAME` — usually `neo4j`
   - `NEO4J_PASSWORD` — long random string

---

## Step 4 — Configure secrets

**Option A — `.env` file (simplest):**

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_from_credentials_file
GEMINI_API_KEY=AIzaSy...
```

Leave the other fields empty for now — they're optional.

**Option B — Doppler (recommended for teams):**

```bash
doppler setup   # select project: engram, config: development
doppler secrets set NEO4J_URI NEO4J_USER NEO4J_PASSWORD GEMINI_API_KEY
```

---

## Step 5 — Start Engram

```bash
engram start
```

You should see:
```
→ Starting Engram on port 8000…
✓ Engram is running  →  http://localhost:8000
✓ Open dashboard     →  http://localhost:8000
```

Open [http://localhost:8000](http://localhost:8000) — you should see the Engram dashboard.

---

## Step 6 — Install MCP integrations

```bash
engram install
```

This configures Claude Code, Cursor, and VS Code to use Engram automatically. It also injects auto-capture instructions into `~/.claude/CLAUDE.md`.

Restart your AI tool after running this.

---

## Step 7 — Ingest your first session

**Option A — From the dashboard:**
1. Open [http://localhost:8000](http://localhost:8000)
2. Paste any AI conversation into the Ingest Session tab
3. Click **Ingest →**

**Option B — From the CLI:**
```bash
cat my_conversation.txt | engram capture --project my-first-project
```

**Option C — From Claude Code / Cursor (after `engram install`):**
Just ask: `"Capture this session to Engram"` — it saves automatically.

---

## Step 8 — Search your history

```bash
engram search "database decisions"
```

Or open the dashboard → Retrieve Context tab.

---

## Step 9 — Install as a system service (auto-starts on login)

```bash
engram service install
```

Now Engram starts automatically every time you log in. No need to run `engram start` manually.

---

## Verify everything is working

```bash
engram status
```

Should show:
```
✓ Server running (managed by launchd)  →  http://localhost:8000

Knowledge Graph
  Active decisions    0
  Counterfactuals     0
  Sessions            0
  Avg weight          0.000
```

---

## Troubleshooting

**`NEO4J_URI and NEO4J_PASSWORD required` error:**
- Check your `.env` file exists and has the correct values
- Make sure you're running from the `engram` directory

**`Connection refused` when starting:**
- Another process is using port 8000
- Run: `lsof -i :8000` to find it, then kill it

**`Embedding failed` during ingest:**
- Check your `GEMINI_API_KEY` is correct
- Verify at: `curl "https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY"`

**Neo4j connection drops on network change:**
- This is normal — the connection re-establishes automatically
- If ingests fail, run `engram retry` to process queued items

**MCP not working in Cursor or VS Code:**
- Make sure Engram server is running: `engram status`
- Restart the AI tool after `engram install`
- Check the config was written: `cat ~/.cursor/mcp.json`

---

## Optional: Sentry error tracking

1. Create a free account at [sentry.io](https://sentry.io)
2. Create a new project → Python
3. Copy the DSN
4. Add to `.env`: `SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx`

---

## What's next

- Read the [README](README.md) for architecture details
- Check `app/mcp/SETUP.md` for MCP configuration options
- Run `engram --help` to see all CLI commands