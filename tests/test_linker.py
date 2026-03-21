"""
Tests for app/agents/linker.py — decision relationship linker.
Mocks Neo4j and ChromaDB so tests run without external services.
"""
import pytest
from unittest.mock import patch, MagicMock, call


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_neo4j(monkeypatch):
    """Mock all Neo4j write operations."""
    mocks = {
        "create_caused_by_edge":     MagicMock(),
        "create_supersedes_edge":    MagicMock(),
        "create_similar_to_edge":    MagicMock(),
        "get_decisions_by_domain_project": MagicMock(return_value=[]),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(f"app.agents.linker.{name}", mock)
    return mocks


@pytest.fixture
def mock_vector_search(monkeypatch):
    """Mock Atlas/ChromaDB vector search."""
    mock = MagicMock(return_value=[])
    monkeypatch.setattr("app.agents.linker.semantic_search", mock)
    return mock


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_link_decision_returns_dict(mock_neo4j, mock_vector_search):
    from app.agents.linker import link_decision
    result = link_decision(
        decision_id="dec-001",
        summary="Chose FastAPI over Flask",
        domain="framework",
        project_id="test-project",
        raw_content="we chose FastAPI",
    )
    assert "caused_by"  in result
    assert "supersedes" in result
    assert "similar_to" in result


def test_link_decision_no_edges_when_no_similar(mock_neo4j, mock_vector_search):
    from app.agents.linker import link_decision
    mock_vector_search.return_value = []
    result = link_decision(
        decision_id="dec-001",
        summary="Chose FastAPI",
        domain="framework",
        project_id="proj",
        raw_content="content",
    )
    assert result["caused_by"]  == []
    assert result["similar_to"] == []


def test_link_decision_supersedes_older_same_domain(mock_neo4j, mock_vector_search):
    """New decision should supersede older ones in same domain+project."""
    from app.agents.linker import link_decision
    mock_neo4j["get_decisions_by_domain_project"].return_value = [
        {"id": "dec-old-001", "summary": "Old framework decision"}
    ]
    result = link_decision(
        decision_id="dec-new-001",
        summary="Chose FastAPI",
        domain="framework",
        project_id="my-project",
        raw_content="content",
    )
    assert "dec-old-001" in result["supersedes"]
    mock_neo4j["create_supersedes_edge"].assert_called_once_with(
        new_decision_id="dec-new-001",
        old_decision_id="dec-old-001",
    )


def test_link_decision_no_supersedes_without_project(mock_neo4j, mock_vector_search):
    """No supersedes if project_id is None."""
    from app.agents.linker import link_decision
    result = link_decision(
        decision_id="dec-001",
        summary="Chose FastAPI",
        domain="framework",
        project_id=None,
        raw_content="content",
    )
    assert result["supersedes"] == []
    mock_neo4j["get_decisions_by_domain_project"].assert_not_called()


def test_link_decision_similar_to_high_score(mock_neo4j, mock_vector_search):
    """High similarity score → SIMILAR_TO edge."""
    from app.agents.linker import link_decision, SIMILAR_TO_THRESHOLD
    mock_vector_search.return_value = [
        {"id": "dec-other", "score": SIMILAR_TO_THRESHOLD + 0.01, "summary": "Similar decision"}
    ]
    result = link_decision(
        decision_id="dec-001",
        summary="Chose FastAPI",
        domain="framework",
        project_id="proj",
        raw_content="content",
    )
    assert "dec-other" in result["similar_to"]
    mock_neo4j["create_similar_to_edge"].assert_called_once()


def test_link_decision_no_similar_to_low_score(mock_neo4j, mock_vector_search):
    """Low similarity score → no SIMILAR_TO edge."""
    from app.agents.linker import link_decision, SIMILAR_TO_THRESHOLD
    mock_vector_search.return_value = [
        {"id": "dec-other", "score": SIMILAR_TO_THRESHOLD - 0.05, "summary": "Weak match"}
    ]
    result = link_decision(
        decision_id="dec-001",
        summary="Chose FastAPI",
        domain="framework",
        project_id="proj",
        raw_content="content",
    )
    assert result["similar_to"] == []
    mock_neo4j["create_similar_to_edge"].assert_not_called()


def test_link_decision_skips_self(mock_neo4j, mock_vector_search):
    """Should never create an edge from a node to itself."""
    from app.agents.linker import link_decision
    mock_vector_search.return_value = [
        {"id": "dec-001", "score": 1.0, "summary": "Same decision"}
    ]
    result = link_decision(
        decision_id="dec-001",
        summary="Chose FastAPI",
        domain="framework",
        project_id="proj",
        raw_content="content",
    )
    assert "dec-001" not in result["similar_to"]
    assert "dec-001" not in result["caused_by"]


def test_link_decision_caused_by_with_keyword_match(mock_neo4j, mock_vector_search):
    """High score + keyword match in raw_content → CAUSED_BY edge."""
    from app.agents.linker import link_decision, CAUSED_BY_THRESHOLD
    mock_vector_search.return_value = [
        {
            "id":      "dec-prior",
            "score":   CAUSED_BY_THRESHOLD + 0.01,
            "summary": "Chose ClickHouse Redis analytics platform caching layer"
        }
    ]
    result = link_decision(
        decision_id="dec-new",
        summary="Adding Redis cache on top of ClickHouse analytics",
        domain="infrastructure",
        project_id="proj",
        # raw_content contains keywords from prior decision summary
        raw_content="We chose ClickHouse last month for analytics. Now adding Redis caching layer.",
    )
    assert "dec-prior" in result["caused_by"]
    mock_neo4j["create_caused_by_edge"].assert_called_once()


def test_link_decision_handles_exception_gracefully(mock_neo4j, mock_vector_search):
    """Linker should not raise even if Neo4j write fails."""
    from app.agents.linker import link_decision
    mock_neo4j["create_supersedes_edge"].side_effect = Exception("Neo4j down")
    mock_neo4j["get_decisions_by_domain_project"].return_value = [
        {"id": "dec-old"}
    ]
    # Should not raise
    result = link_decision(
        decision_id="dec-new",
        summary="decision",
        domain="database",
        project_id="proj",
        raw_content="content",
    )
    assert isinstance(result, dict)


def test_extract_keywords_filters_stop_words():
    from app.agents.linker import _extract_keywords
    keywords = _extract_keywords("Chose FastAPI over Flask for building APIs")
    assert "chose" not in keywords
    assert "over"  not in keywords
    assert "for"   not in keywords
    assert "FastAPI" in keywords or "fastapi" in keywords


def test_extract_keywords_filters_short_words():
    from app.agents.linker import _extract_keywords
    keywords = _extract_keywords("Use a DB for the app")
    # Words shorter than 4 chars filtered out
    assert "Use" not in keywords
    assert "DB"  not in keywords
    assert "the" not in keywords