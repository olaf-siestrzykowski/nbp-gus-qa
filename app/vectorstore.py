import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from app.config import settings
import logging

logger = logging.getLogger(__name__)

_client = None
_collection = None
_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
    return _model


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


def embed(texts: list[str]) -> list[list[float]]:
    return _get_model().encode(texts, show_progress_bar=False).tolist()


def add_documents(chunks: list[dict]) -> int:
    """chunks: list of {id, text, metadata}"""
    collection = _get_collection()
    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [c.get("metadata", {}) for c in chunks]
    embeddings = embed(texts)
    collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    return len(chunks)


def query(text: str, top_k: int = None) -> list[dict]:
    k = top_k or settings.top_k
    collection = _get_collection()
    embedding = embed([text])[0]
    results = collection.query(query_embeddings=[embedding], n_results=k)
    docs = []
    for i, doc in enumerate(results["documents"][0]):
        docs.append({
            "text": doc,
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return docs


def collection_count() -> int:
    return _get_collection().count()
