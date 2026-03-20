"""
Engram — Vector Search client using ChromaDB (local-first).

Stores embeddings on disk at ~/.engram/chroma — no network dependency,
no IP whitelisting, works on any network. Embeddings are generated via
the Gemini REST API and stored locally.

Architecture:
  Write time: Decision/counterfactual saved → embed → store in ChromaDB
  Read time:  Query → embed → ChromaDB cosine similarity → decision IDs

ChromaDB replaces MongoDB Atlas Vector Search. Same cosine similarity,
same 768-dimension embeddings, zero external service dependency.
"""
import os
import requests
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

CHROMA_DIR      = Path.home() / ".engram" / "chroma"
COLLECTION_NAME = "engram_decisions"
EMBEDDING_MODEL = "gemini-embedding-001"
GEMINI_API_URL  = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent"
EMBEDDING_DIMS  = 768

_client     = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _embed(text: str, task_type: str = "retrieval_document") -> list[float]:
    """
    Gemini REST API embedding. No SDK — no version conflicts.
    output_dimensionality=768 matches our ChromaDB collection config.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    payload = {
        "model":                 f"models/{EMBEDDING_MODEL}",
        "content":               {"parts": [{"text": text}]},
        "taskType":              task_type,
        "output_dimensionality": EMBEDDING_DIMS,
    }
    resp = requests.post(
        f"{GEMINI_API_URL}?key={api_key}",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]



def embed_and_store_decision(
    decision_id: str,
    summary: str,
    reasoning: str,
    domain: str,
    situation_context: str,
    project_id: Optional[str] = None,
) -> bool:
    """
    Embeds a decision and stores it in ChromaDB.
    Called by graph_writer_node after each decision is saved to Neo4j.
    """
    try:
        text      = f"{summary}. Context: {situation_context}. Reasoning: {reasoning}"
        embedding = _embed(text, task_type="retrieval_document")
        col       = _get_collection()

        col.upsert(
            ids=[decision_id],
            embeddings=[embedding],
            metadatas=[{
                "node_type":  "decision",
                "summary":    summary[:500],
                "domain":     domain or "other",
                "project_id": project_id or "",
            }],
            documents=[text[:1000]],
        )
        return True
    except Exception as e:
        print(f"ChromaDB write failed for decision {decision_id}: {e}")
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
    """
    Embeds a counterfactual and stores it in ChromaDB.
    Counterfactuals are searchable — enables Level 4 semantic warnings.
    """
    try:
        text = (
            f"Rejected: {rejected_option}. "
            f"Reason: {rejection_reason}. "
            f"Concern: {rejection_concern}. "
            f"Context: {situation_context}"
        )
        embedding = _embed(text, task_type="retrieval_document")
        col       = _get_collection()

        col.upsert(
            ids=[cf_id],
            embeddings=[embedding],
            metadatas=[{
                "node_type":         "counterfactual",
                "rejected_option":   rejected_option[:200],
                "rejection_concern": rejection_concern or "",
                "decision_id":       decision_id,
                "project_id":        project_id or "",
            }],
            documents=[text[:1000]],
        )
        return True
    except Exception as e:
        print(f"ChromaDB write failed for counterfactual {cf_id}: {e}")
        return False



def semantic_search(
    query: str,
    limit: int = 8,
    domain_filter: Optional[str] = None,
    node_type_filter: str = "decision",
) -> list[dict]:
    """
    Level 1 retrieval — cosine similarity search over all stored vectors.
    No network required. Works on any network. Instant.

    domain_filter=None searches ALL domains — key for cross-domain retrieval.
    """
    try:
        query_embedding = _embed(query, task_type="retrieval_query")
        col             = _get_collection()

        where = None
        if domain_filter and node_type_filter:
            where = {"$and": [
                {"domain":    {"$eq": domain_filter}},
                {"node_type": {"$eq": node_type_filter}},
            ]}
        elif domain_filter:
            where = {"domain": {"$eq": domain_filter}}
        elif node_type_filter:
            where = {"node_type": {"$eq": node_type_filter}}

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results":        min(limit, col.count()),
            "include":          ["metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        if col.count() == 0:
            return []

        results = col.query(**kwargs)

        ids        = results["ids"][0]
        metadatas  = results["metadatas"][0]
        distances  = results["distances"][0]

        return [
            {
                "id":         ids[i],
                "score":      round(1 - distances[i], 4),
                "node_type":  metadatas[i].get("node_type"),
                "domain":     metadatas[i].get("domain"),
                "project_id": metadatas[i].get("project_id") or None,
                "summary":    metadatas[i].get("summary", ""),
            }
            for i in range(len(ids))
        ]
    except Exception as e:
        print(f"ChromaDB search failed: {e}")
        return []


def semantic_search_counterfactuals(
    query: str,
    concern_filter: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """
    Semantic search specifically over counterfactual nodes.
    Used by Level 4 retrieval to find semantically similar rejections.
    """
    try:
        query_embedding = _embed(query, task_type="retrieval_query")
        col             = _get_collection()

        if col.count() == 0:
            return []

        where = {"node_type": {"$eq": "counterfactual"}}
        if concern_filter:
            where = {"$and": [
                {"node_type":         {"$eq": "counterfactual"}},
                {"rejection_concern": {"$eq": concern_filter}},
            ]}

        results = col.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, col.count()),
            where=where,
            include=["metadatas", "distances"],
        )

        ids       = results["ids"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        return [
            {
                "id":                ids[i],
                "decision_id":       metadatas[i].get("decision_id"),
                "rejected_option":   metadatas[i].get("rejected_option"),
                "rejection_concern": metadatas[i].get("rejection_concern"),
                "project_id":        metadatas[i].get("project_id") or None,
                "score":             round(1 - distances[i], 4),
            }
            for i in range(len(ids))
        ]
    except Exception as e:
        print(f"ChromaDB counterfactual search failed: {e}")
        return []


def get_collection_stats() -> dict:
    """Returns ChromaDB collection health info."""
    try:
        col = _get_collection()
        return {
            "total_vectors": col.count(),
            "storage_path":  str(CHROMA_DIR),
            "backend":       "chromadb_local",
        }
    except Exception as e:
        return {"error": str(e)}