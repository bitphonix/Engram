"""
Engram — Create Atlas Vector Search Index.
Run once to set up the vector index in MongoDB Atlas.

Usage:
    doppler run -- python scripts/create_vector_index.py
"""
import os
import time
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel


def create_vector_index():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI not set. Run with: doppler run -- python scripts/create_vector_index.py")

    print("Connecting to MongoDB Atlas...")
    client = MongoClient(uri)

    database   = client["engram"]

    if "vectors" not in database.list_collection_names():
        print("Creating 'vectors' collection...")
        database.create_collection("vectors")

    collection = database["vectors"]

    # ── Check if index already exists ────────────────────────────────────────
    existing = list(collection.list_search_indexes())
    for idx in existing:
        if idx.get("name") == "engram_vector_index":
            print("✓ Index 'engram_vector_index' already exists and is ready.")
            client.close()
            return

    # ── Create the vector search index ───────────────────────────────────────
    print("Creating vector search index...")

    model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 768,     # Gemini text-embedding-004 output size
                    "similarity": "cosine"
                },
                {
                    "type": "filter",
                    "path": "domain"           # filter by domain at query time
                },
                {
                    "type": "filter",
                    "path": "node_type"        # filter by Decision vs Counterfactual
                },
                {
                    "type": "filter",
                    "path": "project_id"       # filter by project at query time
                }
            ]
        },
        name="engram_vector_index",
        type="vectorSearch"
    )

    result = collection.create_search_index(model=model)
    print(f"Index '{result}' is building...")

    # ── Wait for index to become queryable ────────────────────────────────────
    print("Waiting for index to become active (may take 1-2 minutes)...")
    while True:
        indices = list(collection.list_search_indexes(result))
        if indices and indices[0].get("queryable") is True:
            break
        print("  still building...")
        time.sleep(5)

    print(f"✓ '{result}' is active and ready for querying.")
    client.close()


if __name__ == "__main__":
    create_vector_index()