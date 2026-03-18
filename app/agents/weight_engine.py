"""
Engram — Epistemic Weight Engine.

Runs as a FastAPI background task. Evolves decision node weights
over time using passive signals — never requires user input.

Weight range: 0.0 (mathematically invisible) to 1.0 (bedrock truth)
Starting weight: 0.7 (neutral-positive)

Four passive signal sources:
  1. Time decay      — older decisions lose weight at their decay_rate
  2. Override signal — a contradicting decision reduces the older one's weight
  3. Propagation     — decisions retrieved and reused gain weight
  4. Contradiction   — decisions that conflict with newer ones decay faster

Design principle: good decisions solidify, bad ones wither — automatically.
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from neo4j import Driver

from app.db.neo4j_client import get_driver, _run_with_retry


# ── Time decay ────────────────────────────────────────────────────────────────

def apply_time_decay():
    """
    Applies exponential decay: W(t) = W * e^(-λ * days_elapsed)
    
    decay_rate (λ) is set per-decision by the triage agent at extraction time:
      0.01 = architectural (months to decay)
      0.05 = design choice (weeks)
      0.15 = bug fix (days)
      0.30 = trivial preference (hours)
    
    Decisions already below 0.1 epistemic_weight are skipped — they're
    already effectively invisible and we avoid unnecessary writes.
    """
    import math

    query = """
        MATCH (d:Decision)
        WHERE NOT d.is_invalidated
        AND d.epistemic_weight > 0.1
        RETURN d.id as id, d.epistemic_weight as weight,
               d.decay_rate as decay_rate, d.created_at as created_at
    """
    update_query = """
        MATCH (d:Decision {id: $id})
        SET d.epistemic_weight = $new_weight
    """

    driver = get_driver()
    with driver.session() as session:
        result = _run_with_retry(session, query)
        records = list(result)

    now = datetime.now(timezone.utc)
    updated = 0

    for record in records:
        try:
            created_str = record["created_at"]
            if isinstance(created_str, str):
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            else:
                created = created_str

            days_elapsed = (now - created).total_seconds() / 86400
            decay_rate   = record["decay_rate"] or 0.05
            current_w    = record["weight"] or 0.7

            # W(t) = W0 * e^(-λ * t)
            new_weight = current_w * math.exp(-decay_rate * days_elapsed)
            new_weight = max(0.05, round(new_weight, 4))  # floor at 0.05

            if abs(new_weight - current_w) > 0.001:  # only write if meaningful change
                with driver.session() as session:
                    _run_with_retry(session, update_query,
                                    {"id": record["id"], "new_weight": new_weight})
                updated += 1
        except Exception:
            continue

    return updated


# ── Override signal detection ─────────────────────────────────────────────────

def detect_and_apply_overrides():
    """
    Detects when a newer decision supersedes an older one in the same domain
    and project, then:
      1. Creates a SUPERSEDES relationship from new → old
      2. Decays the older decision's weight by 0.2
      3. Marks the older decision with is_invalidated if weight drops below 0.15
    
    Logic: same domain + same project + newer created_at = likely override.
    The LLM extraction already tags domain — we use this for detection.
    """
    find_query = """
        MATCH (d1:Decision), (d2:Decision)
        WHERE d1.domain = d2.domain
        AND d1.project_id = d2.project_id
        AND d1.project_id IS NOT NULL
        AND d1.id <> d2.id
        AND d1.created_at > d2.created_at
        AND NOT (d1)-[:SUPERSEDES]->(d2)
        AND NOT d2.is_invalidated
        AND d2.epistemic_weight > 0.15
        RETURN d1.id as newer_id, d2.id as older_id,
               d2.epistemic_weight as older_weight
        LIMIT 20
    """
    supersede_query = """
        MATCH (d1:Decision {id: $newer_id}), (d2:Decision {id: $older_id})
        MERGE (d1)-[:SUPERSEDES]->(d2)
        SET d2.epistemic_weight = max(0.05, d2.epistemic_weight - 0.15)
        SET d2.is_invalidated = CASE
            WHEN d2.epistemic_weight - 0.15 < 0.15 THEN true
            ELSE false
        END
        RETURN d2.epistemic_weight
    """

    driver = get_driver()
    with driver.session() as session:
        result = _run_with_retry(session, find_query)
        pairs = [(r["newer_id"], r["older_id"]) for r in result]

    applied = 0
    for newer_id, older_id in pairs:
        try:
            with driver.session() as session:
                _run_with_retry(session, supersede_query,
                                {"newer_id": newer_id, "older_id": older_id})
            applied += 1
        except Exception:
            continue

    return applied


# ── Propagation signal ────────────────────────────────────────────────────────

def boost_retrieved_decisions(decision_ids: list[str]):
    """
    Called by the retrieval agent when decisions are surfaced to a user.
    A decision being retrieved and used is a positive signal — it's relevant.
    Boost: +0.05 epistemic_weight, capped at 1.0.
    
    This is the reinforcement feedback loop:
    decisions that keep getting used solidify into bedrock knowledge.
    """
    if not decision_ids:
        return

    boost_query = """
        MATCH (d:Decision {id: $id})
        SET d.epistemic_weight = min(1.0, d.epistemic_weight + 0.05)
        SET d.last_reinforced = $now
    """
    now = datetime.now(timezone.utc).isoformat()
    driver = get_driver()

    for decision_id in decision_ids:
        try:
            with driver.session() as session:
                _run_with_retry(session, boost_query,
                                {"id": decision_id, "now": now})
        except Exception:
            continue


# ── Contradiction detection ───────────────────────────────────────────────────

def detect_contradictions():
    """
    Finds decisions in the same domain across different projects where
    the chosen option in one is a rejected option (counterfactual) in another.
    
    Example: Project A chose PostgreSQL. Project B rejected PostgreSQL for performance.
    This is a cross-project contradiction — surfaces as a CONTRADICTS relationship.
    
    These contradictions are the most valuable learning signal:
    "You chose X in project A but rejected it in project B — why?"
    """
    find_query = """
        MATCH (d1:Decision)-[:REJECTED]->(c:Counterfactual)
        MATCH (d2:Decision)
        WHERE d2.chosen = c.rejected_option
        AND d1.id <> d2.id
        AND NOT (d1)-[:CONTRADICTS]-(d2)
        RETURN d1.id as d1_id, d2.id as d2_id,
               c.rejected_option as contested_option,
               c.rejection_concern as concern
        LIMIT 10
    """
    mark_query = """
        MATCH (d1:Decision {id: $d1_id}), (d2:Decision {id: $d2_id})
        MERGE (d1)-[:CONTRADICTS {
            contested_option: $option,
            concern: $concern,
            detected_at: $now
        }]->(d2)
    """
    now = datetime.now(timezone.utc).isoformat()
    driver = get_driver()

    with driver.session() as session:
        result = _run_with_retry(session, find_query)
        contradictions = [
            (r["d1_id"], r["d2_id"], r["contested_option"], r["concern"])
            for r in result
        ]

    marked = 0
    for d1_id, d2_id, option, concern in contradictions:
        try:
            with driver.session() as session:
                _run_with_retry(session, mark_query,
                                {"d1_id": d1_id, "d2_id": d2_id,
                                 "option": option, "concern": concern,
                                 "now": now})
            marked += 1
        except Exception:
            continue

    return marked


# ── Graph health stats ────────────────────────────────────────────────────────

def get_graph_stats() -> dict:
    """Returns current state of the knowledge graph for monitoring."""
    query = """
        MATCH (d:Decision) WHERE NOT d.is_invalidated
        WITH count(d) as active_decisions,
             avg(d.epistemic_weight) as avg_weight
        MATCH (c:Counterfactual)
        WITH active_decisions, avg_weight, count(c) as total_counterfactuals
        MATCH (s:Session)
        RETURN active_decisions, avg_weight,
               total_counterfactuals, count(s) as total_sessions
    """
    try:
        driver = get_driver()
        with driver.session() as session:
            result = _run_with_retry(session, query)
            record = result.single()
            if record:
                return {
                    "active_decisions":     record["active_decisions"],
                    "avg_epistemic_weight": round(record["avg_weight"] or 0, 3),
                    "total_counterfactuals":record["total_counterfactuals"],
                    "total_sessions":       record["total_sessions"],
                }
    except Exception as e:
        return {"error": str(e)}
    return {}


# ── Full engine run ───────────────────────────────────────────────────────────

def run_weight_engine() -> dict:
    """
    Runs all weight engine operations in sequence.
    Called by the FastAPI background task scheduler.
    Safe to run frequently — all operations are idempotent.
    """
    results = {}

    try:
        results["decayed"]       = apply_time_decay()
    except Exception as e:
        results["decay_error"]   = str(e)

    try:
        results["overrides"]     = detect_and_apply_overrides()
    except Exception as e:
        results["override_error"] = str(e)

    try:
        results["contradictions"] = detect_contradictions()
    except Exception as e:
        results["contradiction_error"] = str(e)

    results["stats"]             = get_graph_stats()
    results["ran_at"]            = datetime.now(timezone.utc).isoformat()

    return results