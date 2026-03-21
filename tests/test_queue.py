"""
Tests for app/queue.py — local retry queue for failed ingests.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


# ── Override queue dir to a temp location for tests ───────────────────────────
@pytest.fixture(autouse=True)
def tmp_queue(tmp_path, monkeypatch):
    import app.queue as q
    monkeypatch.setattr(q, "QUEUE_DIR", tmp_path / "queue")
    yield tmp_path / "queue"


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_enqueue_creates_file():
    from app.queue import enqueue_failed, QUEUE_DIR
    path = enqueue_failed(
        content="test session content",
        tool="claude",
        captured_via="manual_paste",
        project_id="test-project",
        error="Gemini timeout",
    )
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["content"] == "test session content"
    assert data["tool"] == "claude"
    assert data["error"] == "Gemini timeout"
    assert data["attempts"] == 1
    assert data["project_id"] == "test-project"


def test_enqueue_empty_queue_returns_empty_list():
    from app.queue import get_queue
    assert get_queue() == []


def test_get_queue_returns_items():
    from app.queue import enqueue_failed, get_queue
    enqueue_failed("content A", "claude", "manual_paste", "proj-a", "error A")
    enqueue_failed("content B", "cursor", "mcp", "proj-b", "error B")
    items = get_queue()
    assert len(items) == 2
    # Sorted oldest first
    assert items[0]["content"] == "content A"
    assert items[1]["content"] == "content B"


def test_get_queue_includes_path():
    from app.queue import enqueue_failed, get_queue
    enqueue_failed("content", "claude", "manual_paste", None, "error")
    items = get_queue()
    assert "_path" in items[0]
    assert items[0]["_path"].endswith(".json")


def test_remove_from_queue():
    from app.queue import enqueue_failed, get_queue, remove_from_queue
    enqueue_failed("content", "claude", "manual_paste", None, "error")
    items = get_queue()
    assert len(items) == 1
    remove_from_queue(items[0]["_path"])
    assert get_queue() == []


def test_queue_size_empty():
    from app.queue import queue_size
    assert queue_size() == 0


def test_queue_size_with_items():
    from app.queue import enqueue_failed, queue_size
    enqueue_failed("content 1", "claude", "manual_paste", None, "error")
    enqueue_failed("content 2", "claude", "manual_paste", None, "error")
    assert queue_size() == 2


def test_enqueue_stores_attempts():
    from app.queue import enqueue_failed
    path = enqueue_failed("content", "claude", "manual_paste", None, "err", attempts=3)
    data = json.loads(path.read_text())
    assert data["attempts"] == 3


def test_enqueue_without_project_id():
    from app.queue import enqueue_failed
    path = enqueue_failed("content", "claude", "manual_paste", None, "error")
    data = json.loads(path.read_text())
    assert data["project_id"] is None


def test_remove_nonexistent_path_does_not_raise():
    from app.queue import remove_from_queue
    # Should not raise even if file doesn't exist
    remove_from_queue("/nonexistent/path/file.json")


def test_queue_dir_created_on_enqueue(tmp_path, monkeypatch):
    import app.queue as q
    new_dir = tmp_path / "new_queue_dir"
    monkeypatch.setattr(q, "QUEUE_DIR", new_dir)
    assert not new_dir.exists()
    q.enqueue_failed("content", "claude", "manual_paste", None, "error")
    assert new_dir.exists()