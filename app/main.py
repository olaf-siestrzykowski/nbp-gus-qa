import json
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.rag import LLM_ERROR_MESSAGE, answer, stream_answer
from app.ratelimit import rate_limit
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
        logger.info("DB empty - starting background ingestion.")
        threading.Thread(target=_run_ingestion, daemon=True).start()
    else:
        logger.info("DB already populated - skipping ingestion.")
    yield


app = FastAPI(title="NBP/GUS Economic Q&A", version="0.1.0", lifespan=lifespan)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class HistoryMessage(BaseModel):
    # Only user/assistant turns: a client must not be able to inject a "system" message
    role: Literal["user", "assistant"]
    content: str = Field(max_length=12_000)  # an answer is at most ~2k tokens


class QuestionRequest(BaseModel):
    # Bounded so one request cannot burn a large number of tokens
    question: str = Field(max_length=1_000)
    history: list[HistoryMessage] = Field(default=[], max_length=12)


class AnswerResponse(BaseModel):
    answer: str
    sources: list[dict]


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


def _history(req: QuestionRequest) -> list[dict]:
    return [m.model_dump() for m in req.history]


# Empty questions are rejected before the rate limit, so they do not use up the quota
def _require_question(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Pytanie nie może być puste.")


@app.post("/ask", response_model=AnswerResponse, dependencies=[Depends(_require_question), Depends(rate_limit)])
def ask(req: QuestionRequest):
    try:
        return answer(req.question, _history(req))
    except Exception:
        logger.exception("LLM call failed (model=%s)", settings.groq_model)
        raise HTTPException(status_code=502, detail=LLM_ERROR_MESSAGE)


@app.post("/ask/stream", dependencies=[Depends(_require_question), Depends(rate_limit)])
def ask_stream(req: QuestionRequest):
    def generate():
        for event_type, data in stream_answer(req.question, _history(req)):
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
        # Not ready while the index is still being (re)built or if building it failed
        "ready": count > 0 and not _ingestion_status["running"] and _ingestion_status["error"] is None,
        "ingestion_running": _ingestion_status["running"],
        "ingestion_error": _ingestion_status["error"],
    }
