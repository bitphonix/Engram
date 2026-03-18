"""
Engram — Shared pipeline state.
Every node reads from and writes to this object.
Write this file first, before any agent logic.
"""
from typing import Optional
from typing_extensions import TypedDict
from app.models.extraction import ExtractedDecision, TriageOutput, RetrievalContext


class State(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    raw_content:    str            # Pasted conversation or captured session text
    tool:           str            # "claude", "chatgpt", "gemini", "cursor", etc.
    project_id:     Optional[str]  # Links to Project node in Neo4j
    captured_via:   str            # "mcp", "browser_extension", "manual_paste"
    user_id:        Optional[str]  # For per-user graph scoping

    # ── Triage output ─────────────────────────────────────────────────────────
    triage:         Optional[TriageOutput]   # Is this worth processing?
    is_high_signal: bool                     # Fast access to triage result

    # ── Extraction output ─────────────────────────────────────────────────────
    decisions:        Optional[list[ExtractedDecision]]  # Atomic decisions found
    session_summary:  Optional[str]
    project_context:  Optional[str]
    domain_primary:   Optional[str]

    # ── Critique output ───────────────────────────────────────────────────────
    critique_score:    Optional[int]    # 0-10
    critique_feedback: Optional[str]   # What to improve on retry

    # ── Graph write output ────────────────────────────────────────────────────
    session_id:          Optional[str]   # Neo4j Session node ID
    saved_decision_ids:  list[str]       # Neo4j Decision node IDs
    saved_counterfact_ids: list[str]     # Neo4j Counterfactual node IDs

    # ── Retrieval output (for context injection) ──────────────────────────────
    retrieval_context: Optional[RetrievalContext]

    # ── Control flow ──────────────────────────────────────────────────────────
    retry_count: int
    error:       Optional[str]