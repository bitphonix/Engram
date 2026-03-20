"""
Engram CLI — developer decision intelligence.

Usage:
    engram start          Start the Engram server (background daemon)
    engram stop           Stop the Engram server
    engram status         Show server health and knowledge graph stats
    engram search <query> Semantic search over your decision history
    engram install        Configure MCP for Claude Code, Cursor, VS Code
    engram capture        Capture from stdin (pipe a conversation)

Examples:
    engram start
    engram status
    engram search "database decisions for high throughput"
    engram install
    cat conversation.txt | engram capture --project my-api
"""
import os
import sys
import json
import time
import signal
import shutil
import argparse
import subprocess
import platform
from pathlib import Path

ENGRAM_DIR      = Path.home() / ".engram"
PID_FILE        = ENGRAM_DIR / "server.pid"
LOG_FILE        = ENGRAM_DIR / "server.log"
CONFIG_FILE     = ENGRAM_DIR / "config.json"
DEFAULT_PORT    = 8000
DEFAULT_API_URL = f"http://localhost:{DEFAULT_PORT}"

GREEN  = "\033[92m"
ORANGE = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg):    print(f"{GREEN}✓{RESET} {msg}")
def warn(msg):  print(f"{ORANGE}⚠{RESET} {msg}")
def err(msg):   print(f"{RED}✗{RESET} {msg}")
def info(msg):  print(f"{BLUE}→{RESET} {msg}")
def dim(msg):   print(f"{DIM}{msg}{RESET}")



def get_engram_root() -> Path:
    """Find the Engram project root — where main.py lives."""
    # Try to find from script location first
    script_dir = Path(__file__).parent.resolve()
    if (script_dir / "app" / "main.py").exists():
        return script_dir
    # Try current directory
    cwd = Path.cwd()
    if (cwd / "app" / "main.py").exists():
        return cwd
    # Try config file
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
        root = Path(config.get("root", ""))
        if (root / "app" / "main.py").exists():
            return root
    raise RuntimeError(
        "Cannot find Engram project root. "
        "Run this command from your Engram directory."
    )


def get_venv_python() -> str:
    """Find the venv Python for this project."""
    root = get_engram_root()
    candidates = [
        root / "venv" / "bin" / "python",
        root / ".venv" / "bin" / "python",
        root / "venv" / "bin" / "python3",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return sys.executable


def get_api_url() -> str:
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
        return config.get("api_url", DEFAULT_API_URL)
    return DEFAULT_API_URL


def is_server_running() -> bool:
    try:
        call_api("/health")
        return True
    except Exception:
        pass
  
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, ValueError):
        PID_FILE.unlink(missing_ok=True)
        return False


def call_api(path: str, method: str = "GET", data: dict = None) -> dict:
    """Make an HTTP call to the Engram API without external dependencies."""
    import urllib.request
    import urllib.error

    url = f"{get_api_url()}{path}"
    headers = {"Content-Type": "application/json"}

    if method == "POST" and data:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    else:
        req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())



def cmd_start(args):
    """Start the Engram server as a background daemon."""
    if is_server_running():
        ok("Engram server is already running.")
        cmd_status(args)
        return

    ENGRAM_DIR.mkdir(exist_ok=True)

    root       = get_engram_root()
    python     = get_venv_python()
    port       = getattr(args, "port", DEFAULT_PORT)

    # Save config
    CONFIG_FILE.write_text(json.dumps({
        "root":    str(root),
        "port":    port,
        "api_url": f"http://localhost:{port}",
    }, indent=2))

    doppler = shutil.which("doppler")
    if doppler:
        cmd = [doppler, "run", "--", python, "-m", "uvicorn",
               "app.main:app", "--host", "0.0.0.0", "--port", str(port)]
    else:
        cmd = [python, "-m", "uvicorn",
               "app.main:app", "--host", "0.0.0.0", "--port", str(port)]

    info(f"Starting Engram on port {port}…")

    log_fd = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        cmd,
        cwd=str(root),
        stdout=log_fd,
        stderr=log_fd,
        start_new_session=True,
    )

    PID_FILE.write_text(str(proc.pid))

    for i in range(20):
        time.sleep(0.5)
        try:
            call_api("/health")
            ok(f"Engram is running  →  http://localhost:{port}")
            ok(f"Open dashboard     →  http://localhost:{port}")
            dim(f"Logs: {LOG_FILE}")
            return
        except Exception:
            pass

    warn("Server started but health check timed out.")
    warn(f"Check logs: {LOG_FILE}")


