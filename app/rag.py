import json
import re

from groq import Groq

from app.config import settings
from app.vectorstore import query

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


SYSTEM_PROMPT = """Jesteś doświadczonym analitykiem ekonomicznym specjalizującym się w polskiej gospodarce.
Odpowiadasz na podstawie oficjalnych dokumentów NBP (Narodowy Bank Polski) i GUS (Główny Urząd Statystyczny).

INTERPRETACJA DANYCH GUS BDL:
Dane CPI z GUS BDL używają skali "rok poprzedni = 100":
- wartość 114.4 oznacza inflację 14,4% (wzrost cen o 14,4% rok do roku)
- wartość 100.0 oznacza brak zmiany (inflacja 0%)
- wartość 98.5 oznacza deflację 1,5%
Zawsze przeliczaj i podawaj wynik jako procent zmiany (np. "inflacja wyniosła 14,4%").
Nigdy nie cytuj surowej wartości indeksu (np. "114,4%") jako poziomu inflacji.

Twoje odpowiedzi:
- Są oparte wyłącznie na danych z dostarczonego kontekstu - nie zgadujesz
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

    full_answer = []
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full_answer.append(delta)
            yield "token", delta

    yield "done", None

    chart = _extract_chart("".join(full_answer), context)
    if chart:
        yield "chart", chart


_CHART_SYSTEM = """Jesteś asystentem który analizuje tekst ekonomiczny i generuje konfigurację wykresów.

Jeśli odpowiedź zawiera dane numeryczne nadające się do wizualizacji (szeregi czasowe, porównania lat, trendy),
zwróć obiekt JSON z konfiguracją Chart.js. W przeciwnym razie zwróć null.

Format odpowiedzi - TYLKO czysty JSON (bez markdown, bez komentarzy):
{
  "type": "line" | "bar",
  "title": "Tytuł wykresu",
  "labels": ["2020", "2021", ...],
  "datasets": [
    {"label": "Seria danych", "data": [1.2, 3.4, ...]}
  ]
}

Zasady:
- Użyj "line" dla trendów/szeregów czasowych, "bar" dla porównań kategorii
- Maksymalnie 2 datasety
- labels to zazwyczaj lata lub miesiące
- data to liczby (float/int), bez jednostek
- Jeśli nie ma odpowiednich danych liczbowych → zwróć null
"""


def _extract_chart(answer: str, context: str) -> dict | None:
    prompt = f"Odpowiedź analityka:\n{answer}\n\nDane kontekstowe (fragment):\n{context[:1500]}"
    try:
        resp = _get_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": _CHART_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=512,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.lower() == "null" or not raw:
            return None
        # Strip markdown fences if model added them
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        cfg = json.loads(raw)
        return _sanitize_chart(cfg)
    except Exception:
        return None


def _sanitize_chart(cfg: dict) -> dict | None:
    """Remove trailing null/zero data points that the LLM may have hallucinated."""
    if not isinstance(cfg, dict):
        return None
    datasets = cfg.get("datasets", [])
    labels = cfg.get("labels", [])
    if not datasets or not labels:
        return cfg

    # Find last index with a real value across all datasets
    last_real = -1
    for ds in datasets:
        data = ds.get("data", [])
        for i, v in enumerate(data):
            if v is not None and v != 0:
                last_real = max(last_real, i)

    if last_real < 0:
        return None

    cfg["labels"] = labels[: last_real + 1]
    for ds in datasets:
        ds["data"] = ds["data"][: last_real + 1]
    return cfg
