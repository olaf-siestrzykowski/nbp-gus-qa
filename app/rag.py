from groq import Groq
from app.vectorstore import query
from app.config import settings

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


SYSTEM_PROMPT = """Jesteś asystentem analitycznym specjalizującym się w polskiej gospodarce.
Odpowiadasz na pytania na podstawie oficjalnych dokumentów NBP (Narodowy Bank Polski) i GUS (Główny Urząd Statystyczny).
Odpowiadaj wyłącznie na podstawie podanych fragmentów. Jeśli informacja nie wynika z kontekstu, powiedz wprost że nie masz danych.
Odpowiadaj po polsku, zwięźle i rzeczowo. Podawaj daty i liczby gdy są dostępne w kontekście."""


def answer(question: str) -> dict:
    chunks = query(question)

    if not chunks:
        return {
            "answer": "Brak dokumentów w bazie. Uruchom najpierw ingestion.",
            "sources": [],
        }

    context_parts = []
    for i, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        source_label = f"[{i+1}] {meta.get('source', 'Nieznane')} ({meta.get('date', '')})"
        context_parts.append(f"{source_label}\n{chunk['text']}")

    context = "\n\n---\n\n".join(context_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Kontekst:\n{context}\n\nPytanie: {question}",
        },
    ]

    response = _get_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0.2,
        max_tokens=1024,
    )

    answer_text = response.choices[0].message.content

    sources = [
        {
            "title": c["metadata"].get("title", ""),
            "source": c["metadata"].get("source", ""),
            "date": c["metadata"].get("date", ""),
            "url": c["metadata"].get("url", ""),
        }
        for c in chunks
    ]

    return {"answer": answer_text, "sources": sources}
