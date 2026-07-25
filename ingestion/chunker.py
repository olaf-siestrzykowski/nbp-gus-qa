from app.config import settings


def chunk_text(text: str, doc_id: str, metadata: dict) -> list[dict]:
    size = settings.chunk_size
    overlap = settings.chunk_overlap
    chunks = []
    start = 0
    idx = 0
    text = text.strip()

    while start < len(text):
        end = start + size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append({
                "id": f"{doc_id}__chunk{idx}",
                "text": chunk,
                "metadata": metadata,
            })
            idx += 1
        start += size - overlap

    return chunks
