"""
Engram — LangGraph node functions.
Each node has a single responsibility and returns only the state fields it changes.

Node order:
  triage_node → extractor_node → critique_node → [retry or] → graph_writer_node
"""
import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI

from app.graph.state import State
from app.models.extraction import (
    TriageOutput, ExtractionOutput, ExtractedDecision, ExtractedCounterfactual
)

# ── LLM setup ─────────────────────────────────────────────────────────────────
# Flash for triage and critique — fast, cheap, no deep reasoning needed
# Pro for extraction — quality matters, counterfactuals need nuanced reasoning
_flash = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
)

_pro = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
)

_triage_chain  = _flash.with_structured_output(TriageOutput)


def _parse_json(text: str) -> dict:
    """Strip markdown fences from Gemini output and parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


# ── Node 1: Triage ─────────────────────────────────────────────────────────────
def triage_node(state: State) -> dict:
    """
    First gate — is this content worth processing?
    Uses flash model. Cheap and fast.
    Prevents noise (typo fixes, trivial questions) from polluting the graph.
    """
    prompt = f"""You are a memory triage agent for a developer decision intelligence system.

Analyze this content and determine if it contains real decisions worth storing.

HIGH SIGNAL (store):
- Architectural decisions (database choice, framework selection, design patterns)
- Explicit rejections ("we decided NOT to use X because...")
- Bug fixes that reveal something about system design
- Preferences that will affect future decisions
- Any choice with reasoning attached

LOW SIGNAL (skip):
- Typo fixes, formatting changes
- Trivial questions with no decision
- Small code adjustments with no architectural impact
- Casual conversation

Content to triage:
{state["raw_content"][:2000]}
"""
    try:
        result: TriageOutput = _triage_chain.invoke(prompt)
        return {
            "triage": result,
            "is_high_signal": result.is_high_signal,
        }
    except Exception as e:
        # On triage failure, assume high signal — better to over-capture than miss
        return {
            "is_high_signal": True,
            "error": f"Triage failed (defaulted high): {str(e)}",
        }


# ── Node 2: Extractor ──────────────────────────────────────────────────────────
def extractor_node(state: State) -> dict:
    """
    Core extraction — pulls atomic decisions AND their counterfactuals.
    Uses pro model. This is the most important node.

    Key difference from ContextBridge:
    - Splits compound decisions into individual atomic nodes
    - Extracts counterfactuals (rejected alternatives) as first-class data
    - Assigns decay rates based on decision type
    - Extracts rejection_concern as controlled vocabulary for graph querying
    """
    feedback_section = ""
    if state.get("critique_feedback"):
        feedback_section = f"""
PREVIOUS ATTEMPT FEEDBACK — address these issues:
{state["critique_feedback"]}
"""

    prompt = f"""You are extracting a decision knowledge graph from a developer's AI session.

Your goal: find every ATOMIC decision made, and for each decision, find every
alternative that was explicitly or implicitly REJECTED.

CRITICAL RULES:
1. Split compound decisions. "We chose PostgreSQL and FastAPI" → two separate decisions.
2. Counterfactuals are the most valuable data. Capture every rejected path with specific reasoning.
3. rejection_concern must be from this list ONLY:
   scalability, complexity, cost, team_expertise, performance,
   maintenance_burden, security, vendor_lock_in, latency, consistency, other
4. decay_rate assignment:
   - 0.01 = architectural (database choice, framework, system design) — lasts months
   - 0.05 = design choice (API structure, data model) — lasts weeks
   - 0.15 = bug fix or workaround — lasts days
   - 0.30 = trivial preference — lasts hours
5. Return ONLY raw JSON, no markdown fences.
{feedback_section}

Session content:
{state["raw_content"]}

Return this exact JSON structure:
{{
  "decisions": [
    {{
      "summary": "Chose X over Y because Z",
      "chosen": "specific technology or approach",
      "reasoning": "full reasoning for this choice",
      "domain": "one of: database|architecture|api_design|authentication|infrastructure|framework|algorithm|data_model|deployment|testing|security|performance|other",
      "situation_context": "what problem triggered this decision",
      "confidence": 0.0-1.0,
      "decay_rate": 0.01-0.30,
      "counterfactuals": [
        {{
          "rejected_option": "specific thing rejected",
          "rejection_reason": "full reason for rejection",
          "rejection_concern": "one concern from the controlled list"
        }}
      ]
    }}
  ],
  "session_summary": "two sentences: what this session was about and the most important decision",
  "project_context": "project name or null",
  "domain_primary": "primary domain of this session"
}}
"""
    try:
        response = _pro.invoke(prompt)
        data = _parse_json(response.content)
        output = ExtractionOutput(**data)
        return {
            "decisions":       output.decisions,
            "session_summary": output.session_summary,
            "project_context": output.project_context,
            "domain_primary":  output.domain_primary,
        }
    except Exception as e:
        return {"error": f"Extractor failed: {str(e)}"}


# ── Node 3: Critique ───────────────────────────────────────────────────────────
def critique_node(state: State) -> dict:
    """
    Quality gate — validates the extraction before writing to the graph.
    Checks specifically for counterfactual quality, not just decision quality.
    Uses flash model.
    """
    decisions = state.get("decisions") or []
    if not decisions:
        return {"critique_score": 0, "critique_feedback": "No decisions extracted."}

    decisions_text = json.dumps(
        [d.model_dump() if hasattr(d, 'model_dump') else d for d in decisions],
        indent=2, default=str
    )

    prompt = f"""You are evaluating a decision extraction for a developer memory system.

