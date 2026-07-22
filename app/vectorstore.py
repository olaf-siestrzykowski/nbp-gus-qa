import chromadb
from chromadb.config import Settings as ChromaSettings
import requests
from app.config import settings
import logging

logger = logging.getLogger(__name__)

_client = None
_collection = None

JINA_API = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _embed(texts: list[str], task: str) -> list[list[float]]:
    response = requests.post(
        JINA_API,
        headers={"Authorization": f"Bearer {settings.jina_api_key}"},
        json={"model": JINA_MODEL, "input": texts, "task": task},
        timeout=60,
    )
    response.raise_for_status()
    return [item["embedding"] for item in response.json()["data"]]


def add_documents(chunks: list[dict]) -> int:
    collection = _get_collection()
    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [c.get("metadata", {}) for c in chunks]
    embeddings = _embed(texts, task="retrieval.passage")
    collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    return len(chunks)


def query(text: str, top_k: int = None) -> list[dict]:
    k = top_k or settings.top_k
    collection = _get_collection()
    embedding = _embed([text], task="retrieval.query")[0]
    results = collection.query(query_embeddings=[embedding], n_results=k)
    return [
        {
            "text": doc,
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        }
        for i, doc in enumerate(results["documents"][0])
    ]


def collection_count() -> int:
    return _get_collection().count()