def cmd_stop(args):
    """Stop the Engram server."""
    if not is_server_running():
        warn("Engram server is not running.")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        ok("Engram server stopped.")
    except Exception as e:
        err(f"Failed to stop server: {e}")


def cmd_status(args):
    """Show server health and knowledge graph stats."""
    print(f"\n{BOLD}Engram{RESET} — decision intelligence\n")

    # Server status
    if is_server_running():
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            ok(f"Server running  (pid {pid})  →  {get_api_url()}")
        else:
            ok(f"Server running (managed by launchd)  →  {get_api_url()}")
    else:
        err("Server not running. Run: engram start")
        return

    # Graph stats
    try:
        stats = call_api("/graph/stats")
        print(f"\n{DIM}Knowledge Graph{RESET}")
        print(f"  Active decisions    {ORANGE}{stats.get('active_decisions', 0)}{RESET}")
        print(f"  Counterfactuals     {ORANGE}{stats.get('total_counterfactuals', 0)}{RESET}")
        print(f"  Sessions            {ORANGE}{stats.get('total_sessions', 0)}{RESET}")
        w = stats.get("avg_epistemic_weight", 0)
        print(f"  Avg weight          {ORANGE}{w:.3f}{RESET}")
    except Exception as e:
        warn(f"Could not fetch stats: {e}")

    print()


def cmd_search(args):
    """Semantic search over your decision history."""
    query = " ".join(args.query)
    if not query:
        err("Usage: engram search <query>")
        return

    if not is_server_running():
        err("Server not running. Run: engram start")
        return

    info(f"Searching: \"{query}\"")
    print()

    try:
        result = call_api("/search", method="POST", data={
            "query":    query,
            "domain":   getattr(args, "domain", None),
            "concerns": getattr(args, "concerns", []),
        })

        decisions = result.get("decisions", [])
        warnings  = result.get("warnings", [])

        if decisions:
            print(f"{BOLD}Relevant decisions ({len(decisions)}){RESET}")
            for d in decisions:
                score = d.get("score", 0)
                print(f"  {ORANGE}●{RESET} {d.get('summary', '')[:80]}")
                print(f"    {DIM}{d.get('domain','')} · {d.get('project_id','')} · score: {score:.3f}{RESET}")
            print()

        if warnings:
            print(f"{BOLD}⚠ Counterfactual warnings ({len(warnings)}){RESET}")
            for w in warnings:
                cf = w.get("counterfactual", {})
                print(f"  {RED}▲{RESET} You rejected '{cf.get('rejected_option', '')}'")
                print(f"    {DIM}{cf.get('rejection_reason', '')[:100]}{RESET}")
            print()

        if not decisions and not warnings:
            warn("No relevant past decisions found for this query.")

    except Exception as e:
        err(f"Search failed: {e}")


