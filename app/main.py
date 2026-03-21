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
    get_graph_network,
)
from app.agents.retrieval import retrieve_context
from app.agents.weight_engine import run_weight_engine, get_graph_stats, boost_retrieved_decisions

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

@app.on_event("startup")
def on_startup():
    try:
        setup_constraints()
    except Exception as e:
        print(f"Warning: Neo4j constraint setup failed: {e}")


FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.get("/")
def serve_frontend():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Engram API running. Frontend not built yet."}


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
    critique_score:        Optional[float]
    error:                 Optional[str] = None


class ContextRequest(BaseModel):
    query:      str
    domain:     Optional[str] = None
    concerns:   Optional[List[str]] = None
    project_id: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "engram"}


@app.get("/graph/stats")
def graph_stats():
    """Returns live knowledge graph health metrics."""
    return get_graph_stats()


@app.post("/graph/run-engine")
def run_engine():
    """Triggers the epistemic weight engine."""
    return run_weight_engine()


@app.get("/graph/network")
def graph_network():
    """Returns all Decision nodes and typed edges for D3.js visualization."""
    return get_graph_network()


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    """
    Main ingestion endpoint.
    Accepts raw session content, runs the LangGraph pipeline,
    writes decisions + counterfactuals to Neo4j + Atlas.
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

    try:
        result = pipeline.invoke(initial_state)
    except Exception as e:
        # Pipeline failed — save to local queue for retry
        from app.queue import enqueue_failed
        path = enqueue_failed(
            content=      req.content,
            tool=         req.tool,
            captured_via= req.captured_via,
            project_id=   req.project_id,
            error=        str(e),
        )
        return IngestResponse(
            session_id=            None,
            saved_decisions=       0,
            saved_counterfactuals= 0,
            is_high_signal=        True,
            session_summary=       None,
            domain_primary=        None,
            critique_score=        None,
            error=f"queued for retry: {str(e)[:100]}",
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


@app.post("/search")
def quick_search(req: ContextRequest):
    """
    Fast search endpoint for CLI — skips briefing synthesis.
    Returns Level 1 vector results + Level 4 warnings only.
    """
    from app.db.vector_client import semantic_search
    from app.db.neo4j_client import surface_counterfactuals

    decisions = semantic_search(req.query, limit=8, domain_filter=req.domain)
    warnings  = surface_counterfactuals(req.concerns) if req.concerns else []

    return {
        "decisions": decisions,
        "warnings":  warnings,
    }

@app.post("/context")
def get_context(req: ContextRequest):
    """
    4-level causal retrieval.
    Level 1: Atlas Vector Search — semantic similarity
    Level 2: Neo4j causal ancestry — CAUSED_BY traversal
    Level 3: Full episodes — decision + counterfactuals + outcomes
    Level 4: Counterfactual surface — rejected paths by concern
    """
    result = retrieve_context(
        query=req.query,
        domain=req.domain,
        concerns=req.concerns,
    )
    # Propagation boost — retrieved decisions gain epistemic weight
    retrieved_ids = [d.get("id") for d in result.get("level1_decisions", []) if d.get("id")]
    if retrieved_ids:
        boost_retrieved_decisions(retrieved_ids)
    return result