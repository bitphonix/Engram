"""
Engram — 4-Level Causal Retrieval Agent.

This is what makes Engram fundamentally different from mem0 and claude-mem.

The 4 levels:
  Level 1: Semantic search — fast ID lookup, ~50 tokens per result
  Level 2: Causal ancestry — what led to similar decisions across history
  Level 3: Full episode — the chosen path + its outcome quality signal
  Level 4: Counterfactual surface — rejected alternatives you should know about

The agent is given a query (what the user is about to decide) and traverses
the knowledge graph to build a context injection that fits in ~500 tokens.
"""
import os
import json
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI

from app.db.neo4j_client import (
    get_similar_decisions,
    get_causal_ancestry,
    get_full_episode,
    surface_counterfactuals,
    get_driver,
)
from app.db.schema import CYPHER

# Flash model — retrieval synthesis doesn't need pro
_flash = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
)


# ── Level 1: Semantic search (Atlas Vector Search) ────────────────────────────
def level1_search(query: str, domain: str = None, limit: int = 8) -> list[dict]:
    """
    True semantic search over all stored decision vectors.
    Uses Atlas Vector Search with cosine similarity.

    Returns decision IDs + summaries + scores.
    Token cost: ~50 tokens per result.

    Falls back to Neo4j domain search if Atlas is unavailable.
    """
    from app.db.vector_client import semantic_search

    # Try vector search first
    vector_results = semantic_search(
        query=query,
        limit=limit,
        domain_filter=domain,   # None = search all domains
        node_type_filter="decision",
    )

    if vector_results:
        return vector_results

    # Fallback to Neo4j domain filter if vector search fails
    if domain:
        decisions = get_similar_decisions(domain)
        return [
            {
                "id":               d.get("id"),
                "summary":          d.get("summary"),
                "epistemic_weight": d.get("epistemic_weight"),
                "domain":           d.get("domain"),
                "score":            d.get("epistemic_weight", 0.7),
            }
            for d in decisions[:limit]
        ]
    return []


# ── Level 2: Causal ancestry ──────────────────────────────────────────────────
def level2_ancestry(decision_ids: list[str]) -> list[dict]:
    """
    Traverses the causal graph upstream from each decision.
    Finds what led to similar decisions — the history behind the history.
    Token cost: ~100 tokens per ancestor chain.
    """
    all_ancestors = []
    for decision_id in decision_ids[:3]:  # limit to top 3 decisions
        ancestors = get_causal_ancestry(decision_id)
        if ancestors:
            all_ancestors.extend(ancestors)
    return all_ancestors


# ── Level 3: Full episode ─────────────────────────────────────────────────────
def level3_episodes(decision_ids: list[str]) -> list[dict]:
    """
    Fetches full decision episodes for the most relevant decisions.
    Includes: decision + counterfactuals + outcomes.
    Token cost: ~300-500 tokens per episode.
    Only fetches top 2 to stay within token budget.
    """
    episodes = []
    for decision_id in decision_ids[:2]:
        episode = get_full_episode(decision_id)
        if episode:
            episodes.append(episode)
    return episodes


# ── Level 4: Counterfactual surface ──────────────────────────────────────────
def level4_counterfactuals(concerns: list[str]) -> list[dict]:
    """
    THE key retrieval layer — surfaces past rejections relevant to current concerns.

    If you're about to make a decision involving 'scalability' concerns,
    this finds every past decision where an alternative was rejected
    specifically because of scalability — across all projects and time.

    This is what nobody else has. The counterfactual memory.
    Token cost: ~150 tokens per warning.
    """
    if not concerns:
        return []
    return surface_counterfactuals(concerns)


# ── Concern extractor ─────────────────────────────────────────────────────────
def extract_concerns_from_query(query: str) -> list[str]:
    """
    Analyzes the user's query to identify what concerns are relevant.
    This determines which counterfactuals to surface in Level 4.
    """
    prompt = f"""Given this developer query about a decision they're about to make,
identify which concerns are most relevant.

Query: {query}

Return ONLY a JSON array of concerns from this list:
["scalability", "complexity", "cost", "team_expertise", "performance",
 "maintenance_burden", "security", "vendor_lock_in", "latency", "consistency"]

Return maximum 3 concerns. Example: ["scalability", "cost"]
Return raw JSON only, no markdown.
"""
    try:
        response = _flash.invoke(prompt)
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        concerns = json.loads(text)
        return concerns if isinstance(concerns, list) else []
    except Exception:
        return []


# ── Domain extractor ──────────────────────────────────────────────────────────
def extract_domain_from_query(query: str) -> str:
    """Identifies the decision domain from the query."""
    prompt = f"""Given this query, return ONLY one domain word from this list:
database, architecture, api_design, authentication, infrastructure,
framework, algorithm, data_model, deployment, testing, security, performance, other

Query: {query}

Return just the single word, nothing else."""
    try:
        response = _flash.invoke(prompt)
        return response.content.strip().lower().split()[0]
    except Exception:
        return "other"


