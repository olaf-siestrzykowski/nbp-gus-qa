from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    groq_api_key: str
    jina_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    chroma_path: str = str(BASE_DIR / "data" / "chroma")
    chroma_collection: str = "nbp_gus_docs"
    top_k: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 100

    class Config:
        env_file = ".env"


settings = Settings()