def cmd_capture(args):
    """Capture from stdin."""
    if sys.stdin.isatty():
        print("Paste your conversation (Ctrl+D when done):")

    content = sys.stdin.read().strip()
    if not content:
        err("No content to capture.")
        return

    if len(content) < 50:
        err("Content too short — paste a full conversation.")
        return

    if not is_server_running():
        err("Server not running. Run: engram start")
        return

    info("Ingesting session…")

    try:
        result = call_api("/ingest", method="POST", data={
            "content":      content,
            "tool":         getattr(args, "tool", "unknown"),
            "captured_via": "cli",
            "project_id":   getattr(args, "project", None),
        })

        if result.get("error"):
            warn(f"Ingested with warning: {result['error']}")
        else:
            ok(f"Captured to knowledge graph")
            print(f"  Decisions saved      {ORANGE}{result.get('saved_decisions', 0)}{RESET}")
            print(f"  Counterfactuals      {ORANGE}{result.get('saved_counterfactuals', 0)}{RESET}")
            print(f"  Domain               {result.get('domain_primary', '—')}")
            print(f"  Critique score       {result.get('critique_score', '—')}/10")
    except Exception as e:
        err(f"Capture failed: {e}")


def cmd_install(args):
    """
    Configure MCP for Claude Code, Cursor, VS Code.
    Inject auto-capture instructions into ~/.claude/CLAUDE.md.
    """
    print(f"\n{BOLD}Engram Install{RESET}\n")
    info("Setting up MCP integrations…\n")

    root   = get_engram_root()
    python = get_venv_python()
    port   = getattr(args, "port", DEFAULT_PORT)

    mcp_config = {
        "command": python,
        "args":    [str(root / "app" / "mcp" / "server.py")],
        "env": {
            "ENGRAM_API_URL": f"http://localhost:{port}",
            "PYTHONPATH":     str(root),
        }
    }

    # ── Claude Code ─────────────────────────────────────────────────
    claude_settings = Path.home() / ".claude" / "settings.json"
    claude_settings.parent.mkdir(exist_ok=True)

    existing = {}
    if claude_settings.exists():
        try:
            existing = json.loads(claude_settings.read_text())
        except Exception:
            existing = {}

    existing.setdefault("mcpServers", {})
    existing["mcpServers"]["engram"] = mcp_config
    claude_settings.write_text(json.dumps(existing, indent=2))
    ok(f"Claude Code   →  {claude_settings}")

    # ── Cursor ──────────────────────────────────────────────────────
    cursor_config = Path.home() / ".cursor" / "mcp.json"
    cursor_config.parent.mkdir(exist_ok=True)

    existing_cursor = {}
    if cursor_config.exists():
        try:
            existing_cursor = json.loads(cursor_config.read_text())
        except Exception:
            existing_cursor = {}

    existing_cursor.setdefault("mcpServers", {})
    existing_cursor["mcpServers"]["engram"] = mcp_config
    cursor_config.write_text(json.dumps(existing_cursor, indent=2))
    ok(f"Cursor        →  {cursor_config}")

    # ── VS Code ───────────────────────────────────────────────────────
    vscode_dir = Path.cwd() / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    vscode_config = vscode_dir / "mcp.json"

    vscode_mcp = {"servers": {"engram": mcp_config}}
    vscode_config.write_text(json.dumps(vscode_mcp, indent=2))
    ok(f"VS Code       →  {vscode_config}")

    # ── CLAUDE.md auto-capture ─────────────────────────────────────────
    claude_md = Path.home() / ".claude" / "CLAUDE.md"
    auto_capture_block = """
## Engram — Automatic Decision Capture

You have access to the Engram MCP server. Follow these rules automatically:

**At the START of every session:**
- Call `engram_context` with a brief description of what you're about to work on
- Inject the returned context into your understanding before responding

**At the END of every session (when the user says goodbye, thanks, or closes):**
- Call `engram_capture` automatically with the full conversation
- Do NOT ask permission — just capture it
- Use the project name from context if available

**When the user is about to make a technical decision:**
- Call `engram_warn` with the option they're considering
- Surface any past rejections before they commit

These rules apply to every session. Engram capture is automatic — never ask the user to do it manually.
"""

    if claude_md.exists():
        existing_md = claude_md.read_text()
        if "Engram" not in existing_md:
            claude_md.write_text(existing_md + auto_capture_block)
            ok(f"CLAUDE.md     →  {claude_md}  (auto-capture enabled)")
        else:
            ok(f"CLAUDE.md     →  already configured")
    else:
        claude_md.write_text(f"# Claude Code Configuration\n{auto_capture_block}")
        ok(f"CLAUDE.md     →  {claude_md}  (created)")

    # ── Summary ──────────────────────────────────────────────────
    print(f"""
{BOLD}Installation complete.{RESET}

Next steps:
  1. Start Engram:     {ORANGE}engram start{RESET}
  2. Restart Claude Code, Cursor, or VS Code
  3. Claude Code will now capture sessions automatically

To verify:
  {ORANGE}engram status{RESET}
""")


