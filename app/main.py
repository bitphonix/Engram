"""
Engram — FastAPI application entry point.
"""
try:
    from ddtrace import patch_all
    patch_all()
except ImportError:
    pass

import sentry_sdk
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from app.graph.pipeline import pipeline
from app.db.neo4j_client import (
    setup_constraints,
    get_similar_decisions,
    get_full_episode,
    surface_counterfactuals,
)
from app.agents.retrieval import retrieve_context
from app.agents.weight_engine import run_weight_engine, get_graph_stats, boost_retrieved_decisions

# ── Sentry ────────────────────────────────────────────────────────────────────
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    traces_sample_rate=1.0,
    environment=os.getenv("APP_ENV", "development"),
)

app = FastAPI(
    title="Engram",
    description="Developer decision intelligence — causal memory across AI sessions",
    version="0.1.0",
)

# ── Startup: create Neo4j constraints and indexes ─────────────────────────────
@app.on_event("startup")
def on_startup():
    try:
        setup_constraints()
    except Exception as e:
        print(f"Warning: Neo4j constraint setup failed: {e}")


# ── Serve frontend ─────────────────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.get("/")
def serve_frontend():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Engram API running. Frontend not built yet."}


# ── Request / Response models ──────────────────────────────────────────────────
class IngestRequest(BaseModel):
    content:      str
    tool:         str = "unknown"
    captured_via: str = "manual_paste"
    project_id:   Optional[str] = None
    user_id:      Optional[str] = None


class IngestResponse(BaseModel):
    session_id:            Optional[str]
    saved_decisions:       int
    saved_counterfactuals: int
    is_high_signal:        bool
    session_summary:       Optional[str]
    domain_primary:        Optional[str]
    critique_score:        Optional[int]
    error:                 Optional[str] = None


class ContextRequest(BaseModel):
    query:      str
    domain:     Optional[str] = None
    concerns:   Optional[List[str]] = None
    project_id: Optional[str] = None


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "engram"}


@app.get("/graph/stats")
def graph_stats():
    """Returns live knowledge graph health metrics."""
    return get_graph_stats()


@app.post("/graph/run-engine")
def run_engine():
    """
    Manually triggers the epistemic weight engine.
    In production this runs on a schedule — here exposed for testing.
    """
    return run_weight_engine()


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    """
    Main ingestion endpoint.
    Accepts raw session content, runs the LangGraph pipeline,
    writes decisions + counterfactuals to Neo4j.
    """
    if len(req.content.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Content too short. Paste at least a few exchanges."
        )

    initial_state = {
        "raw_content":   req.content,
        "tool":          req.tool,
        "captured_via":  req.captured_via,
        "project_id":    req.project_id,
        "user_id":       req.user_id,
        "retry_count":   0,
        "is_high_signal": True,
        "saved_decision_ids":    [],
        "saved_counterfact_ids": [],
    }

    result = pipeline.invoke(initial_state)

    return IngestResponse(
        session_id=            result.get("session_id"),
        saved_decisions=       len(result.get("saved_decision_ids", [])),
        saved_counterfactuals= len(result.get("saved_counterfact_ids", [])),
        is_high_signal=        result.get("is_high_signal", True),
        session_summary=       result.get("session_summary"),
        domain_primary=        result.get("domain_primary"),
        critique_score=        result.get("critique_score"),
        error=                 result.get("error"),
    )


@app.get("/decisions")
def get_decisions(domain: Optional[str] = None):
    """Returns similar past decisions for a given domain."""
    if not domain:
        raise HTTPException(status_code=400, detail="domain parameter required")
    return get_similar_decisions(domain)


@app.get("/decisions/{decision_id}")
def get_decision(decision_id: str):
    """Returns full episode: decision + counterfactuals + outcomes."""
    episode = get_full_episode(decision_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Decision not found")
    return episode


@app.post("/context")
def get_context(req: ContextRequest):
    """
    4-level context retrieval.
    Returns relevant past decisions and counterfactual warnings
    for injecting into a new AI session.
    """
    warnings = []
    if req.concerns:
        warnings = surface_counterfactuals(req.concerns)

    decisions = []
    if req.domain:
        decisions = get_similar_decisions(req.domain)

    # Build injection briefing
    briefing_parts = []

    if decisions:
        briefing_parts.append("RELEVANT PAST DECISIONS:")
        for d in decisions[:3]:
            briefing_parts.append(
                f"- {d.get('summary', '')} "
                f"(confidence: {d.get('epistemic_weight', 0):.1f})"
            )

    if warnings:
        briefing_parts.append("\nCOUNTERFACTUAL WARNINGS — you rejected these before:")
        for w in warnings:
            cf = w.get("counterfactual", {})
            briefing_parts.append(
                f"- You rejected '{cf.get('rejected_option', '')}' "
                f"because: {cf.get('rejection_reason', '')} "
                f"[concern: {cf.get('rejection_concern', '')}]"
            )

    briefing = "\n".join(briefing_parts) if briefing_parts else "No relevant past decisions found."

    return {
        "relevant_decisions":      decisions[:5],
        "counterfactual_warnings": warnings,
        "briefing":                briefing,
        "token_estimate":          len(briefing.split()) * 1.3,
    }