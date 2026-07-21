from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import logging

from app.rag import answer
from app.vectorstore import collection_count

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NBP/GUS Economic Q&A", version="0.1.0")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class QuestionRequest(BaseModel):
    question: str


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
    result = answer(req.question)
    return result


@app.get("/status")
def status():
    count = collection_count()
    return {"documents_in_db": count, "ready": count > 0}
