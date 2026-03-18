"""
NEXUS — Temporal Causal Knowledge Graph Schema
===============================================

Node types and relationship types for the Neo4j graph.
This file is the single source of truth for the data model.
Every agent, every query, every API call derives its shape from here.

Design principles:
- Counterfactuals are first-class nodes, not afterthoughts
- Epistemic weight evolves passively from real signals, never manually
- Nothing is deleted — soft invalidation preserves causal history
- Every relationship is typed and directed with a timestamp
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Node type labels (used in Cypher queries) ─────────────────────────────────

class NodeLabel(str, Enum):
    SESSION      = "Session"       # A conversation or work session
    DECISION     = "Decision"      # A choice that was made, with reasoning
    COUNTERFACT  = "Counterfactual"# A path explicitly rejected — most valuable
    OUTCOME      = "Outcome"       # What resulted from a decision over time
    CONCEPT      = "Concept"       # A recurring idea, pattern, or technology
    PROJECT      = "Project"       # A codebase or work context


# ── Relationship types (directed edges in Cypher) ─────────────────────────────

class RelType(str, Enum):
    # Session → Decision
    PRODUCED        = "PRODUCED"       # This session produced this decision

    # Decision → Decision
    CAUSED_BY       = "CAUSED_BY"      # This decision was caused by a prior decision
    SUPERSEDES      = "SUPERSEDES"     # This decision replaces/overrides an older one
    CONTRADICTS     = "CONTRADICTS"    # This decision conflicts with another (detected)
    SIMILAR_TO      = "SIMILAR_TO"     # Structurally similar decision in different context

    # Decision → Counterfactual
    REJECTED        = "REJECTED"       # This decision rejected this alternative

    # Counterfactual → Counterfactual
    ALSO_REJECTED   = "ALSO_REJECTED"  # Same session rejected multiple alternatives

    # Decision → Outcome
    LED_TO          = "LED_TO"         # This decision led to this outcome

    # Outcome → Decision
    REINFORCED      = "REINFORCED"     # Success signal boosted this decision's weight
    INVALIDATED     = "INVALIDATED"    # Failure signal decayed this decision's weight

    # Decision / Counterfactual → Concept
    INVOLVES        = "INVOLVES"       # Decision involves this concept/technology

    # Session → Project
    BELONGS_TO      = "BELONGS_TO"     # Session occurred in this project context

    # Counterfactual → Decision (cross-session — the most powerful relationship)
    CHOSEN_LATER    = "CHOSEN_LATER"   # Something rejected here was chosen later
                                       # This surfaces contradictions across time


# ── Node models ───────────────────────────────────────────────────────────────

class SessionNode(BaseModel):
    """
    Represents one conversation or work session with an AI tool.
    Entry point into the graph — all decisions trace back to a session.
    """
    id:           str                  # UUID
    tool:         str                  # "claude", "chatgpt", "gemini", "cursor", etc.
    project_id:   Optional[str]        # Links to a Project node
    raw_excerpt:  Optional[str]        # First 500 chars for display only
    started_at:   datetime
    captured_via: str                  # "mcp", "browser_extension", "manual_paste"


class DecisionNode(BaseModel):
    """
    The core node. Represents one atomic decision made during a session.

    'atomic' is critical — one decision per node, not "all decisions from a session."
    The extraction pipeline splits compound decisions into individual nodes.

    Epistemic weight starts at 0.7 (neutral-positive) and evolves via outcome signals.
    Weight range: 0.0 (mathematically invisible) to 1.0 (bedrock truth).
    """
    id:                str
    summary:           str             # "Chose PostgreSQL over MongoDB"
    chosen:            str             # What was decided — specific, not vague
    reasoning:         str             # Why — the full reasoning, not a summary
    domain:            str             # "database", "architecture", "api_design", etc.
    situation_context: str             # What problem triggered this decision
    confidence:        float           # Extractor's confidence in this extraction (0-1)
    epistemic_weight:  float = 0.7     # Evolves over time via passive signals
    decay_rate:        float           # λ — set by triage agent based on decision type
    is_invalidated:    bool = False    # Soft delete — never hard delete
    tool:              str             # Which AI tool was used when this was decided
    project_id:        Optional[str]
    session_id:        str
    created_at:        datetime
    last_reinforced:   Optional[datetime]  # Last time a success signal touched this node


class CounterfactualNode(BaseModel):
    """
    THE most important and undervalued node type.

    Stores explicitly rejected alternatives — the roads not taken.
    This is what no existing memory system captures properly.

    When a future session faces a similar decision, the system surfaces:
    "You rejected this exact approach before. Here's why.
    You're about to choose it now — is your situation different?"

    rejection_concern is the specific worry that drove rejection.
    This is more valuable than the rejection itself.
    """
    id:                  str
    rejected_option:     str           # What was considered and rejected
    rejection_reason:    str           # Why it was rejected
    rejection_concern:   str           # The specific worry: "scalability", "complexity",
                                       # "team expertise", "cost", "maintenance burden"
    situation_context:   str           # What situation was this rejected in
    epistemic_weight:    float = 0.8   # Counterfactuals start slightly higher —
                                       # explicit rejection is high-confidence signal
    decision_id:         str           # The decision this was rejected in favor of
    session_id:          str
    created_at:          datetime


class OutcomeNode(BaseModel):
    """
    Tracks what actually happened as a result of a decision.
    Populated passively from multiple signal sources — never manually.

    quality_score: 0.0 = clear failure, 1.0 = clear success
    This score updates the epistemic_weight of the linked DecisionNode.
    """
    id:                  str
    description:         str           # What the outcome was
    quality_score:       float         # 0.0 to 1.0
    signal_sources:      list[str]     # ["git_stability", "override_signal",
                                       #  "propagation_signal", "contradiction_signal"]
    decision_id:         str
    observed_at:         datetime


class ConceptNode(BaseModel):
    """
    Represents a recurring technology, pattern, or idea.
    Enables cross-project linking: "Every time you use FastAPI, you make X decision."
    """
    id:    str
    name:  str                         # "PostgreSQL", "microservices", "JWT", etc.
    type:  str                         # "technology", "pattern", "framework", "principle"


class ProjectNode(BaseModel):
    """
    A codebase or work context. Links sessions across time to the same project.
    """
    id:          str
    name:        str
    description: Optional[str]
    created_at:  datetime


# ── Cypher query templates ────────────────────────────────────────────────────
# These are the queries the retrieval agent uses.
# Defined here so schema and queries stay in sync.

CYPHER = {

    # Create nodes
    "create_session": """
        MERGE (s:Session {id: $id})
        SET s += $props
        RETURN s
    """,

    "create_decision": """
        MERGE (d:Decision {id: $id})
        SET d += $props
        WITH d
        MATCH (s:Session {id: $session_id})
        MERGE (s)-[:PRODUCED]->(d)
        RETURN d
    """,

    "create_counterfactual": """
        MERGE (c:Counterfactual {id: $id})
        SET c += $props
        WITH c
        MATCH (d:Decision {id: $decision_id})
        MERGE (d)-[:REJECTED]->(c)
        RETURN c
    """,

    "create_outcome": """
        MERGE (o:Outcome {id: $id})
        SET o += $props
        WITH o
        MATCH (d:Decision {id: $decision_id})
        MERGE (d)-[:LED_TO]->(o)
        RETURN o
    """,

    # ── Retrieval Layer 1: Semantic search (Atlas Vector → IDs) ──────────────
    # (Vector search happens in MongoDB Atlas — result IDs then used here)

    # ── Retrieval Layer 2: Causal ancestry ───────────────────────────────────
    "causal_ancestry": """
        MATCH (d:Decision {id: $decision_id})
        MATCH path = (ancestor:Decision)-[:CAUSED_BY|SUPERSEDES*1..4]->(d)
        WHERE ancestor.epistemic_weight > 0.3
        AND NOT ancestor.is_invalidated
        RETURN ancestor, relationships(path)
        ORDER BY ancestor.epistemic_weight DESC
        LIMIT 10
    """,

    # ── Retrieval Layer 3: Full decision episode ──────────────────────────────
    "full_episode": """
        MATCH (d:Decision {id: $decision_id})
        OPTIONAL MATCH (d)-[:REJECTED]->(c:Counterfactual)
        OPTIONAL MATCH (d)-[:LED_TO]->(o:Outcome)
        OPTIONAL MATCH (s:Session)-[:PRODUCED]->(d)
        RETURN d, collect(c) as counterfactuals, collect(o) as outcomes, s
    """,

    # ── Retrieval Layer 4: Counterfactual surface ─────────────────────────────
    # THE key query — "you rejected this before, you're choosing it now"
    "surface_counterfactuals": """
        MATCH (c:Counterfactual)
        WHERE c.rejection_concern IN $concerns
        AND c.epistemic_weight > 0.4
        AND NOT exists((c)-[:CHOSEN_LATER]->())
        MATCH (d:Decision)-[:REJECTED]->(c)
        MATCH (s:Session)-[:PRODUCED]->(d)
        RETURN c, d, s
        ORDER BY c.epistemic_weight DESC
        LIMIT 5
    """,

    # ── Pattern detection: same decision made multiple times ──────────────────
    "similar_decisions": """
        MATCH (d:Decision)
        WHERE d.domain = $domain
        AND d.epistemic_weight > 0.5
        AND NOT d.is_invalidated
        RETURN d
        ORDER BY d.epistemic_weight DESC, d.created_at DESC
        LIMIT 8
    """,

    # ── Cross-project contradiction detection ─────────────────────────────────
    "detect_contradictions": """
        MATCH (d1:Decision), (d2:Decision)
        WHERE d1.id <> d2.id
        AND d1.domain = d2.domain
        AND d1.project_id <> d2.project_id
        AND NOT (d1)-[:CONTRADICTS]-(d2)
        AND NOT d1.is_invalidated
        AND NOT d2.is_invalidated
        RETURN d1, d2
        LIMIT 20
    """,

    # ── Epistemic weight update (called by outcome engine) ────────────────────
    "boost_weight": """
        MATCH (d:Decision {id: $decision_id})
        SET d.epistemic_weight = min(1.0, d.epistemic_weight + $delta)
        SET d.last_reinforced = $now
        RETURN d.epistemic_weight
    """,

    "decay_weight": """
        MATCH (d:Decision {id: $decision_id})
        SET d.epistemic_weight = max(0.0, d.epistemic_weight - $delta)
        RETURN d.epistemic_weight
    """,

    # ── Soft invalidation ─────────────────────────────────────────────────────
    "soft_invalidate": """
        MATCH (d:Decision {id: $decision_id})
        SET d.is_invalidated = true
        SET d.epistemic_weight = 0.05
        RETURN d
    """,
}