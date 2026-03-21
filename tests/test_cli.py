"""
Tests for engram_cli.py — CLI commands.
Tests argument parsing, output formatting, and error handling.
Does NOT require a running server — mocks call_api and is_server_running.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_args(**kwargs):
    """Create a mock args namespace."""
    class Args:
        pass
    args = Args()
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


# ── engram status ──────────────────────────────────────────────────────────────

def test_status_when_server_not_running(capsys):
    with patch("engram_cli.is_server_running", return_value=False):
        import engram_cli
        engram_cli.cmd_status(make_args())
    out = capsys.readouterr().out
    assert "not running" in out.lower() or "✗" in out


def test_status_when_server_running(capsys):
    with patch("engram_cli.is_server_running", return_value=True), \
         patch("engram_cli.PID_FILE") as mock_pid, \
         patch("engram_cli.call_api", return_value={
             "active_decisions":     15,
             "total_counterfactuals": 24,
             "total_sessions":        6,
             "avg_epistemic_weight":  0.72,
         }):
        mock_pid.exists.return_value = False
        import engram_cli
        engram_cli.cmd_status(make_args())
    out = capsys.readouterr().out
    assert "running" in out.lower()
    assert "15"  in out
    assert "24"  in out
    assert "0.720" in out


# ── engram search ──────────────────────────────────────────────────────────────

def test_search_not_running(capsys):
    with patch("engram_cli.is_server_running", return_value=False):
        import engram_cli
        engram_cli.cmd_search(make_args(query=["database"], domain=None, concerns=[]))
    out = capsys.readouterr().out
    assert "not running" in out.lower() or "✗" in out


def test_search_displays_decisions(capsys):
    mock_result = {
        "decisions": [
            {"id": "dec-001", "score": 0.85, "summary": "Chose FastAPI over Flask",
             "domain": "framework", "project_id": "my-project", "node_type": "decision"},
        ],
        "warnings": [],
    }
    with patch("engram_cli.is_server_running", return_value=True), \
         patch("engram_cli.call_api", return_value=mock_result):
        import engram_cli
        engram_cli.cmd_search(make_args(query=["framework"], domain=None, concerns=[]))
    out = capsys.readouterr().out
    assert "FastAPI" in out
    assert "framework" in out
    assert "0.850" in out


def test_search_displays_warnings(capsys):
    mock_result = {
        "decisions": [],
        "warnings": [
            {
                "counterfactual": {
                    "rejected_option": "MongoDB",
                    "rejection_reason": "no ACID transactions",
                    "rejection_concern": "consistency",
                },
                "decision": {}, "session": {}
            }
        ],
    }
    with patch("engram_cli.is_server_running", return_value=True), \
         patch("engram_cli.call_api", return_value=mock_result):
        import engram_cli
        engram_cli.cmd_search(make_args(query=["database"], domain=None, concerns=[]))
    out = capsys.readouterr().out
    assert "MongoDB" in out
    assert "rejected" in out.lower()


def test_search_no_results_message(capsys):
    with patch("engram_cli.is_server_running", return_value=True), \
         patch("engram_cli.call_api", return_value={"decisions": [], "warnings": []}):
        import engram_cli
        engram_cli.cmd_search(make_args(query=["nothing"], domain=None, concerns=[]))
    out = capsys.readouterr().out
    assert "no relevant" in out.lower() or "not found" in out.lower()


def test_search_api_error(capsys):
    with patch("engram_cli.is_server_running", return_value=True), \
         patch("engram_cli.call_api", side_effect=Exception("connection refused")):
        import engram_cli
        engram_cli.cmd_search(make_args(query=["test"], domain=None, concerns=[]))
    out = capsys.readouterr().out
    assert "✗" in out or "failed" in out.lower()


# ── engram capture ─────────────────────────────────────────────────────────────

def test_capture_not_running(capsys, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("fake content"))
    with patch("engram_cli.is_server_running", return_value=False):
        import engram_cli
        engram_cli.cmd_capture(make_args(project=None, tool="claude"))
    out = capsys.readouterr().out
    assert "not running" in out.lower() or "✗" in out


def test_capture_success(capsys, monkeypatch):
    mock_response = {
        "saved_decisions":       3,
        "saved_counterfactuals": 4,
        "domain_primary":        "architecture",
        "critique_score":        9,
        "error":                 None,
    }
    import io
    fake_stdin = io.StringIO("x" * 200)  # long enough content

    with patch("engram_cli.is_server_running", return_value=True), \
         patch("engram_cli.call_api", return_value=mock_response), \
         patch("sys.stdin", fake_stdin), \
         patch("sys.stdin.isatty", return_value=False):
        import engram_cli
        engram_cli.cmd_capture(make_args(project="my-project", tool="claude"))
    out = capsys.readouterr().out
    assert "3" in out  # saved_decisions
    assert "4" in out  # saved_counterfactuals


# ── engram retry ──────────────────────────────────────────────────────────────

def test_retry_empty_queue(capsys, tmp_path, monkeypatch):
    import engram_cli
    monkeypatch.setattr(engram_cli, "get_engram_root", lambda: tmp_path)
    with patch("engram_cli.is_server_running", return_value=True):
        # Patch sys.path and import
        import sys
        sys.path.insert(0, str(tmp_path))

        # Create a minimal app/queue.py in tmp for import
        (tmp_path / "app").mkdir(exist_ok=True)
        (tmp_path / "app" / "__init__.py").write_text("")
        (tmp_path / "app" / "queue.py").write_text(
            "def get_queue(): return []\n"
            "def remove_from_queue(p): pass\n"
            "def queue_size(): return 0\n"
        )
        engram_cli.cmd_retry(make_args())
    out = capsys.readouterr().out
    assert "empty" in out.lower()


# ── engram delete ──────────────────────────────────────────────────────────────

def test_delete_not_running(capsys):
    with patch("engram_cli.is_server_running", return_value=False):
        import engram_cli
        engram_cli.cmd_delete(make_args(decision_id="dec-001", force=True))
    out = capsys.readouterr().out
    assert "not running" in out.lower() or "✗" in out


def test_delete_success(capsys):
    import urllib.request
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"deleted": True, "id": "dec-001"}).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("engram_cli.is_server_running", return_value=True), \
         patch("urllib.request.urlopen", return_value=mock_resp):
        import engram_cli
        engram_cli.cmd_delete(make_args(decision_id="dec-001", force=True))
    out = capsys.readouterr().out
    assert "✓" in out
    assert "deleted" in out.lower()


def test_delete_cancelled_without_force(capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with patch("engram_cli.is_server_running", return_value=True):
        import engram_cli
        engram_cli.cmd_delete(make_args(decision_id="dec-001", force=False))
    out = capsys.readouterr().out
    assert "cancelled" in out.lower() or "⚠" in out


# ── CLI argument parsing ───────────────────────────────────────────────────────

def test_main_help_exits():
    import engram_cli
    with pytest.raises(SystemExit) as exc:
        with patch("sys.argv", ["engram", "--help"]):
            engram_cli.main()
    assert exc.value.code == 0


def test_main_no_command_prints_help(capsys):
    import engram_cli
    with patch("sys.argv", ["engram"]):
        engram_cli.main()
    out = capsys.readouterr().out
    assert "engram" in out.lower()


def test_search_subcommand_parsed():
    import engram_cli
    with patch("sys.argv", ["engram", "search", "database", "choices"]), \
         patch("engram_cli.cmd_search") as mock_cmd:
        engram_cli.main()
    mock_cmd.assert_called_once()
    args = mock_cmd.call_args[0][0]
    assert args.query == ["database", "choices"]


def test_delete_subcommand_parsed():
    import engram_cli
    with patch("sys.argv", ["engram", "delete", "dec-001", "--force"]), \
         patch("engram_cli.cmd_delete") as mock_cmd:
        engram_cli.main()
    mock_cmd.assert_called_once()
    args = mock_cmd.call_args[0][0]
    assert args.decision_id == "dec-001"
    assert args.force is True