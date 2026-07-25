from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # Patch collection_count so lifespan sees a populated DB and skips ingestion
    with patch("app.vectorstore.collection_count", return_value=100):
        from app.main import app
        with TestClient(app) as c:
            yield c


def test_status_returns_ready(client):
    with patch("app.vectorstore.collection_count", return_value=100):
        resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "documents_in_db" in data
    assert "ready" in data
    assert data["ready"] is True


def test_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_ask_empty_question_returns_400(client):
    resp = client.post("/ask", json={"question": "   "})
    assert resp.status_code == 400


def test_ask_stream_empty_question_returns_400(client):
    resp = client.post("/ask/stream", json={"question": ""})
    assert resp.status_code == 400


def test_ask_returns_answer(client):
    mock_result = {
        "answer": "Inflacja w 2024 wyniosła 3.5%.",
        "sources": [{"title": "GUS CPI", "source": "GUS", "date": "2024", "url": ""}],
    }
    # Patch where the function is used (main.py imports it directly)
    with patch("app.main.answer", return_value=mock_result):
        resp = client.post("/ask", json={"question": "jaka jest inflacja?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Inflacja w 2024 wyniosła 3.5%."
    assert len(body["sources"]) == 1


def test_ask_passes_history(client):
    mock_result = {"answer": "odpowiedź", "sources": []}
    history = [
        {"role": "user", "content": "poprzednie pytanie"},
        {"role": "assistant", "content": "poprzednia odpowiedź"},
    ]
    with patch("app.main.answer", return_value=mock_result) as mock_answer:
        client.post("/ask", json={"question": "pytanie", "history": history})
    mock_answer.assert_called_once_with("pytanie", history)


def test_ask_stream_returns_sse_events(client):
    def mock_stream(question, history):
        yield "sources", []
        yield "token", "Inflacja "
        yield "token", "wyniosła 3.5%."
        yield "done", None

    with patch("app.main.stream_answer", side_effect=mock_stream):
        resp = client.post("/ask/stream", json={"question": "inflacja?"})

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "token" in body
    assert "done" in body
