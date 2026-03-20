"""
Neo4j driver — connection, constraint setup, and CRUD operations.
"""
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Optional

from neo4j import GraphDatabase, Driver
from app.db.schema import (
    CYPHER, SessionNode, DecisionNode,
    CounterfactualNode, OutcomeNode
)

_driver: Optional[Driver] = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        uri      = os.getenv("NEO4J_URI")
        user     = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")
        if not uri or not password:
            raise RuntimeError("NEO4J_URI and NEO4J_PASSWORD required.")
        _driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_pool_size=5,
            connection_timeout=30,
            max_transaction_retry_time=15,
            keep_alive=True,
        )
    return _driver


def close_driver():
    global _driver
    if _driver:
        _driver.close()
        _driver = None


def _run_with_retry(session, query, params=None, retries=3):
    """Run a Cypher query with retry and driver reconnect on connection failure."""
    global _driver
    last_error = None
    for attempt in range(retries):
        try:
            return session.run(query, **(params or {}))
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(1 * (attempt + 1))
                if "defunct" in str(e).lower() or "routing" in str(e).lower():
                    if _driver:
                        try:
                            _driver.close()
                        except Exception:
                            pass
                        _driver = None
    raise last_error


def setup_constraints():
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Session)        REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Decision)       REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Counterfactual) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Outcome)        REQUIRE o.id IS UNIQUE",
        "CREATE INDEX IF NOT EXISTS FOR (d:Decision) ON (d.domain, d.epistemic_weight)",
        "CREATE INDEX IF NOT EXISTS FOR (c:Counterfactual) ON (c.rejection_concern)",
    ]
    driver = get_driver()
    with driver.session() as session:
        for constraint in constraints:
            _run_with_retry(session, constraint)


def save_session(tool: str, project_id: Optional[str],
                 captured_via: str, raw_excerpt: Optional[str] = None) -> str:
    node = SessionNode(
        id=str(uuid.uuid4()), tool=tool, project_id=project_id,
        raw_excerpt=raw_excerpt, started_at=datetime.now(timezone.utc),
        captured_via=captured_via,
    )
    props = node.model_dump(mode="json")
    with get_driver().session() as session:
        _run_with_retry(session, CYPHER["create_session"],
                        {"id": node.id, "props": props})
    return node.id


def save_decision(summary, chosen, reasoning, domain, situation_context,
                  session_id, tool, confidence=0.8, project_id=None, decay_rate=0.05) -> str:
    node = DecisionNode(
        id=str(uuid.uuid4()), summary=summary, chosen=chosen,
        reasoning=reasoning, domain=domain, situation_context=situation_context,
        confidence=confidence, epistemic_weight=0.7, decay_rate=decay_rate,
        is_invalidated=False, tool=tool, project_id=project_id,
        session_id=session_id, created_at=datetime.now(timezone.utc), last_reinforced=None,
    )
    props = node.model_dump(mode="json")
    with get_driver().session() as session:
        _run_with_retry(session, CYPHER["create_decision"],
                        {"id": node.id, "props": props, "session_id": session_id})
    return node.id


def save_counterfactual(rejected_option, rejection_reason, rejection_concern,
                        situation_context, decision_id, session_id) -> str:
    node = CounterfactualNode(
        id=str(uuid.uuid4()), rejected_option=rejected_option,
        rejection_reason=rejection_reason, rejection_concern=rejection_concern,
        situation_context=situation_context, epistemic_weight=0.8,
        decision_id=decision_id, session_id=session_id,
        created_at=datetime.now(timezone.utc),
    )
    props = node.model_dump(mode="json")
    with get_driver().session() as session:
        _run_with_retry(session, CYPHER["create_counterfactual"],
                        {"id": node.id, "props": props, "decision_id": decision_id})
    return node.id


def save_outcome(description, quality_score, signal_sources, decision_id) -> str:
    node = OutcomeNode(
        id=str(uuid.uuid4()), description=description,
        quality_score=quality_score, signal_sources=signal_sources,
        decision_id=decision_id, observed_at=datetime.now(timezone.utc),
    )
    props = node.model_dump(mode="json")
    delta = (quality_score - 0.5) * 0.2
    with get_driver().session() as session:
        _run_with_retry(session, CYPHER["create_outcome"],
                        {"id": node.id, "props": props, "decision_id": decision_id})
        if delta > 0:
            _run_with_retry(session, CYPHER["boost_weight"],
                            {"decision_id": decision_id, "delta": delta,
                             "now": datetime.now(timezone.utc).isoformat()})
        elif delta < 0:
            _run_with_retry(session, CYPHER["decay_weight"],
                            {"decision_id": decision_id, "delta": abs(delta)})
    return node.id