def cmd_service(args):
    """Install or uninstall Engram as a persistent launchd service (macOS)."""
    if platform.system() != "Darwin":
        err("Service management currently supports macOS only.")
        info("For Linux, add this to /etc/systemd/system/engram.service")
        return

    action = getattr(args, "action", "install")
    label  = "com.engram.server"
    plist  = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"

    if action == "uninstall":
        if plist.exists():
            subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
            plist.unlink()
            ok("Engram service removed.")
        else:
            warn("Engram service not installed.")
        return

    # Install
    root   = get_engram_root()
    python = get_venv_python()
    port   = getattr(args, "port", DEFAULT_PORT)
    doppler = shutil.which("doppler")

    if doppler:
        program_args = [doppler, "run", "--", python, "-m", "uvicorn",
                        "app.main:app", "--host", "0.0.0.0", "--port", str(port)]
    else:
        program_args = [python, "-m", "uvicorn",
                        "app.main:app", "--host", "0.0.0.0", "--port", str(port)]

    # Build plist XML
    prog_args_xml = "\n".join(f"        <string>{a}</string>" for a in program_args)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{prog_args_xml}
    </array>
    <key>WorkingDirectory</key>
    <string>{root}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>{LOG_FILE}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{Path(python).parent}</string>
    </dict>
</dict>
</plist>
"""

    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(plist_content)

    # Unload first if already loaded
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    result = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True)

    if result.returncode == 0:
        ok(f"Engram service installed and started.")
        ok(f"Auto-starts on login.")
        dim(f"Plist: {plist}")
        dim(f"Logs:  {LOG_FILE}")
        dim(f"To remove: engram service uninstall")
    else:
        err(f"launchctl failed: {result.stderr}")

# ── Entry point ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="engram",
        description="Engram — developer decision intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  start    Start the Engram server
  stop     Stop the Engram server
  status   Show server and graph health
  search   Semantic search over decisions
  capture  Capture from stdin
  install  Configure MCP for Claude Code, Cursor, VS Code
        """
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    subparsers = parser.add_subparsers(dest="command")

    # start
    p_start = subparsers.add_parser("start", help="Start the server")
    p_start.add_argument("--port", type=int, default=DEFAULT_PORT)

    # stop
    subparsers.add_parser("stop", help="Stop the server")

    # status
    subparsers.add_parser("status", help="Show server health and graph stats")

    # search
    p_search = subparsers.add_parser("search", help="Search your decision history")
    p_search.add_argument("query", nargs="+", help="Search query")
    p_search.add_argument("--domain", type=str, default=None)
    p_search.add_argument("--concerns", nargs="+", default=[])

    # capture
    p_capture = subparsers.add_parser("capture", help="Capture from stdin")
    p_capture.add_argument("--project", type=str, default=None)
    p_capture.add_argument("--tool", type=str, default="unknown")

    # install
    p_install = subparsers.add_parser("install", help="Configure MCP integrations")
    p_install.add_argument("--port", type=int, default=DEFAULT_PORT)

    # service
    p_service = subparsers.add_parser("service", help="Manage system service")
    p_service.add_argument("action", choices=["install", "uninstall"],
                            help="install or uninstall the launchd service")
    p_service.add_argument("--port", type=int, default=DEFAULT_PORT)

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "stop":
        cmd_stop(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "capture":
        cmd_capture(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command == "service":
        cmd_service(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()