# ── Briefing synthesizer ──────────────────────────────────────────────────────
def synthesize_briefing(
    query: str,
    level1_results: list[dict],
    level3_episodes: list[dict],
    level4_warnings: list[dict],
) -> str:
    """
    Synthesizes all retrieval levels into a single injected briefing.
    Target: ~400-600 tokens. Dense, structured, immediately actionable.
    """
    # Build context for the synthesizer
    past_decisions_text = ""
    if level1_results:
        lines = []
        for d in level1_results[:4]:
            weight = d.get("epistemic_weight", 0)
            lines.append(
                f"- {d.get('summary', '')} "
                f"[confidence: {weight:.1f}]"
            )
        past_decisions_text = "\n".join(lines)

    episodes_text = ""
    if level3_episodes:
        parts = []
        for ep in level3_episodes:
            d = ep.get("decision", {})
            cfs = ep.get("counterfactuals", [])
            outcomes = ep.get("outcomes", [])
            episode_str = f"Decision: {d.get('summary', '')}\nReasoning: {d.get('reasoning', '')}"
            if cfs:
                cf_lines = [f"  Rejected '{c.get('rejected_option','')}': {c.get('rejection_reason','')}" for c in cfs[:3]]
                episode_str += "\nRejected alternatives:\n" + "\n".join(cf_lines)
            if outcomes:
                episode_str += f"\nOutcome: {outcomes[0].get('description', '')}"
            parts.append(episode_str)
        episodes_text = "\n\n".join(parts)

    warnings_text = ""
    if level4_warnings:
        lines = []
        for w in level4_warnings[:3]:
            cf = w.get("counterfactual", {})
            lines.append(
                f"⚠ You previously rejected '{cf.get('rejected_option', '')}' "
                f"because: {cf.get('rejection_reason', '')} "
                f"[concern: {cf.get('rejection_concern', '')}]"
            )
        warnings_text = "\n".join(lines)

    prompt = f"""You are injecting historical decision context into a developer's AI session.

CURRENT QUESTION: {query}

PAST DECISIONS:
{past_decisions_text or "None."}

FULL EPISODES:
{episodes_text or "None."}

COUNTERFACTUAL WARNINGS:
{warnings_text or "None."}

Write EXACTLY this structure — no markdown, no bold, no extra sections:

PAST DECISIONS: [2-3 sentences about relevant past choices. If none, write "No relevant past decisions found."]
WARNINGS: [One line per warning starting with "- You rejected X because Y." If none, write "None."]
RECOMMENDATION: [One sentence starting with "Based on your history,"]

Rules:
- No markdown formatting, no ** bold **, no headers with #
- No numbered lists
- Exactly 3 lines starting with PAST DECISIONS:, WARNINGS:, RECOMMENDATION:
- Max 150 words total
- Do not add any text before or after these 3 lines
"""
    try:
        response = _flash.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        return f"Context retrieval available but synthesis failed: {str(e)}"


# ── Main retrieval function ───────────────────────────────────────────────────
def retrieve_context(
    query: str,
    domain: Optional[str] = None,
    concerns: Optional[list[str]] = None,
) -> dict:
    """
    Full 4-level retrieval pipeline.
    Called by the /context endpoint.

    Args:
        query:    What the user is about to decide
        domain:   Override domain detection (optional)
        concerns: Override concern extraction (optional)

    Returns:
        dict with all retrieval levels + synthesized briefing
    """
    # Extract domain and concerns if not provided
    resolved_domain   = domain
    resolved_concerns = concerns or extract_concerns_from_query(query)

    # Level 1: True semantic search over Atlas Vector Search
    l1 = level1_search(query=query, domain=resolved_domain)

    # Level 2: Causal ancestry (only if we found decisions)
    decision_ids = [d["id"] for d in l1 if d.get("id")]
    # Fallback: if Atlas is down, use Neo4j domain search for IDs
    if not decision_ids and resolved_domain:
        fallback = get_similar_decisions(resolved_domain)
        decision_ids = [d.get("id") for d in fallback if d.get("id")]
        l1 = fallback
    l2 = level2_ancestry(decision_ids) if decision_ids else []

    # Level 3: Full episodes for top decisions
    l3 = level3_episodes(decision_ids) if decision_ids else []

    # Level 4: Counterfactual warnings
    l4 = level4_counterfactuals(resolved_concerns)

    # Synthesize into injection briefing
    briefing = synthesize_briefing(query, l1, l3, l4)

    return {
        "query":                   query,
        "domain":                  resolved_domain,
        "concerns":                resolved_concerns,
        "level1_decisions":        l1,
        "level2_ancestors":        l2,
        "level3_episodes":         l3,
        "level4_warnings":         l4,
        "briefing":                briefing,
        "token_estimate":          int(len(briefing.split()) * 1.3),
        "decisions_found":         len(l1),
        "warnings_found":          len(l4),
    }