def get_similar_decisions(domain: str) -> list[dict]:
    with get_driver().session() as session:
        result = _run_with_retry(session, CYPHER["similar_decisions"], {"domain": domain})
        return [dict(r["d"]) for r in result]


def get_causal_ancestry(decision_id: str) -> list[dict]:
    query = """
        MATCH (d:Decision {id: $decision_id})-[:CAUSED_BY*1..3]->(ancestor:Decision)
        RETURN ancestor
        LIMIT 10
    """
    with get_driver().session() as session:
        result = _run_with_retry(session, query, {"decision_id": decision_id})
        return [dict(r["ancestor"]) for r in result]


def get_full_episode(decision_id: str) -> dict:
    with get_driver().session() as session:
        result = _run_with_retry(session, CYPHER["full_episode"],
                                 {"decision_id": decision_id})
        record = result.single()
        if not record:
            return {}
        return {
            "decision":       dict(record["d"]),
            "counterfactuals":[dict(c) for c in record["counterfactuals"]],
            "outcomes":       [dict(o) for o in record["outcomes"]],
            "session":        dict(record["s"]) if record["s"] else None,
        }


def surface_counterfactuals(concerns: list[str]) -> list[dict]:
    with get_driver().session() as session:
        result = _run_with_retry(session, CYPHER["surface_counterfactuals"],
                                 {"concerns": concerns})
        return [
            {"counterfactual": dict(r["c"]), "decision": dict(r["d"]), "session": dict(r["s"])}
            for r in result
        ]


def soft_invalidate(decision_id: str):
    with get_driver().session() as session:
        _run_with_retry(session, CYPHER["soft_invalidate"], {"decision_id": decision_id})


def create_caused_by_edge(new_decision_id: str, prior_decision_id: str):
    """New decision was caused by / built on top of a prior decision."""
    query = """
        MATCH (new:Decision {id: $new_id})
        MATCH (prior:Decision {id: $prior_id})
        MERGE (new)-[:CAUSED_BY]->(prior)
    """
    with get_driver().session() as session:
        _run_with_retry(session, query, {"new_id": new_decision_id, "prior_id": prior_decision_id})


def create_supersedes_edge(new_decision_id: str, old_decision_id: str):
    """New decision supersedes an older decision in the same domain/project."""
    query = """
        MATCH (new:Decision {id: $new_id})
        MATCH (old:Decision {id: $old_id})
        MERGE (new)-[:SUPERSEDES]->(old)
        SET old.is_invalidated = true
    """
    with get_driver().session() as session:
        _run_with_retry(session, query, {"new_id": new_decision_id, "old_id": old_decision_id})


def create_similar_to_edge(decision_id_a: str, decision_id_b: str, similarity_score: float):
    """Two decisions are semantically similar across projects."""
    query = """
        MATCH (a:Decision {id: $id_a})
        MATCH (b:Decision {id: $id_b})
        MERGE (a)-[r:SIMILAR_TO]->(b)
        SET r.score = $score
    """
    with get_driver().session() as session:
        _run_with_retry(session, query,
                        {"id_a": decision_id_a, "id_b": decision_id_b, "score": similarity_score})


def get_decisions_by_domain_project(domain: str, project_id: str,
                                     exclude_id: str) -> list[dict]:
    """Get existing decisions in the same domain + project for supersedes detection."""
    query = """
        MATCH (d:Decision)
        WHERE d.domain = $domain
          AND d.project_id = $project_id
          AND d.id <> $exclude_id
          AND d.is_invalidated = false
        RETURN d
        ORDER BY d.created_at ASC
    """
    with get_driver().session() as session:
        result = _run_with_retry(session, query,
                                  {"domain": domain, "project_id": project_id,
                                   "exclude_id": exclude_id})
        return [dict(r["d"]) for r in result]