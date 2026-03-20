"""
Engram — Atlas Vector Search client.
Uses Gemini REST API directly — no SDK version conflicts.
Model: gemini-embedding-001 via v1beta, output truncated to 768 dims.
"""
import os
import requests
from typing import Optional
from pymongo import MongoClient

VECTOR_INDEX     = "engram_vector_index"
MONGO_DB         = "engram"
MONGO_COLLECTION = "vectors"
EMBEDDING_MODEL  = "gemini-embedding-001"
GEMINI_API_URL   = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent"
EMBEDDING_DIMS   = 768

_mongo_client = None
_collection   = None


def _get_collection():
    global _mongo_client, _collection
    if _collection is None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI not set.")
        _mongo_client = MongoClient(uri)
        _collection   = _mongo_client[MONGO_DB][MONGO_COLLECTION]
    return _collection


def _embed(text: str, task_type: str = "retrieval_document") -> list[float]:
    """
    Call Gemini REST API for embeddings.
    output_dimensionality=768 keeps compatibility with existing Atlas index.
    task_type: retrieval_document for writes, retrieval_query for searches.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    payload = {
        "model":                f"models/{EMBEDDING_MODEL}",
        "content":              {"parts": [{"text": text}]},
        "taskType":             task_type,
        "output_dimensionality": EMBEDDING_DIMS,
    }
    resp = requests.post(
        f"{GEMINI_API_URL}?key={api_key}",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


# ── Write operations ───────────────────────────────────────────────────────────

def embed_and_store_decision(
    decision_id: str,
    summary: str,
    reasoning: str,
    domain: str,
    situation_context: str,
    project_id: Optional[str] = None,
) -> bool:
    try:
        text      = f"{summary}. Context: {situation_context}. Reasoning: {reasoning}"
        embedding = _embed(text, task_type="retrieval_document")
        doc = {
            "_id":        decision_id,
            "node_type":  "decision",
            "summary":    summary,
            "domain":     domain,
            "project_id": project_id,
            "embedding":  embedding,
        }
        _get_collection().replace_one({"_id": decision_id}, doc, upsert=True)
        return True
    except Exception as e:
        print(f"Vector write failed for decision {decision_id}: {e}")
        return False


def embed_and_store_counterfactual(
    cf_id: str,
    rejected_option: str,
    rejection_reason: str,
    rejection_concern: str,
    situation_context: str,
    decision_id: str,
    project_id: Optional[str] = None,
) -> bool:
    try:
        text = (
            f"Rejected: {rejected_option}. "
            f"Reason: {rejection_reason}. "
            f"Concern: {rejection_concern}. "
            f"Context: {situation_context}"
        )
        embedding = _embed(text, task_type="retrieval_document")
        doc = {
            "_id":               cf_id,
            "node_type":         "counterfactual",
            "rejected_option":   rejected_option,
            "rejection_concern": rejection_concern,
            "decision_id":       decision_id,
            "project_id":        project_id,
            "embedding":         embedding,
        }
        _get_collection().replace_one({"_id": cf_id}, doc, upsert=True)
        return True
    except Exception as e:
        print(f"Vector write failed for counterfactual {cf_id}: {e}")
        return False


# ── Search operations ──────────────────────────────────────────────────────────

def semantic_search(
    query: str,
    limit: int = 8,
    domain_filter: Optional[str] = None,
    node_type_filter: str = "decision",
) -> list[dict]:
    try:
        query_embedding = _embed(query, task_type="retrieval_query")
        collection      = _get_collection()

        vector_stage = {
            "$vectorSearch": {
                "index":         VECTOR_INDEX,
                "path":          "embedding",
                "queryVector":   query_embedding,
                "numCandidates": limit * 10,
                "limit":         limit,
            }
        }

        if domain_filter:
            vector_stage["$vectorSearch"]["filter"] = {"domain": {"$eq": domain_filter}}

        pipeline = [
            vector_stage,
            {"$project": {
                "_id": 1, "node_type": 1, "domain": 1,
                "project_id": 1, "summary": 1, "rejected_option": 1,
                "score": {"$meta": "vectorSearchScore"},
            }}
        ]

        results = list(collection.aggregate(pipeline))
        # Filter by node_type in Python — more reliable than Atlas filter
        if node_type_filter:
            results = [r for r in results if r.get("node_type") == node_type_filter]
        
        return [
            {
                "id":         str(r["_id"]),
                "score":      r.get("score", 0),
                "node_type":  r.get("node_type"),
                "domain":     r.get("domain"),
                "project_id": r.get("project_id"),
                "summary":    r.get("summary", r.get("rejected_option", "")),
            }
            for r in results
        ]
    except Exception as e:
        print(f"Vector search failed: {e}")
        return []


def semantic_search_counterfactuals(
    query: str,
    concern_filter: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    try:
        query_embedding = _embed(query, task_type="retrieval_query")
        collection      = _get_collection()

        cf_filter = {"node_type": {"$eq": "counterfactual"}}
        if concern_filter:
            cf_filter = {"$and": [
                {"node_type":         {"$eq": "counterfactual"}},
                {"rejection_concern": {"$eq": concern_filter}},
            ]}

        pipeline = [
            {"$vectorSearch": {
                "index":         VECTOR_INDEX,
                "path":          "embedding",
                "queryVector":   query_embedding,
                "numCandidates": limit * 10,
                "limit":         limit,
                "filter":        cf_filter,
            }},
            {"$project": {
                "_id": 1, "rejected_option": 1, "rejection_concern": 1,
                "decision_id": 1, "project_id": 1,
                "score": {"$meta": "vectorSearchScore"},
            }}
        ]

        results = list(collection.aggregate(pipeline))
        return [
            {
                "id":                str(r["_id"]),
                "decision_id":       r.get("decision_id"),
                "rejected_option":   r.get("rejected_option"),
                "rejection_concern": r.get("rejection_concern"),
                "project_id":        r.get("project_id"),
                "score":             r.get("score", 0),
            }
            for r in results
        ]
    except Exception as e:
        print(f"Counterfactual vector search failed: {e}")
        return []