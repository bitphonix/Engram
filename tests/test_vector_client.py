"""
Tests for app/db/vector_client.py — ChromaDB local vector search.
Uses a temp directory so tests never touch the real ~/.engram/chroma.
Mocks the Gemini embedding API so tests run without network or API key.
"""
import pytest
from unittest.mock import patch, MagicMock


FAKE_EMBEDDING = [0.1] * 768  # 768-dim fake vector


def fake_embed(text, task_type="retrieval_document"):
    """Returns a deterministic fake embedding."""
    return FAKE_EMBEDDING


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_chroma(tmp_path, monkeypatch):
    """Give each test its own ChromaDB directory and reset singletons."""
    import app.db.vector_client as vc
    monkeypatch.setattr(vc, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vc, "_client", None)
    monkeypatch.setattr(vc, "_collection", None)
    yield
    # Reset singletons after test
    vc._client     = None
    vc._collection = None


@pytest.fixture(autouse=True)
def mock_embed(monkeypatch):
    """Mock the Gemini embedding API for all tests."""
    import app.db.vector_client as vc
    monkeypatch.setattr(vc, "_embed", fake_embed)


# ── Collection init tests ──────────────────────────────────────────────────────

def test_get_collection_creates_collection():
    from app.db.vector_client import _get_collection
    col = _get_collection()
    assert col is not None
    assert col.count() == 0


def test_get_collection_singleton():
    from app.db.vector_client import _get_collection
    col1 = _get_collection()
    col2 = _get_collection()
    assert col1 is col2


# ── Write tests ────────────────────────────────────────────────────────────────

def test_embed_and_store_decision_returns_true():
    from app.db.vector_client import embed_and_store_decision
    result = embed_and_store_decision(
        decision_id="dec-001",
        summary="Chose FastAPI over Flask",
        reasoning="FastAPI has async support",
        domain="framework",
        situation_context="building a new API",
        project_id="test-project",
    )
    assert result is True


def test_embed_and_store_decision_persists():
    from app.db.vector_client import embed_and_store_decision, _get_collection
    embed_and_store_decision(
        decision_id="dec-001",
        summary="Chose FastAPI over Flask",
        reasoning="async support",
        domain="framework",
        situation_context="building an API",
        project_id="test-project",
    )
    assert _get_collection().count() == 1


def test_embed_and_store_decision_upserts():
    """Storing the same ID twice should not create duplicates."""
    from app.db.vector_client import embed_and_store_decision, _get_collection
    for _ in range(3):
        embed_and_store_decision(
            decision_id="dec-001",
            summary="Chose FastAPI",
            reasoning="async",
            domain="framework",
            situation_context="API",
            project_id="proj",
        )
    assert _get_collection().count() == 1


def test_embed_and_store_counterfactual_returns_true():
    from app.db.vector_client import embed_and_store_counterfactual
    result = embed_and_store_counterfactual(
        cf_id="cf-001",
        rejected_option="Flask",
        rejection_reason="no async support",
        rejection_concern="performance",
        situation_context="building an API",
        decision_id="dec-001",
        project_id="test-project",
    )
    assert result is True


def test_embed_and_store_counterfactual_persists():
    from app.db.vector_client import embed_and_store_counterfactual, _get_collection
    embed_and_store_counterfactual(
        cf_id="cf-001",
        rejected_option="Flask",
        rejection_reason="no async",
        rejection_concern="performance",
        situation_context="building an API",
        decision_id="dec-001",
    )
    assert _get_collection().count() == 1


def test_store_decision_without_project_id():
    from app.db.vector_client import embed_and_store_decision, _get_collection
    result = embed_and_store_decision(
        decision_id="dec-002",
        summary="Chose PostgreSQL",
        reasoning="reliability",
        domain="database",
        situation_context="picking a DB",
        project_id=None,
    )
    assert result is True
    assert _get_collection().count() == 1


# ── Search tests ───────────────────────────────────────────────────────────────

def test_semantic_search_empty_collection():
    from app.db.vector_client import semantic_search
    results = semantic_search("any query", limit=5)
    assert results == []


def test_semantic_search_returns_results():
    from app.db.vector_client import embed_and_store_decision, semantic_search
    embed_and_store_decision(
        decision_id="dec-001",
        summary="Chose FastAPI",
        reasoning="async",
        domain="framework",
        situation_context="API",
        project_id="proj",
    )
    results = semantic_search("framework choice", limit=5)
    assert len(results) == 1
    assert results[0]["id"] == "dec-001"
    assert results[0]["domain"] == "framework"
    assert "score" in results[0]


def test_semantic_search_result_structure():
    from app.db.vector_client import embed_and_store_decision, semantic_search
    embed_and_store_decision(
        decision_id="dec-001",
        summary="Chose Redis",
        reasoning="fast",
        domain="infrastructure",
        situation_context="caching",
        project_id="my-project",
    )
    results = semantic_search("caching solution")
    r = results[0]
    assert "id"         in r
    assert "score"      in r
    assert "node_type"  in r
    assert "domain"     in r
    assert "project_id" in r
    assert "summary"    in r


def test_semantic_search_node_type_filter():
    from app.db.vector_client import (
        embed_and_store_decision, embed_and_store_counterfactual, semantic_search
    )
    embed_and_store_decision(
        decision_id="dec-001", summary="Chose Redis",
        reasoning="fast", domain="infrastructure",
        situation_context="caching", project_id="proj",
    )
    embed_and_store_counterfactual(
        cf_id="cf-001", rejected_option="Memcached",
        rejection_reason="limited", rejection_concern="performance",
        situation_context="caching", decision_id="dec-001",
    )
    # Search decisions only
    results = semantic_search("caching", node_type_filter="decision")
    assert all(r["node_type"] == "decision" for r in results)
    assert len(results) == 1


def test_semantic_search_multiple_results():
    from app.db.vector_client import embed_and_store_decision, semantic_search
    for i in range(5):
        embed_and_store_decision(
            decision_id=f"dec-00{i}",
            summary=f"Decision {i}",
            reasoning="reasoning",
            domain="database",
            situation_context="context",
            project_id="proj",
        )
    results = semantic_search("query", limit=3)
    assert len(results) <= 3


def test_semantic_search_counterfactuals():
    from app.db.vector_client import (
        embed_and_store_counterfactual, semantic_search_counterfactuals
    )
    embed_and_store_counterfactual(
        cf_id="cf-001",
        rejected_option="MongoDB",
        rejection_reason="no transactions",
        rejection_concern="consistency",
        situation_context="database selection",
        decision_id="dec-001",
    )
    results = semantic_search_counterfactuals("database choice")
    assert len(results) == 1
    assert results[0]["id"] == "cf-001"
    assert results[0]["rejected_option"] == "MongoDB"


def test_get_collection_stats():
    from app.db.vector_client import embed_and_store_decision, get_collection_stats
    embed_and_store_decision(
        decision_id="dec-001", summary="test",
        reasoning="r", domain="database",
        situation_context="ctx", project_id="proj",
    )
    stats = get_collection_stats()
    assert stats["total_vectors"] == 1
    assert stats["backend"] == "chromadb_local"
    assert "storage_path" in stats