from groq import Groq
from app.vectorstore import query
from app.config import settings

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


SYSTEM_PROMPT = """Jesteś doświadczonym analitykiem ekonomicznym specjalizującym się w polskiej gospodarce.
Odpowiadasz na podstawie oficjalnych dokumentów NBP (Narodowy Bank Polski) i GUS (Główny Urząd Statystyczny).

Twoje odpowiedzi:
- Są oparte wyłącznie na danych z dostarczonego kontekstu — nie zgadujesz
- Zawierają konkretne liczby, daty i trendy gdy są dostępne
- Porównują obecną sytuację z wcześniejszymi okresami gdy kontekst na to pozwala
- Wskazują zależności między wskaźnikami (np. inflacja → stopy procentowe → kurs walut)
- Są sformatowane w Markdown: **pogrubienia** dla kluczowych liczb, listy dla wielu punktów
- Jeśli dane są niewystarczające, piszesz to wprost

Odpowiadaj po polsku. Jeśli pytanie nawiązuje do poprzedniej odpowiedzi, uwzględnij kontekst rozmowy."""


def _build_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    context_parts = []
    for i, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        label = f"[{i+1}] {meta.get('source', 'Nieznane')} ({meta.get('date', '')})"
        context_parts.append(f"{label}\n{chunk['text']}")
    context = "\n\n---\n\n".join(context_parts)

    sources = [
        {
            "title": c["metadata"].get("title", ""),
            "source": c["metadata"].get("source", ""),
            "date": c["metadata"].get("date", ""),
            "url": c["metadata"].get("url", ""),
        }
        for c in chunks
    ]
    return context, sources


def answer(question: str, history: list[dict] | None = None) -> dict:
    chunks = query(question)

    if not chunks:
        return {
            "answer": "Brak dokumentów w bazie. Uruchom najpierw ingestion.",
            "sources": [],
        }

    context, sources = _build_context(chunks)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-6:])
    messages.append({
        "role": "user",
        "content": f"Kontekst z bazy wiedzy:\n{context}\n\nPytanie: {question}",
    })

    response = _get_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
    )

    return {"answer": response.choices[0].message.content, "sources": sources}


def stream_answer(question: str, history: list[dict] | None = None):
    """Generator yielding (event_type, data) tuples for SSE streaming."""
    chunks = query(question)

    if not chunks:
        yield "error", "Brak dokumentów w bazie."
        return

    context, sources = _build_context(chunks)
    yield "sources", sources

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-6:])
    messages.append({
        "role": "user",
        "content": f"Kontekst z bazy wiedzy:\n{context}\n\nPytanie: {question}",
    })

    stream = _get_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield "token", delta

    yield "done", None
