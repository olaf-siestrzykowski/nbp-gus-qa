import json
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.rag import answer, stream_answer
from app.vectorstore import collection_count

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_ingestion_status = {"running": False, "done": False, "error": None}


def _run_ingestion():
    _ingestion_status["running"] = True
    try:
        from ingestion.ingest import run
        run(embed_only=True)
        _ingestion_status["done"] = True
        logger.info("Background ingestion complete.")
    except Exception as e:
        _ingestion_status["error"] = str(e)
        logger.error(f"Background ingestion failed: {e}")
    finally:
        _ingestion_status["running"] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    if collection_count() == 0:
        logger.info("DB empty — starting background ingestion.")
        threading.Thread(target=_run_ingestion, daemon=True).start()
    else:
        logger.info("DB already populated — skipping ingestion.")
    yield


app = FastAPI(title="NBP/GUS Economic Q&A", version="0.1.0", lifespan=lifespan)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class QuestionRequest(BaseModel):
    question: str
    history: list[dict] = []


class AnswerResponse(BaseModel):
    answer: str
    sources: list[dict]


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.post("/ask", response_model=AnswerResponse)
def ask(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Pytanie nie może być puste.")
    return answer(req.question, req.history)


@app.post("/ask/stream")
def ask_stream(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Pytanie nie może być puste.")

    def generate():
        for event_type, data in stream_answer(req.question, req.history):
            yield f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/status")
def status():
    count = collection_count()
    return {
        "documents_in_db": count,
        "ready": count > 0,
        "ingestion_running": _ingestion_status["running"],
        "ingestion_error": _ingestion_status["error"],
    }
