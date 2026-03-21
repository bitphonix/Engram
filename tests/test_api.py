"""
Tests for new API endpoints:
  DELETE /decisions/{id}  — delete decision + counterfactuals
  POST   /search          — fast search without briefing synthesis
  POST   /ingest          — deduplication via content hash

Uses FastAPI TestClient — no real server needed.
Mocks Neo4j, ChromaDB, and the LangGraph pipeline.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_google_credentials(monkeypatch):
    """Prevent Google SDK from looking for credentials during tests."""
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    with patch("google.auth.default", return_value=(MagicMock(), "test-project")):
        yield

# ── App fixture ────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    """Create test client with all external services mocked."""

    # Mock Neo4j setup
    monkeypatch.setattr(
        "app.db.neo4j_client.setup_constraints",
        MagicMock()
    )

    from app.main import app
    return TestClient(app)


# ── DELETE /decisions/{id} ─────────────────────────────────────────────────────

def test_delete_decision_success(client, monkeypatch):
    monkeypatch.setattr(
        "app.db.neo4j_client.delete_decision",
        MagicMock(return_value=True)
    )
    monkeypatch.setattr(
        "app.db.vector_client._get_collection",
        MagicMock(return_value=MagicMock(delete=MagicMock()))
    )
    resp = client.delete("/decisions/dec-001")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert resp.json()["id"] == "dec-001"


def test_delete_decision_not_found(client, monkeypatch):
    monkeypatch.setattr(
        "app.db.neo4j_client.delete_decision",
        MagicMock(return_value=False)
    )
    resp = client.delete("/decisions/nonexistent-id")
    assert resp.status_code == 404


def test_delete_decision_chroma_failure_still_succeeds(client, monkeypatch):
    """ChromaDB delete failure should not fail the whole endpoint."""
    monkeypatch.setattr(
        "app.db.neo4j_client.delete_decision",
        MagicMock(return_value=True)
    )
    monkeypatch.setattr(
        "app.db.vector_client._get_collection",
        MagicMock(side_effect=Exception("ChromaDB error"))
    )
    resp = client.delete("/decisions/dec-001")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


# ── POST /search ───────────────────────────────────────────────────────────────

def test_search_returns_decisions_and_warnings(client, monkeypatch):
    monkeypatch.setattr(
        "app.db.vector_client.semantic_search",
        MagicMock(return_value=[
            {"id": "dec-001", "score": 0.85, "summary": "Chose FastAPI",
             "domain": "framework", "project_id": "proj", "node_type": "decision"}
        ])
    )
    monkeypatch.setattr(
        "app.db.neo4j_client.surface_counterfactuals",
        MagicMock(return_value=[])
    )
    resp = client.post("/search", json={"query": "framework choice"})
    assert resp.status_code == 200
    data = resp.json()
    assert "decisions" in data
    assert "warnings"  in data
    assert len(data["decisions"]) == 1
    assert data["decisions"][0]["id"] == "dec-001"


def test_search_without_concerns_returns_empty_warnings(client, monkeypatch):
    monkeypatch.setattr(
        "app.db.vector_client.semantic_search",
        MagicMock(return_value=[])
    )
    monkeypatch.setattr(
        "app.db.neo4j_client.surface_counterfactuals",
        MagicMock(return_value=[])
    )
    resp = client.post("/search", json={"query": "test"})
    assert resp.status_code == 200
    assert resp.json()["warnings"] == []


def test_search_with_concerns_calls_counterfactuals(client, monkeypatch):
    mock_surface = MagicMock(return_value=[
        {"counterfactual": {"rejected_option": "MongoDB",
                            "rejection_reason": "no transactions",
                            "rejection_concern": "consistency"},
         "decision": {}, "session": {}}
    ])
    monkeypatch.setattr("app.db.vector_client.semantic_search", MagicMock(return_value=[]))
    monkeypatch.setattr("app.db.neo4j_client.surface_counterfactuals", mock_surface)
    resp = client.post("/search", json={
        "query":    "database",
        "concerns": ["consistency", "performance"],
    })
    assert resp.status_code == 200
    mock_surface.assert_called_once_with(["consistency", "performance"])
    assert len(resp.json()["warnings"]) == 1


def test_search_requires_query(client):
    resp = client.post("/search", json={})
    assert resp.status_code == 422  # Pydantic validation error


# ── POST /ingest deduplication ─────────────────────────────────────────────────

def test_ingest_rejects_duplicate(monkeypatch):
    """Duplicate detection in graph_writer_node returns error without writing."""
    from app.graph.nodes import graph_writer_node

    with patch("app.db.neo4j_client.session_hash_exists", return_value=True):
        result = graph_writer_node({
            "raw_content":   "x" * 100,
            "tool":          "claude",
            "captured_via":  "manual_paste",
            "project_id":    None,
            "decisions":     [],
            "retry_count":   0,
        })

    assert result.get("error") == "duplicate: session already ingested"
    assert result.get("saved_decision_ids") == []
    assert result.get("session_id") is None


# ── GET /graph/network ─────────────────────────────────────────────────────────

def test_graph_network_returns_nodes_and_edges(client, monkeypatch):
    monkeypatch.setattr(
        "app.main.get_graph_network",    # ← patch where it's used
        MagicMock(return_value={
            "nodes": [{"id": "dec-001", "summary": "test", "domain": "database",
                       "project_id": "proj", "weight": 0.7, "is_invalidated": False,
                       "chosen": "PostgreSQL"}],
            "edges": [],
        })
    )
    resp = client.get("/graph/network")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 1


# ── GET /health ────────────────────────────────────────────────────────────────

def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "engram"