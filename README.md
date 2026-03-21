# Engram

**Developer decision intelligence — causal memory across AI sessions.**

Most AI memory tools store *what happened*. Engram stores *what was decided, what was rejected, and why* — building a living knowledge graph of your technical judgment that grows smarter every session.

```bash
pip install -e .
engram install   # configure Claude Code, Cursor, VS Code in one command
engram start     # run as background daemon, auto-starts on login
engram search "database for high throughput writes"
```

> Built with LangGraph · Neo4j · ChromaDB · Google Gemini

[![CI](https://github.com/YOUR_USERNAME/engram/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/engram/actions)
[![Tests](https://img.shields.io/badge/tests-64%20passing-2d7a4f)](https://github.com/YOUR_USERNAME/engram/actions)
[![Python](https://img.shields.io/badge/python-3.11-e8650a)](https://python.org)

---

## The problem

Every AI session ends with lost context. You close the chat and the decisions, the dead ends, the reasoning behind every choice — evaporate. You open a new session tomorrow and start over.

Existing solutions only solve half the problem:

| Tool | What it stores | What it misses |
|---|---|---|
| claude-mem | Tool outputs within a session | Rejected alternatives, cross-project patterns |
| mem0 | Facts and preferences | The *why* behind decisions, counterfactuals |
| Chat history | Everything | Signal in the noise, cross-session intelligence |

**Engram stores what no other system does: the roads not taken.**

When you chose PostgreSQL over MongoDB, the *rejection* contains more information than the choice. The concern that drove it, the reasoning, the constraints — that's the intelligence that should survive session boundaries.

---

## Quickstart

```bash
git clone https://github.com/YOUR_USERNAME/engram
cd engram
python -m venv venv && source venv/bin/activate
pip install -e .

# Set secrets (Neo4j AuraDB + Gemini API key)
doppler setup   # or copy .env.example to .env

# One-time setup
engram install  # wires up Claude Code, Cursor, VS Code + auto-capture
engram start    # starts server + installs launchd service (auto-starts on login)
```

Open `http://localhost:8000` for the dashboard.

---

## CLI

```
engram start              Start server as background daemon (auto-restarts on login)
engram stop               Stop the server
engram status             Live server health + knowledge graph stats
engram search <query>     Semantic search over your decision history
engram install            Configure MCP for Claude Code, Cursor, VS Code
engram capture            Capture from stdin (pipe any conversation)
engram delete <id>        Remove a decision from graph + vector store
engram retry              Retry failed ingests from the local queue
engram service install    Install as launchd service (macOS)
engram service uninstall  Remove the launchd service
```

### Examples

```bash
# Search your decision history
engram search "database for high throughput writes"
→ Chose managed ClickHouse over PostgreSQL, Kafka, and BigQuery
  database · analytics_platform · score: 0.714

# Capture any conversation
cat conversation.txt | engram capture --project my-api --tool claude

# Check graph health
engram status
→ Active decisions    36
→ Counterfactuals     54
→ Sessions            13
→ Avg weight          0.643
```

---

## MCP integration — works with Claude Code, Cursor, and VS Code

`engram install` configures all three tools at once. After setup, your AI tools call Engram automatically:

```
# Claude Code, Cursor, or VS Code Copilot (Agent mode)
"Capture this session to Engram"           → saves decisions to graph
"What does Engram know about databases?"   → 4-level causal retrieval
"Have I rejected Kafka before?"            → counterfactual warning
"Show my Engram graph stats"               → live knowledge graph stats
```

Claude Code also captures sessions **automatically** — Engram injects instructions into `~/.claude/CLAUDE.md` so capture happens at session end without prompting.

Config locations:
- Claude Code: `~/.claude/settings.json`
- Cursor:      `~/.cursor/mcp.json`
- VS Code:     `.vscode/mcp.json` (note: uses `"servers"` key, not `"mcpServers"`)

---

## How it works

### The knowledge graph

Every ingested session creates three types of nodes in Neo4j:

**Decision nodes** — one per atomic choice. `summary`, `chosen`, `reasoning`, `domain`, `situation_context`, `epistemic_weight`, `decay_rate`.

**Counterfactual nodes** — every rejected alternative. `rejected_option`, `rejection_reason`, `rejection_concern` (controlled vocabulary). This is the data no other system captures.

**Typed relationship edges** — created automatically by the linker:
- `CAUSED_BY` — new decision explicitly builds on a prior one
- `SUPERSEDES` — newer decision in same domain/project replaces older
- `SIMILAR_TO` — semantically similar decisions across projects

### 4-level causal retrieval

```
Level 1  Semantic search (ChromaDB)
         → decision IDs + summaries ranked by cosine similarity
           works across ALL domains — finds related decisions by meaning

Level 2  Causal ancestry (Neo4j)
         → traverses CAUSED_BY edges upstream
           "what decisions led to this one?"

Level 3  Full episode (Neo4j)
         → decision + all counterfactuals + outcomes
           the complete context for each relevant decision

Level 4  Counterfactual surface
         → "You rejected X in 3 similar situations. Here's why."
           nobody else has this
```

### The epistemic weight engine

Decisions are not equally trustworthy. The weight engine runs asynchronously:

- **Time decay** — `W(t) = W₀ · e^(-λt)` where λ is set per decision type at extraction (0.01 architectural → 0.30 trivial)
- **Override signal** — newer decisions in the same domain/project decay older ones via `SUPERSEDES`
- **Propagation boost** — retrieved and reused decisions gain weight
- **Contradiction detection** — same option chosen in one project, rejected in another → `CONTRADICTS` edge

### Local-first architecture

- Vector embeddings stored locally at `~/.engram/chroma` (ChromaDB) — no cloud dependency, no IP whitelisting
- Failed ingests queued to `~/.engram/queue/` — nothing lost when Gemini is down
- Duplicate detection via content hashing — same session never ingested twice
- Server persists across reboots via launchd (macOS) — runs in the background always

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Capture Layer                                               │
│  MCP Server (Claude Code, Cursor, VS Code)                  │
│  Manual paste · engram capture (stdin)                      │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Extraction Pipeline                              │
│  triage_node → extractor_node → critique_node               │
│       ↑_____________ (reflection loop) _____|               │
│  graph_writer_node → linker → Neo4j + ChromaDB              │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌────────────────────────────┐  ┌──────────────────────────────┐
│  Neo4j AuraDB              │  │  ChromaDB (local)            │
│  Causal knowledge graph    │  │  Vector embeddings           │
│  Decision + CF + edges     │  │  ~/.engram/chroma            │
└──────────────┬─────────────┘  └─────────────┬────────────────┘
               └────────────────┬──────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────┐
│  4-Level Causal Retrieval                                   │
│  L1 semantic → L2 ancestry → L3 episode → L4 counterfactual│
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  Injection Layer                                            │
│  MCP context provider · Session briefing · engram search   │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Agent framework | LangGraph 0.2 | Conditional edges for reflection loop, stateful pipeline |
| LLM | Google Gemini 2.5 Pro/Flash | Pro for extraction quality, Flash for triage/critique |
| Graph database | Neo4j AuraDB | Native graph traversal, causal queries, typed relationships |
| Vector store | ChromaDB (local) | Zero network dependency, works on any wifi |
| API | FastAPI | Async, auto-docs, Pydantic validation |
| CLI | Python argparse | `engram install` wires up all three AI tools at once |
| MCP server | Python stdio | Passive capture from Claude Code, Cursor, VS Code |
| Observability | Datadog APM + Sentry | Full trace per pipeline run, error tracking |
| Secret management | Doppler | Zero `.env` files |

---

## Agentic patterns demonstrated

- **Multi-node LangGraph pipeline** with shared TypedDict state
- **Triage gate** — cheap Flash model decides if content is worth expensive Pro extraction
- **Self-correction / reflection loop** — Critique node scores quality, routes back to extractor on failure
- **Knowledge graph write** — typed Neo4j nodes with causal relationship edges
- **Decision linker** — automatically creates CAUSED_BY, SUPERSEDES, SIMILAR_TO edges
- **Causal graph traversal** — 4-level retrieval agent traverses ancestry
- **Epistemic weight evolution** — async background engine evolves node weights
- **MCP server** — stdio protocol server working across Claude Code, Cursor, VS Code
- **Local-first vector search** — ChromaDB replaces hosted Atlas for zero network dependency
- **Persistent daemon** — launchd service auto-starts on macOS login

---

## Running locally

**Prerequisites:** Python 3.11+, [Doppler CLI](https://docs.doppler.com/docs/install-cli), [Neo4j AuraDB Free](https://neo4j.com/cloud/aura)

```bash
git clone https://github.com/YOUR_USERNAME/engram
cd engram
python -m venv venv && source venv/bin/activate
pip install -e .

# Configure secrets
doppler setup   # select project: engram, config: development
# Required: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, GEMINI_API_KEY

# Start
engram start
engram install

# Open dashboard
open http://localhost:8000
```

### Running tests

```bash
pytest tests/ -v
# 64 tests — queue, vector_client, linker, API endpoints, CLI
```

---

## Roadmap

- [ ] Browser extension — passive capture from Claude.ai, ChatGPT, Gemini web
- [ ] FS watcher — capture from IDE file changes as outcome signal
- [ ] Local SLM triage — replace cloud Flash model with ONNX for zero API cost
- [ ] Outcome feedback loop — git signals update epistemic weights automatically
- [ ] Public graph — opt-in sharing of decision graphs
- [ ] Team sync — shared knowledge graph for engineering teams

---

Built by [Tanishk Soni](https://github.com/bitphonix) · [LinkedIn](https://linkedin.com/in/tanishk-soni-a94077239)