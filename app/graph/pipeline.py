"""
Engram — LangGraph pipeline assembly.

Graph flow:
  START
    → triage_node
        → [low signal] → low_signal_node → END
        → [high signal] → extractor_node
            → critique_node
                → [pass] → graph_writer_node → END
                → [fail] → increment_retry → extractor_node (loop, max 2)
"""
from langgraph.graph import StateGraph, START, END
from app.graph.state import State
from app.graph.nodes import (
    triage_node,
    extractor_node,
    critique_node,
    graph_writer_node,
    low_signal_node,
    increment_retry,
)
from app.graph.edges import route_after_triage, route_after_critique


def build_pipeline():
    graph = StateGraph(State)

    # ── Register nodes ─────────────────────────────────────────────────────
    graph.add_node("triage_node",       triage_node)
    graph.add_node("extractor_node",    extractor_node)
    graph.add_node("critique_node",     critique_node)
    graph.add_node("graph_writer_node", graph_writer_node)
    graph.add_node("low_signal_node",   low_signal_node)
    graph.add_node("increment_retry",   increment_retry)

    # ── Main flow ──────────────────────────────────────────────────────────
    graph.add_edge(START, "triage_node")

    graph.add_conditional_edges(
        "triage_node",
        route_after_triage,
        {
            "extractor_node": "extractor_node",
            "low_signal_node": "low_signal_node",
        }
    )

    graph.add_edge("extractor_node",    "critique_node")

    graph.add_conditional_edges(
        "critique_node",
        route_after_critique,
        {
            "graph_writer_node": "graph_writer_node",
            "increment_retry":   "increment_retry",
        }
    )

    graph.add_edge("increment_retry",   "extractor_node")
    graph.add_edge("graph_writer_node", END)
    graph.add_edge("low_signal_node",   END)

    return graph.compile()


# Compiled once at import time — reused across all requests
pipeline = build_pipeline()