Score this extraction 0-10. Passing score is 7.

Evaluate on:
1. Are decisions truly atomic? (one choice per node)
2. Are counterfactuals specific? (not "other options" but "MongoDB Atlas")
3. Does each rejection have a clear, specific reason?
4. Are rejection_concerns correctly categorized?
5. Is the reasoning full enough to be useful months later?

Extracted decisions:
{decisions_text}

Return JSON only:
{{
  "score": 0-10,
  "feedback": "specific improvements needed, or null if passing"
}}
"""
    try:
        response = _flash.invoke(prompt)
        data = _parse_json(response.content)
        return {
            "critique_score":    data.get("score", 7),
            "critique_feedback": data.get("feedback"),
        }
    except Exception as e:
        # Default pass on critique failure
        return {"critique_score": 7, "critique_feedback": None,
                "error": f"Critique failed (defaulted pass): {str(e)}"}


# ── Node 4: Graph Writer ───────────────────────────────────────────────────────
def graph_writer_node(state: State) -> dict:
    """
    Writes all extracted decisions and counterfactuals to Neo4j.
    Called only after critique passes.

    For each decision:
    1. Creates a Session node (if not exists)
    2. Creates one Decision node per atomic decision
    3. Creates one Counterfactual node per rejected alternative
    4. Creates all relationships in the graph

    This is where the knowledge graph gets built.
    """
    from app.db.neo4j_client import save_session, save_decision, save_counterfactual

    decisions = state.get("decisions") or []
    if not decisions:
        return {"saved_decision_ids": [], "saved_counterfact_ids": []}

    try:
        # Create session node
        session_id = save_session(
            tool=state.get("tool", "unknown"),
            project_id=state.get("project_id"),
            captured_via=state.get("captured_via", "manual_paste"),
            raw_excerpt=state["raw_content"][:500],
        )

        saved_decision_ids   = []
        saved_counterfact_ids = []

        for decision in decisions:
            # Handle both Pydantic model and dict
            d = decision if isinstance(decision, dict) else decision.model_dump()

            # Skip low-confidence extractions
            if d.get("confidence", 1.0) < 0.5:
                continue

            decision_id = save_decision(
                summary=          d["summary"],
                chosen=           d["chosen"],
                reasoning=        d["reasoning"],
                domain=           d["domain"],
                situation_context=d["situation_context"],
                session_id=       session_id,
                tool=             state.get("tool", "unknown"),
                confidence=       d.get("confidence", 0.8),
                project_id=       state.get("project_id"),
                decay_rate=       d.get("decay_rate", 0.05),
            )
            saved_decision_ids.append(decision_id)

            # Write counterfactuals — the most valuable data
            for cf in d.get("counterfactuals", []):
                c = cf if isinstance(cf, dict) else cf.model_dump()
                cf_id = save_counterfactual(
                    rejected_option=  c["rejected_option"],
                    rejection_reason= c["rejection_reason"],
                    rejection_concern=c["rejection_concern"],
                    situation_context=d["situation_context"],
                    decision_id=      decision_id,
                    session_id=       session_id,
                )
                saved_counterfact_ids.append(cf_id)

        return {
            "session_id":           session_id,
            "saved_decision_ids":   saved_decision_ids,
            "saved_counterfact_ids": saved_counterfact_ids,
        }

    except Exception as e:
        return {"error": f"Graph writer failed: {str(e)}"}


# ── Node 5: Low Signal Handler ─────────────────────────────────────────────────
def low_signal_node(state: State) -> dict:
    """
    Called when triage decides content is not worth processing.
    Returns gracefully without hitting expensive cloud APIs.
    """
    return {
        "saved_decision_ids":    [],
        "saved_counterfact_ids": [],
        "session_id":            None,
    }


# ── Node 6: Retry Incrementer ──────────────────────────────────────────────────
def increment_retry(state: State) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1}