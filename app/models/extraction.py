"""
Pydantic models for the LangGraph extraction pipeline.
These define what the LLM must output — the Field descriptions
are the actual instructions sent to Gemini.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ExtractedCounterfactual(BaseModel):
    """One rejected alternative from a decision."""

    rejected_option: str = Field(
        description=(
            "What was explicitly considered and rejected. "
            "Be specific: not 'other databases' but 'MongoDB Atlas'."
        )
    )
    rejection_reason: str = Field(
        description="Why it was rejected. Full reasoning, not a summary."
    )
    rejection_concern: str = Field(
        description=(
            "The single core concern that drove rejection. "
            "Must be one of: scalability, complexity, cost, team_expertise, "
            "performance, maintenance_burden, security, vendor_lock_in, "
            "latency, consistency, other."
        )
    )


class ExtractedDecision(BaseModel):
    """
    One atomic decision extracted from a conversation.
    Atomic = one choice, not a bundle of choices.
    """

    summary: str = Field(
        description="One sentence: 'Chose X over Y for Z reason'."
    )
    chosen: str = Field(
        description="Exactly what was chosen. Specific technology, approach, or pattern."
    )
    reasoning: str = Field(
        description=(
            "The full reasoning. Why this was chosen. "
            "What constraints, requirements, or concerns drove this choice."
        )
    )
    domain: str = Field(
        description=(
            "The decision domain. Must be one of: "
            "database, architecture, api_design, authentication, "
            "infrastructure, framework, algorithm, data_model, "
            "deployment, testing, security, performance, other."
        )
    )
    situation_context: str = Field(
        description=(
            "What problem or situation triggered this decision. "
            "What were the constraints? What was the user trying to achieve?"
        )
    )
    confidence: float = Field(
        description="How confident you are this is a real decision (0.0-1.0).",
        ge=0.0, le=1.0
    )
    counterfactuals: List[ExtractedCounterfactual] = Field(
        description=(
            "All alternatives that were explicitly or implicitly rejected. "
            "This is the most important field — capture every rejected path. "
            "If nothing was rejected, return empty list."
        ),
        default_factory=list,
    )
    decay_rate: float = Field(
        description=(
            "How quickly this decision becomes obsolete. "
            "0.01 = architectural (lasts months), "
            "0.05 = design choice (lasts weeks), "
            "0.15 = bug fix or workaround (lasts days), "
            "0.30 = trivial preference (lasts hours)."
        ),
        ge=0.01, le=0.30
    )


class ExtractionOutput(BaseModel):
    """
    Full extraction result from one session.
    May contain multiple atomic decisions.
    """

    decisions: List[ExtractedDecision] = Field(
        description=(
            "All atomic decisions made in this conversation. "
            "Split compound decisions into individual nodes. "
            "If no real decisions were made, return empty list."
        ),
        default_factory=list,
    )
    session_summary: str = Field(
        description=(
            "Two sentences: what this session was about and "
            "what the most important decision was."
        )
    )
    project_context: Optional[str] = Field(
        description="The project or codebase this session was about, if identifiable.",
        default=None,
    )
    domain_primary: str = Field(
        description="The primary domain of this session (same options as decision domain)."
    )


class TriageOutput(BaseModel):
    """
    Output from the local triage agent.
    Decides if content is worth processing before hitting cloud APIs.
    """

    is_high_signal: bool = Field(
        description=(
            "True if this content contains real decisions, architectural choices, "
            "or explicit rejections worth storing. "
            "False for typo fixes, formatting changes, trivial questions."
        )
    )
    signal_type: str = Field(
        description=(
            "Type of signal. One of: "
            "architectural_decision, bug_fix, preference, "
            "workflow_change, knowledge_gain, trivial."
        )
    )
    reason: str = Field(
        description="One sentence explaining the triage decision."
    )


class RetrievalContext(BaseModel):
    """
    Structured context injected into a new session.
    Built by the 4-level retrieval agent from the knowledge graph.
    """

    relevant_decisions: List[dict] = Field(default_factory=list)
    causal_ancestors:   List[dict] = Field(default_factory=list)
    counterfactual_warnings: List[dict] = Field(default_factory=list,
        description="Rejected alternatives from past sessions relevant to current context"
    )
    briefing: str = Field(
        description="Ready-to-inject context briefing for the new session."
    )
    token_count: int = Field(
        description="Estimated tokens in this context injection."
    )