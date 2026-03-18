"""
Engram — Conditional edge functions.
These functions determine routing between nodes.
"""
from app.graph.state import State

PASS_SCORE = 7
MAX_RETRIES = 2


def route_after_triage(state: State) -> str:
    """
    After triage: route to extractor if high signal, low_signal_node if not.
    """
    if state.get("is_high_signal", True):
        return "extractor_node"
    return "low_signal_node"


def route_after_critique(state: State) -> str:
    """
    After critique: save to graph if passing, retry if failing.
    """
    score       = state.get("critique_score", 0)
    retry_count = state.get("retry_count", 0)

    if retry_count >= MAX_RETRIES:
        return "graph_writer_node"  # Force save even if imperfect
    if score >= PASS_SCORE:
        return "graph_writer_node"
    return "increment_retry"