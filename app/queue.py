"""
Engram — Local ingest queue.

When ingestion fails (Gemini down, Neo4j down, network error),
the session content is saved to ~/.engram/queue/ as a JSON file.

On next `engram start` or `engram retry`, the queue is drained
automatically — no content is ever lost.

Queue file format:
  ~/.engram/queue/<timestamp>_<hash>.json
  {
    "content":      "...",
    "tool":         "claude",
    "captured_via": "manual_paste",
    "project_id":   "my-project",
    "failed_at":    "2026-03-21T10:00:00Z",
    "error":        "Gemini API timeout",
    "attempts":     1
  }
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

QUEUE_DIR = Path.home() / ".engram" / "queue"
MAX_ATTEMPTS = 5


def _queue_path(content: str, timestamp: str) -> Path:
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
    return QUEUE_DIR / f"{timestamp}_{content_hash}.json"


def enqueue_failed(
    content: str,
    tool: str,
    captured_via: str,
    project_id: Optional[str],
    error: str,
    attempts: int = 1,
) -> Path:
    """
    Save a failed ingest to the local queue.
    Called by the ingest endpoint when the pipeline raises an exception.
    """
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path      = _queue_path(content, timestamp)

    item = {
        "content":      content,
        "tool":         tool,
        "captured_via": captured_via,
        "project_id":   project_id,
        "failed_at":    datetime.now(timezone.utc).isoformat(),
        "error":        error,
        "attempts":     attempts,
    }

    path.write_text(json.dumps(item, indent=2))
    return path


def get_queue() -> list[dict]:
    """Return all items in the queue, sorted by oldest first."""
    if not QUEUE_DIR.exists():
        return []

    items = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        try:
            item = json.loads(f.read_text())
            item["_path"] = str(f)
            items.append(item)
        except Exception:
            continue
    return items


def remove_from_queue(path: str):
    """Remove a successfully retried item from the queue."""
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def queue_size() -> int:
    """Return number of items waiting in queue."""
    if not QUEUE_DIR.exists():
        return 0
    return len(list(QUEUE_DIR.glob("*.json")))