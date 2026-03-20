"""
Engram — Decision Outcome Linker.

Runs after each decision is written to Neo4j + Atlas.
Creates typed relationship edges between decisions:

  CAUSED_BY   — new decision explicitly builds on a prior one
               detected by: raw_content references prior decision keywords
               e.g. "We chose ClickHouse last month, now we're adding caching"

  SUPERSEDES  — new decision replaces an older one in same domain+project
               detected by: same domain + same project_id → new supersedes old
               e.g. two "database" decisions in "analytics_platform"

  SIMILAR_TO  — two decisions are semantically similar across projects
               detected by: Atlas vector similarity score > 0.85
               e.g. "chose Redis for caching" ~ "chose Redis for rate limiting"

This is what populates Level 2 causal ancestry in retrieval.
"""
from typing import Optional

from app.db.vector_client import semantic_search
from app.db.neo4j_client import (
    create_caused_by_edge,
    create_supersedes_edge,
    create_similar_to_edge,
    get_decisions_by_domain_project,
)

# Similarity thresholds
SIMILAR_TO_THRESHOLD  = 0.87   # high bar — must be genuinely similar
CAUSED_BY_THRESHOLD   = 0.88   # even higher — explicit causal link
SUPERSEDES_THRESHOLD  = 0.80   # same domain+project → likely supersedes


def link_decision(
    decision_id: str,
    summary: str,
    domain: str,
    project_id: Optional[str],
    raw_content: str,
) -> dict:
    """
    Main entry point. Called by graph_writer_node after each decision write.

    Returns a dict of edges created for logging.
    """
    edges_created = {
        "caused_by":   [],
        "supersedes":  [],
        "similar_to":  [],
    }

    try:
        # ── 1. SUPERSEDES — same domain + same project ─────────────────────
        # If there are older decisions in the same domain+project,
        # the new one supersedes them.
        if project_id and domain:
            older = get_decisions_by_domain_project(
                domain=domain,
                project_id=project_id,
                exclude_id=decision_id,
            )
            for old in older:
                old_id = old.get("id")
                if old_id and old_id != decision_id:
                    create_supersedes_edge(
                        new_decision_id=decision_id,
                        old_decision_id=old_id,
                    )
                    edges_created["supersedes"].append(old_id)

        # ── 2. SIMILAR_TO + CAUSED_BY — via Atlas vector search ────────────
        # Find semantically similar decisions across all projects.
        similar = semantic_search(
            query=summary,
            limit=10,
            domain_filter=None,     # search ALL domains
            node_type_filter="decision",
        )

        for result in similar:
            other_id    = result.get("id")
            score       = result.get("score", 0)
            other_summary = result.get("summary", "")

            # Skip self
            if other_id == decision_id:
                continue

            # Skip already superseded decisions
            if other_id in edges_created["supersedes"]:
                continue

            # CAUSED_BY — check if raw_content explicitly references this decision
            # by looking for key terms from the prior decision's summary
            if score >= CAUSED_BY_THRESHOLD:
                prior_keywords = _extract_keywords(other_summary)
                content_lower  = raw_content.lower()
                matches = sum(1 for kw in prior_keywords if kw in content_lower)

                if matches >= 2:
                    create_caused_by_edge(
                        new_decision_id=decision_id,
                        prior_decision_id=other_id,
                    )
                    edges_created["caused_by"].append(other_id)
                    continue  # caused_by is stronger — skip similar_to for this pair

            # SIMILAR_TO — semantically similar but not explicitly causal
            if score >= SIMILAR_TO_THRESHOLD:
                create_similar_to_edge(
                    decision_id_a=decision_id,
                    decision_id_b=other_id,
                    similarity_score=score,
                )
                edges_created["similar_to"].append(other_id)

    except Exception as e:
        print(f"Linker failed for decision {decision_id}: {e}")

    total = (len(edges_created["caused_by"]) +
             len(edges_created["supersedes"]) +
             len(edges_created["similar_to"]))

    if total:
        print(f"Linker: {decision_id[:8]}… → "
              f"{len(edges_created['caused_by'])} CAUSED_BY, "
              f"{len(edges_created['supersedes'])} SUPERSEDES, "
              f"{len(edges_created['similar_to'])} SIMILAR_TO")

    return edges_created


def _extract_keywords(summary: str) -> list[str]:
    """
    Extract meaningful keywords from a decision summary for CAUSED_BY detection.
    Filters out common stop words and short tokens.
    Returns lowercase keywords.
    """
    stop_words = {
        "chose", "over", "and", "for", "the", "a", "an", "to", "of",
        "in", "due", "its", "with", "from", "that", "this", "was",
        "is", "are", "be", "been", "by", "on", "at", "or", "but",
        "not", "as", "it", "we", "our", "their", "instead", "rather",
        "than", "also", "more", "less", "better", "best", "good",
        "high", "low", "new", "old", "based", "using", "use",
    }
    words = summary.lower().replace(",", " ").replace(".", " ").split()
    return [w for w in words if len(w) > 3 and w not in stop_words]